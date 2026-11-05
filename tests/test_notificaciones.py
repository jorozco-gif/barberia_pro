"""Correos del sistema por SMTP (RF-04, RF-07, RF-21, RF-25, RNF-01, RNF-05 y RNF-10).

Ninguna prueba abre una conexión real ni usa una cuenta de Gmail: smtplib.SMTP y smtplib.SMTP_SSL se
sustituyen por un doble que registra lo que recibiría el servidor. Estas pruebas comprueban la
construcción de los mensajes, la configuración, la autenticación y el cifrado simulados, el manejo de
errores y la integración con services.py. No demuestran que Gmail acepte las credenciales: para eso está
la prueba real de envío (`python notificaciones.py destinatario@ejemplo.com`, ver .env.example).
"""
import datetime
import logging
import socket
import smtplib
import ssl
import threading
import time
from concurrent.futures import Future
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser
from types import SimpleNamespace

import pytest

import database
import models
import notificaciones
import plantillas_correo
from helpers import CLAVE, agendar, crear_cita

ENVIAR = notificaciones.enviar  # la función real; el fixture autouse `correos` la sustituye en cada prueba

CUENTA = "remitente@gmail.test"
CLAVE_DE_APLICACION = "abcd efgh ijkl mnop"  # inventada, con el formato en que Google muestra las contraseñas de aplicación


# ==========================================
# Dobles de prueba
# ==========================================
class RegistroSMTP:
    """Lo que habría recibido el servidor, y fallos que se pueden provocar en cada paso."""

    def __init__(self):
        self.conexiones = []   # (clase, host, puerto, timeout, contexto)
        self.starttls = []     # contextos con los que se pidió STARTTLS
        self.logins = []       # (usuario, contraseña)
        self.mensajes = []
        self.error_conexion = None
        self.error_starttls = None
        self.error_login = None
        self.error_envio = None
        self.espera = None     # threading.Event: el envío no termina hasta que se active
        self.respuesta_data = (250, b"2.0.0 OK  1730000000 a1b2c3 - gsmtp")  # como responde Gmail al mensaje


@pytest.fixture
def smtp(monkeypatch):
    registro = RegistroSMTP()

    class SMTPFalso:
        def __init__(self, host, puerto, timeout=None, context=None, **_):
            if registro.error_conexion:
                raise registro.error_conexion
            registro.conexiones.append((type(self).__name__, host, puerto, timeout, context))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self, context=None):
            if registro.error_starttls:
                raise registro.error_starttls
            registro.starttls.append(context)

        def login(self, usuario, password):
            if registro.error_login:
                raise registro.error_login
            registro.logins.append((usuario, password))
            return (235, b"2.7.0 Accepted")

        def data(self, mensaje):
            return registro.respuesta_data

        def send_message(self, mensaje):
            # Como smtplib: send_message -> sendmail -> data(); si data no responde 250, lanza SMTPDataError.
            if registro.espera is not None:
                registro.espera.wait(10)
            if registro.error_envio:
                raise registro.error_envio
            self.data(mensaje.as_bytes())
            registro.mensajes.append(mensaje)

    class SMTPFalsoSSL(SMTPFalso):
        pass

    monkeypatch.setattr(notificaciones.smtplib, "SMTP", SMTPFalso)
    monkeypatch.setattr(notificaciones.smtplib, "SMTP_SSL", SMTPFalsoSSL)
    return registro


# El aislamiento del .env real y el bloqueo de conexiones están en conftest.py (fixture autouse `sin_smtp_real`).


def configurar(monkeypatch, **variables):
    for nombre, valor in variables.items():
        monkeypatch.setenv(nombre, valor)


@pytest.fixture
def gmail(monkeypatch, smtp):
    """Configuración de Gmail con datos inventados (no son credenciales reales)."""
    configurar(
        monkeypatch, SMTP_HOST="smtp.gmail.com", SMTP_PORT="587", SMTP_USER=CUENTA,
        SMTP_PASSWORD=CLAVE_DE_APLICACION, SMTP_FROM_EMAIL=CUENTA, SMTP_FROM_NAME="BarberShop Pro",
    )
    return smtp


class EjecutorInmediato:
    """Sustituye al hilo de envío para que la entrega termine antes de que la prueba compruebe nada."""

    def submit(self, funcion, *args):
        futuro = Future()
        futuro.set_result(funcion(*args))
        return futuro


@pytest.fixture
def envio_real(monkeypatch):
    """Restaura el envío real (el fixture `correos` lo sustituye) y lo hace síncrono."""
    monkeypatch.setattr(notificaciones, "enviar", ENVIAR)
    monkeypatch.setattr(notificaciones, "_ejecutor", EjecutorInmediato())


def mensaje_recibido(mensaje):
    """El mensaje tal como lo leería un cliente de correo: se serializa y se vuelve a interpretar."""
    return BytesParser(policy=policy.default).parsebytes(mensaje.as_bytes())


def cuerpo_de(mensaje, tipo):
    return mensaje.get_body(preferencelist=(tipo,)).get_content()


# ==========================================
# Configuración (variables de entorno)
# ==========================================
def test_sin_smtp_host_no_hay_configuracion():
    assert notificaciones.cargar_config() is None


def test_configuracion_completa_de_gmail(gmail):
    config = notificaciones.cargar_config()
    assert (config.host, config.puerto, config.usuario) == ("smtp.gmail.com", 587, CUENTA)
    assert (config.remitente_correo, config.remitente_nombre) == (CUENTA, "BarberShop Pro")


def test_valores_por_defecto(monkeypatch):
    configurar(monkeypatch, SMTP_HOST="correo.test")
    config = notificaciones.cargar_config()
    assert config.puerto == 587 and config.usuario == "" and config.password == ""
    assert config.remitente_correo == notificaciones.REMITENTE_POR_DEFECTO
    assert config.remitente_nombre == plantillas_correo.NOMBRE_NEGOCIO


def test_el_remitente_es_el_usuario_si_no_se_define_smtp_from_email(monkeypatch):
    configurar(monkeypatch, SMTP_HOST="smtp.gmail.com", SMTP_USER=CUENTA, SMTP_PASSWORD="x")
    assert notificaciones.cargar_config().remitente_correo == CUENTA


def test_smtp_from_antiguo_sigue_funcionando_y_smtp_from_email_tiene_prioridad(monkeypatch):
    configurar(monkeypatch, SMTP_HOST="correo.test", SMTP_FROM="Citas <citas@barbershop.test>")
    config = notificaciones.cargar_config()
    assert (config.remitente_correo, config.remitente_nombre) == ("citas@barbershop.test", "Citas")
    configurar(monkeypatch, SMTP_FROM_EMAIL="nuevo@barbershop.test", SMTP_FROM_NAME="Barbería Pro")
    config = notificaciones.cargar_config()
    assert (config.remitente_correo, config.remitente_nombre) == ("nuevo@barbershop.test", "Barbería Pro")


@pytest.mark.parametrize("puerto", ["abc", "0", "70000", "-1"])
def test_puerto_invalido(monkeypatch, puerto):
    configurar(monkeypatch, SMTP_HOST="correo.test", SMTP_PORT=puerto)
    with pytest.raises(notificaciones.ConfiguracionSMTPError, match="SMTP_PORT"):
        notificaciones.cargar_config()


@pytest.mark.parametrize("variables, falta", [
    ({"SMTP_USER": CUENTA}, "SMTP_PASSWORD"),
    ({"SMTP_PASSWORD": "valor-secreto"}, "SMTP_USER"),
])
def test_usuario_y_contrasena_deben_definirse_juntos(monkeypatch, variables, falta):
    configurar(monkeypatch, SMTP_HOST="correo.test", **variables)
    with pytest.raises(notificaciones.ConfiguracionSMTPError, match=falta) as error:
        notificaciones.cargar_config()
    assert "valor-secreto" not in str(error.value)  # el mensaje nombra la variable, nunca su valor


def test_remitente_invalido(monkeypatch):
    configurar(monkeypatch, SMTP_HOST="correo.test", SMTP_FROM_EMAIL="sin-arroba")
    with pytest.raises(notificaciones.ConfiguracionSMTPError, match="SMTP_FROM_EMAIL"):
        notificaciones.cargar_config()


def test_gmail_se_quitan_los_espacios_de_la_contrasena_de_aplicacion(gmail, monkeypatch):
    assert notificaciones.cargar_config().password == "abcdefghijklmnop"
    configurar(monkeypatch, SMTP_HOST="otro.servidor.test")
    assert notificaciones.cargar_config().password == CLAVE_DE_APLICACION  # en otros servidores se respeta tal cual


def test_la_contrasena_no_aparece_en_la_representacion_de_la_configuracion(gmail):
    config = notificaciones.cargar_config()
    assert "abcdefghijklmnop" not in repr(config) and "abcd" not in str(config)


# ==========================================
# Construcción del mensaje
# ==========================================
def config_de_prueba(**cambios):
    datos = dict(host="correo.test", puerto=587, usuario="u", password="p",
                 remitente_correo="citas@barbershop.test", remitente_nombre="Barbería Pro")
    datos.update(cambios)
    return notificaciones.ConfigSMTP(**datos)


def test_el_mensaje_lleva_texto_plano_y_html_en_utf8():
    original = notificaciones.construir_mensaje(
        config_de_prueba(), "ana@test.com", "Recupera tu contraseña - BarberShop Pro",
        "Hola Ana, texto plano con ñ y tildes: Sánchez", "<html><body><p>Hola Ana, HTML con ñ</p></body></html>",
    )
    m = mensaje_recibido(original)
    assert m.get_content_type() == "multipart/alternative"
    assert [parte.get_content_type() for parte in m.iter_parts()] == ["text/plain", "text/html"]
    assert "Sánchez" in cuerpo_de(m, "plain") and "HTML con ñ" in cuerpo_de(m, "html")
    assert m["Subject"] == "Recupera tu contraseña - BarberShop Pro"
    remitente = m["From"].addresses[0]
    assert (remitente.display_name, remitente.addr_spec) == ("Barbería Pro", "citas@barbershop.test")
    assert m["To"].addresses[0].addr_spec == "ana@test.com"
    assert m["Date"] and m["Message-ID"].endswith("@barbershop.test>")
    assert m["Auto-Submitted"] == "auto-generated"


def test_sin_html_el_mensaje_es_solo_texto():
    m = notificaciones.construir_mensaje(config_de_prueba(), "ana@test.com", "Asunto", "Solo texto")
    assert not m.is_multipart() and m.get_content_type() == "text/plain"


def test_un_destinatario_con_salto_de_linea_no_puede_inyectar_cabeceras(gmail):
    with pytest.raises(ValueError):
        notificaciones.construir_mensaje(config_de_prueba(), "ana@test.com\nBcc: otra@test.com", "Asunto", "Texto")
    assert notificaciones.entregar("ana@test.com\nBcc: otra@test.com", "Asunto", "Texto") is False
    assert gmail.mensajes == []


# ==========================================
# Entrega por SMTP (con el doble)
# ==========================================
def test_puerto_587_usa_starttls_con_certificado_verificado_y_autentica(gmail):
    assert notificaciones.entregar("ana@test.com", "Asunto", "Texto", "<p>HTML</p>") is True
    clase, host, puerto, timeout, _ = gmail.conexiones[0]
    assert (clase, host, puerto, timeout) == ("SMTPFalso", "smtp.gmail.com", 587, 10)
    contexto = gmail.starttls[0]
    assert contexto.verify_mode == ssl.CERT_REQUIRED and contexto.check_hostname is True
    assert gmail.logins == [(CUENTA, "abcdefghijklmnop")]  # sin espacios
    m = mensaje_recibido(gmail.mensajes[0])
    assert m["To"].addresses[0].addr_spec == "ana@test.com"
    assert m["From"].addresses[0].addr_spec == CUENTA
    assert cuerpo_de(m, "plain").strip() == "Texto" and "<p>HTML</p>" in cuerpo_de(m, "html")


def test_puerto_465_usa_ssl_con_certificado_verificado(gmail, monkeypatch):
    configurar(monkeypatch, SMTP_PORT="465")
    assert notificaciones.entregar("ana@test.com", "Asunto", "Texto") is True
    clase, host, puerto, _, contexto = gmail.conexiones[0]
    assert (clase, host, puerto) == ("SMTPFalsoSSL", "smtp.gmail.com", 465)
    assert contexto.verify_mode == ssl.CERT_REQUIRED and contexto.check_hostname is True
    assert gmail.starttls == [] and len(gmail.logins) == 1


def test_sin_usuario_no_se_autentica(smtp, monkeypatch):
    configurar(monkeypatch, SMTP_HOST="relay.interno.test")
    assert notificaciones.entregar("ana@test.com", "Asunto", "Texto") is True
    assert smtp.logins == [] and len(smtp.mensajes) == 1


def test_sin_smtp_host_solo_se_registra_que_no_se_envio_sin_el_contenido(smtp, caplog):
    """El contenido puede llevar el enlace de recuperación con su token: no se escribe en el registro."""
    with caplog.at_level(logging.WARNING, logger="barberia.notificaciones"):
        assert notificaciones.entregar("ana@test.com", "Asunto", "Enlace: http://x/restablecer?token=SECRETO") is False
    assert "Correo no enviado «Asunto» para an***@test.com" in caplog.text
    assert "reinicia el backend" in caplog.text  # el .env solo se lee al arrancar
    assert "SECRETO" not in caplog.text and "ana@test.com" not in caplog.text
    assert smtp.conexiones == []


def test_configuracion_incompleta_no_abre_conexion_ni_registra_el_contenido(smtp, monkeypatch, caplog):
    configurar(monkeypatch, SMTP_HOST="smtp.gmail.com", SMTP_USER=CUENTA)  # falta la contraseña
    with caplog.at_level(logging.ERROR, logger="barberia.notificaciones"):
        assert notificaciones.entregar("ana@test.com", "Asunto", "Enlace secreto del correo") is False
    assert smtp.conexiones == []
    assert "SMTP_PASSWORD" in caplog.text and "Enlace secreto del correo" not in caplog.text


# ==========================================
# Errores de SMTP
# ==========================================
@pytest.mark.parametrize("paso, error, pista", [
    ("error_login", smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted"), "contraseña de aplicación"),
    ("error_conexion", ConnectionRefusedError(111, "Connection refused"), "no se pudo conectar"),
    ("error_conexion", socket.gaierror(-2, "Name or service not known"), "no se pudo conectar"),
    ("error_conexion", smtplib.SMTPServerDisconnected("Connection unexpectedly closed"), "no se pudo conectar"),
    ("error_conexion", TimeoutError("timed out"), "no respondió a tiempo"),
    ("error_conexion", ssl.SSLCertVerificationError(1, "certificate verify failed"), "certificado"),
    ("error_conexion", ssl.SSLError(1, "wrong version number"), "cifrado"),
    ("error_starttls", smtplib.SMTPNotSupportedError("STARTTLS extension not supported by server."), "STARTTLS"),
    ("error_envio", smtplib.SMTPRecipientsRefused({"ana@test.com": (550, b"No such user")}), "destinatario"),
    ("error_envio", smtplib.SMTPSenderRefused(553, b"5.7.1 not allowed", CUENTA), "remitente"),
    ("error_envio", smtplib.SMTPDataError(550, b"5.4.5 Daily user sending limit exceeded"), "límite diario"),
    ("error_envio", RuntimeError("fallo inesperado"), "inesperado"),
])
def test_los_errores_de_smtp_se_registran_con_su_causa_y_no_se_propagan(gmail, caplog, paso, error, pista):
    setattr(gmail, paso, error)
    with caplog.at_level(logging.ERROR, logger="barberia.notificaciones"):
        assert notificaciones.entregar("ana@test.com", "Asunto", "Texto") is False  # no lanza excepción
    assert "No se pudo enviar el correo «Asunto» a an***@test.com" in caplog.text
    etapa = {"error_conexion": "conexión", "error_starttls": "cifrado", "error_login": "autenticación", "error_envio": "envío"}[paso]
    assert f"Falló en la etapa: {etapa} ({type(error).__name__}" in caplog.text
    assert pista in caplog.text
    assert "ana@test.com" not in caplog.text
    assert gmail.mensajes == []


def test_el_registro_muestra_cada_etapa_y_la_respuesta_del_servidor_al_aceptar(gmail, caplog):
    with caplog.at_level(logging.INFO, logger="barberia.notificaciones"):
        assert notificaciones.entregar("ana@test.com", "Asunto", "Texto") is True
    # Solo las líneas de este hilo: un envío en segundo plano de otra prueba podría escribir a la vez.
    lineas = [r.getMessage() for r in caplog.records if r.thread == threading.get_ident()]
    etapas = ["Conectando con smtp.gmail.com:587 (STARTTLS)", "Conexión cifrada", "certificado de smtp.gmail.com verificado",
              f"Autenticación aceptada para {CUENTA} (235 2.7.0 Accepted)", "ACEPTADO por smtp.gmail.com"]
    posiciones = [next(i for i, l in enumerate(lineas) if e in l) for e in etapas]
    assert posiciones == sorted(posiciones)
    assert "Respuesta del servidor: 250 2.0.0 OK 1730000000 a1b2c3 - gsmtp" in lineas[-1]
    numero = lineas[0].split(":")[0]
    assert numero.startswith("Correo #") and all(l.startswith(numero + ":") for l in lineas)


def test_el_error_de_autenticacion_muestra_la_respuesta_del_servidor_sin_credenciales(monkeypatch, gmail, caplog):
    # Un servidor que repitiera la contraseña en su respuesta no debe hacer que llegue al registro.
    gmail.error_login = smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted abcdefghijklmnop")
    with caplog.at_level(logging.INFO, logger="barberia.notificaciones"):
        assert notificaciones.entregar("ana@test.com", "Asunto", "Texto") is False
    assert "Conexión cifrada" in caplog.text and "Autenticación aceptada" not in caplog.text
    assert "respuesta del servidor: 535 5.7.8 Username and Password not accepted ****" in caplog.text
    assert "abcdefghijklmnop" not in caplog.text and "ACEPTADO" not in caplog.text


def test_si_el_servidor_rechaza_el_mensaje_no_se_da_por_aceptado(gmail, caplog):
    gmail.error_envio = smtplib.SMTPDataError(554, b"5.7.0 Message rejected")
    with caplog.at_level(logging.INFO, logger="barberia.notificaciones"):
        assert notificaciones.entregar("ana@test.com", "Asunto", "Texto") is False
    assert "Autenticación aceptada" in caplog.text and "ACEPTADO" not in caplog.text
    assert "Falló en la etapa: envío (SMTPDataError; respuesta del servidor: 554 5.7.0 Message rejected)" in caplog.text


@pytest.mark.parametrize("codigo, texto, pista", [
    (534, b"5.7.9 Application-specific password required", "contraseña normal"),
    (535, b"5.7.8 Username and Password not accepted", "misma cuenta"),
])
def test_explicacion_de_los_rechazos_de_autenticacion_de_gmail(codigo, texto, pista):
    explicacion = notificaciones.explicar_error(smtplib.SMTPAuthenticationError(codigo, texto))
    assert pista in explicacion and "contraseña de aplicación" in explicacion


def test_un_correo_tiene_un_solo_destinatario():
    for destino in ("a@test.com,b@test.com", "a@test.com;b@test.com", "a@test.com b@test.com", "Ana <a@test.com>", "sin-arroba"):
        with pytest.raises(ValueError):
            notificaciones.construir_mensaje(config_de_prueba(), destino, "Asunto", "Texto")


def test_ni_los_registros_ni_los_errores_ni_el_mensaje_exponen_la_contrasena(monkeypatch, smtp, caplog):
    secreto = "Sup3r-Secreta-9876"
    configurar(monkeypatch, SMTP_HOST="correo.test", SMTP_USER=CUENTA, SMTP_PASSWORD=secreto)
    smtp.error_login = smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted")
    with caplog.at_level(logging.DEBUG):
        assert notificaciones.entregar("ana@test.com", "Asunto", "Texto") is False
    assert secreto not in caplog.text
    import base64
    assert base64.b64encode(f"\0{CUENTA}\0{secreto}".encode()).decode() not in caplog.text  # AUTH PLAIN
    assert secreto not in notificaciones.explicar_error(smtp.error_login)
    smtp.error_login = None
    assert notificaciones.entregar("ana@test.com", "Asunto", "Texto", "<p>HTML</p>") is True
    assert secreto not in smtp.mensajes[0].as_string()  # la contraseña no viaja en el mensaje
    assert secreto not in repr(notificaciones.cargar_config())


# ==========================================
# Envío en segundo plano
# ==========================================
def test_enviar_no_hace_esperar_a_quien_llama(gmail):
    gmail.espera = threading.Event()
    futuro = ENVIAR("ana@test.com", "Asunto", "Texto")
    try:
        assert isinstance(futuro, Future) and not futuro.done()
        assert gmail.mensajes == []   # el servidor todavía no recibió nada
    finally:
        gmail.espera.set()
    assert futuro.result(timeout=5) is True
    assert len(gmail.mensajes) == 1


def test_enviar_registra_la_cola_y_el_resultado_con_el_mismo_numero(gmail, caplog):
    with caplog.at_level(logging.INFO, logger="barberia.notificaciones"):
        assert ENVIAR("ana@test.com", "Asunto", "Texto").result(timeout=5) is True
    lineas = [r.getMessage() for r in caplog.records]
    en_cola = [l for l in lineas if "en cola «Asunto» para an***@test.com" in l]
    assert len(en_cola) == 1
    numero = en_cola[0].split(":")[0]
    propias = [l for l in lineas if l.startswith(numero + ":")]
    assert propias[0] == en_cola[0] and propias[-1].startswith(numero + ": ACEPTADO")


def test_una_excepcion_escapada_del_hilo_de_envio_queda_registrada(caplog):
    futuro = Future()
    futuro.set_exception(RuntimeError("fallo imprevisto"))
    with caplog.at_level(logging.ERROR, logger="barberia.notificaciones"):
        notificaciones._avisar_si_el_hilo_fallo(futuro)
    assert "error inesperado" in caplog.text and "fallo imprevisto" in caplog.text


def test_la_consola_del_backend_muestra_el_registro_solo_si_nadie_lo_configuro(monkeypatch):
    """uvicorn no configura el registro raíz: sin este manejador no se vería que un correo fue ACEPTADO."""
    manejadores = [h for h in notificaciones.logger.handlers
                   if any(isinstance(f, notificaciones._SoloSinOtroRegistro) for f in h.filters)]
    assert len(manejadores) == 1 and notificaciones.logger.propagate is True
    registro = logging.makeLogRecord({"name": "barberia.notificaciones", "levelno": logging.INFO, "msg": "x"})
    monkeypatch.setattr(logging.getLogger(), "handlers", [])
    assert manejadores[0].filter(registro)
    monkeypatch.setattr(logging.getLogger(), "handlers", [logging.NullHandler()])
    assert not manejadores[0].filter(registro)  # con registro configurado (p. ej. pytest) no se duplica


def test_un_fallo_en_segundo_plano_se_registra_y_no_lanza(gmail, caplog):
    gmail.error_conexion = TimeoutError("timed out")
    with caplog.at_level(logging.ERROR, logger="barberia.notificaciones"):
        assert ENVIAR("ana@test.com", "Asunto", "Texto").result(timeout=5) is False
    assert "No se pudo enviar el correo" in caplog.text


def test_enviar_sin_smtp_registra_en_el_acto_y_no_usa_hilos(caplog):
    with caplog.at_level(logging.WARNING, logger="barberia.notificaciones"):
        assert ENVIAR("ana@test.com", "Asunto", "Texto del correo") is None
    assert "Correo no enviado" in caplog.text


def test_si_el_ejecutor_ya_no_acepta_tareas_se_entrega_en_el_acto(gmail, monkeypatch):
    def cerrado(*args, **kwargs):
        raise RuntimeError("cannot schedule new futures after shutdown")

    monkeypatch.setattr(notificaciones._ejecutor, "submit", cerrado)
    assert ENVIAR("ana@test.com", "Asunto", "Texto") is None
    assert len(gmail.mensajes) == 1


# ==========================================
# Formato
# ==========================================
@pytest.mark.parametrize("minutos, texto", [
    (15, "15 minutos"), (60, "1 hora"), (75, "1 hora 15 minutos"), (120, "2 horas"), (135, "2 horas 15 minutos"),
])
def test_duracion_en_palabras(minutos, texto):
    assert notificaciones._duracion(minutos) == texto


@pytest.mark.parametrize("intervalo, texto", [
    (datetime.timedelta(hours=1), "1 hora"), (datetime.timedelta(hours=12), "12 horas"),
    (datetime.timedelta(minutes=30), "30 minutos"),
])
def test_politicas_en_palabras(intervalo, texto):
    assert notificaciones._horas(intervalo) == texto


# ==========================================
# Contenido de cada correo (con datos reales de la base de pruebas)
# ==========================================
def test_correo_de_confirmacion(client, reloj, h_cliente, cliente, barbero, corte, barba, correos, monkeypatch):
    monkeypatch.setenv("FRONTEND_URL", "https://barberia.test/")
    cita = agendar(client, h_cliente, barbero, [corte, barba], reloj.en(2), "15:00").json()
    assert len(correos) == 1
    correo = correos[0]
    assert correo["para"] == cliente.email
    assert correo["asunto"] == f"Cita confirmada {cita['codigo_reserva']} - BarberShop Pro"
    for contenido in (correo["cuerpo"], correo["html"]):
        for dato in ("Hola Ana Cliente", cita["codigo_reserva"], "Mateo Maestro", "Corte ($20.000)", "Barba ($10.000)",
                     "Miércoles 09/01/2030", "3:00 p. m. a 3:45 p. m.", "45 minutos", "$30.000", "12 horas"):
            assert dato in contenido, dato
    assert "https://barberia.test" in correo["cuerpo"] and 'href="https://barberia.test"' in correo["html"]


def test_correo_de_cancelacion_para_el_cliente_y_para_el_barbero(client, db, reloj, h_cliente, cliente, barbero, corte, correos):
    cita = crear_cita(db, cliente, barbero, corte, reloj.en(2), "10:00")
    client.post(f"/api/citas/{cita.id}/cancelar", headers=h_cliente)
    del_cliente, del_barbero = sorted(correos, key=lambda c: c["para"] != cliente.email)
    assert (del_cliente["para"], del_barbero["para"]) == (cliente.email, barbero.usuario.email)
    for correo in correos:
        assert f"Cita cancelada {cita.codigo_reserva}" in correo["asunto"]
        assert cita.codigo_reserva in correo["cuerpo"] and cita.codigo_reserva in correo["html"]
        assert "Miércoles 09/01/2030" in correo["cuerpo"] and "10:00 a. m." in correo["html"]
    assert "Hola Ana Cliente" in del_cliente["cuerpo"] and "Agendar una nueva cita" in del_cliente["html"]
    assert "Hola Mateo Maestro" in del_barbero["cuerpo"] and "Cliente: Ana Cliente" in del_barbero["cuerpo"]
    assert "Agendar una nueva cita" not in del_barbero["html"]


def test_correo_de_reprogramacion_muestra_el_horario_nuevo_y_el_anterior_aparte(
    client, db, reloj, h_cliente, cliente, barbero, corte, correos
):
    cita = crear_cita(db, cliente, barbero, corte, reloj.en(1), "10:00")
    client.post(f"/api/citas/{cita.id}/reprogramar", headers=h_cliente,
                json={"fecha": reloj.en(3).isoformat(), "hora_inicio": "15:00"})
    assert sorted(c["para"] for c in correos) == sorted([cliente.email, barbero.usuario.email])
    for correo in correos:
        assert f"Cita reprogramada {cita.codigo_reserva}" in correo["asunto"]
        lineas = correo["cuerpo"].splitlines()
        assert "Fecha: Jueves 10/01/2030" in lineas and "Hora: 3:00 p. m. a 3:30 p. m." in lineas  # el nuevo
        assert "Horario anterior (ya no vigente): Martes 08/01/2030, 10:00 a. m." in lineas
    assert "se puede reprogramar una sola vez" in correos[0]["cuerpo"]  # aviso solo para el cliente
    assert "se puede reprogramar una sola vez" not in correos[1]["cuerpo"]


def test_correo_de_baja_del_barbero(client, db, reloj, h_admin, cliente, barbero, corte, correos):
    cita = crear_cita(db, cliente, barbero, corte, reloj.en(2), "10:00")
    client.delete(f"/api/admin/barberos/{barbero.id}", headers=h_admin)
    assert len(correos) == 1 and correos[0]["para"] == cliente.email
    assert correos[0]["asunto"] == f"Tu cita {cita.codigo_reserva} fue cancelada - BarberShop Pro"
    for contenido in (correos[0]["cuerpo"], correos[0]["html"]):
        assert "el barbero ya no atiende" in contenido and "Mateo Maestro" in contenido
    assert "Agendar una nueva cita" in correos[0]["html"]


def test_correo_de_recuperacion_lleva_el_enlace_su_vigencia_y_nunca_la_contrasena(client, correos, cliente):
    client.post("/api/auth/recuperar", json={"email": cliente.email})
    correo = correos[0]
    assert correo["para"] == cliente.email and correo["asunto"] == "Recupera tu contraseña - BarberShop Pro"
    for contenido in (correo["cuerpo"], correo["html"]):
        assert "/restablecer?token=" in contenido and "vence en 1 hora" in contenido and "un solo uso" in contenido
        assert CLAVE not in contenido


def test_el_enlace_se_escapa_en_el_html_y_queda_intacto_en_el_texto(correos):
    usuario = SimpleNamespace(nombre="Ana", email="ana@test.com")
    notificaciones.recuperacion_password(usuario, "https://barberia.test/restablecer?token=abc&x=1")
    assert 'href="https://barberia.test/restablecer?token=abc&amp;x=1"' in correos[0]["html"]
    assert "restablecer?token=abc&x=1" in correos[0]["cuerpo"]


def test_el_html_escapa_los_datos_que_vienen_de_la_base_de_datos(correos):
    cliente = SimpleNamespace(nombre='<script>alert("x")</script> & Cía', email="ana@test.com")
    barbero = SimpleNamespace(nombre="<b>Mateo</b>", email="mateo@test.com")
    cita = SimpleNamespace(
        codigo_reserva="BSP-123456", cliente=cliente, barbero=barbero, fecha=datetime.date(2030, 1, 8),
        hora_inicio=datetime.time(9, 0), hora_fin=datetime.time(9, 30), total=20000,
        servicios=[SimpleNamespace(servicio=SimpleNamespace(nombre="<i>Corte</i>"), precio_aplicado=20000, duracion_minutos=30)],
    )
    notificaciones.confirmacion_cita(cita)
    html = correos[0]["html"]
    assert "<script>" not in html and "<b>Mateo</b>" not in html and "<i>Corte</i>" not in html
    assert "&lt;script&gt;" in html and "&amp; Cía" in html
    assert '<script>alert("x")</script> & Cía' in correos[0]["cuerpo"]  # en texto plano no se escapa


class _Balance(HTMLParser):
    VACIOS = {"meta", "br", "img", "hr", "link", "input"}

    def __init__(self):
        super().__init__()
        self.pila, self.errores = [], []

    def handle_starttag(self, tag, attrs):
        if tag not in self.VACIOS:
            self.pila.append(tag)

    def handle_endtag(self, tag):
        if self.pila and self.pila[-1] == tag:
            self.pila.pop()
        else:
            self.errores.append(tag)


def test_todos_los_correos_comparten_presentacion_y_son_autocontenidos(
    client, db, reloj, h_cliente, h_admin, cliente, otro_cliente, barbero, corte, barba, correos
):
    cita = agendar(client, h_cliente, barbero, [corte, barba], reloj.en(2), "10:00").json()
    client.post(f"/api/citas/{cita['id']}/reprogramar", headers=h_cliente,
                json={"fecha": reloj.en(3).isoformat(), "hora_inicio": "11:00"})
    client.post(f"/api/citas/{cita['id']}/cancelar", headers=h_cliente)
    crear_cita(db, otro_cliente, barbero, corte, reloj.en(4), "10:00")
    client.delete(f"/api/admin/barberos/{barbero.id}", headers=h_admin)
    client.post("/api/auth/recuperar", json={"email": cliente.email})

    assert len(correos) == 7  # 1 confirmación + 2 reprogramación + 2 cancelación + 1 baja + 1 recuperación
    for correo in correos:
        asunto, texto, html = correo["asunto"], correo["cuerpo"], correo["html"]
        assert asunto.endswith(" - BarberShop Pro")
        assert texto.startswith("BARBERSHOP PRO\n") and "Hasta pronto,\nEl equipo de BarberShop Pro" in texto
        assert "\nHola " in texto and "<" not in texto  # texto plano sin etiquetas
        assert '<html lang="es">' in html and 'name="viewport"' in html and f"<title>{asunto}</title>" in html
        assert "Hasta pronto" in html and "BarberShop Pro" in html
        assert not any(marca in html for marca in ("<img", "src=", "<script", "<link", "url("))  # nada externo
        assert CLAVE not in texto and CLAVE not in html
        balance = _Balance()
        balance.feed(html)
        assert balance.errores == [] and balance.pila == []  # etiquetas bien cerradas


# ==========================================
# Integración con services.py: momento del envío y tolerancia a fallos
# ==========================================
def espiar(monkeypatch, consulta):
    """Sustituye el envío por un espía que, en el instante de enviar, consulta la base con una sesión nueva."""
    vistos = []

    def enviar_espia(para, asunto, cuerpo, html=None):
        sesion = database.SessionLocal()
        try:
            vistos.append(consulta(sesion))
        finally:
            sesion.close()

    monkeypatch.setattr(notificaciones, "enviar", enviar_espia)
    return vistos


def test_la_confirmacion_se_envia_cuando_la_cita_ya_esta_guardada(client, reloj, h_cliente, barbero, corte, monkeypatch):
    vistos = espiar(monkeypatch, lambda s: s.query(models.Cita).filter_by(estado="Programada").count())
    assert agendar(client, h_cliente, barbero, corte, reloj.en(1), "10:00").status_code == 201
    assert vistos == [1]


def test_la_cancelacion_se_envia_cuando_el_estado_ya_esta_guardado(client, db, reloj, h_cliente, cliente, barbero, corte, monkeypatch):
    cita = crear_cita(db, cliente, barbero, corte, reloj.en(1), "10:00")
    vistos = espiar(monkeypatch, lambda s: s.get(models.Cita, cita.id).estado)
    assert client.post(f"/api/citas/{cita.id}/cancelar", headers=h_cliente).status_code == 200
    assert vistos == ["Cancelada", "Cancelada"]  # un correo al cliente y otro al barbero


def test_la_reprogramacion_se_envia_cuando_el_nuevo_horario_ya_esta_guardado(
    client, db, reloj, h_cliente, cliente, barbero, corte, monkeypatch
):
    cita = crear_cita(db, cliente, barbero, corte, reloj.en(1), "10:00")
    vistos = espiar(monkeypatch, lambda s: (s.get(models.Cita, cita.id).fecha, s.get(models.Cita, cita.id).hora_inicio))
    r = client.post(f"/api/citas/{cita.id}/reprogramar", headers=h_cliente,
                    json={"fecha": reloj.en(2).isoformat(), "hora_inicio": "15:00"})
    assert r.status_code == 200
    assert vistos == [(reloj.en(2), datetime.time(15, 0))] * 2


def test_la_baja_se_notifica_cuando_las_citas_ya_estan_canceladas(client, db, reloj, h_admin, cliente, barbero, corte, monkeypatch):
    cita = crear_cita(db, cliente, barbero, corte, reloj.en(2), "10:00")
    vistos = espiar(monkeypatch, lambda s: (s.get(models.Cita, cita.id).estado, s.get(models.Barbero, barbero.id).activo))
    assert client.delete(f"/api/admin/barberos/{barbero.id}", headers=h_admin).status_code == 200
    assert vistos == [("Cancelada", False)]


def test_el_enlace_de_recuperacion_se_envia_cuando_el_token_ya_esta_guardado(client, cliente, monkeypatch):
    vistos = espiar(monkeypatch, lambda s: s.query(models.TokenRecuperacion).count())
    assert client.post("/api/auth/recuperar", json={"email": cliente.email}).status_code == 200
    assert vistos == [1]


@pytest.mark.parametrize("paso, error", [
    ("error_conexion", TimeoutError("timed out")),
    ("error_login", smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted")),
    ("error_envio", smtplib.SMTPDataError(550, b"5.4.5 Daily user sending limit exceeded")),
])
def test_un_fallo_de_smtp_no_deshace_ninguna_operacion(
    client, db, reloj, gmail, envio_real, caplog, h_cliente, h_admin, cliente, otro_cliente, barbero, corte, paso, error
):
    setattr(gmail, paso, error)
    with caplog.at_level(logging.ERROR, logger="barberia.notificaciones"):
        agendada = agendar(client, h_cliente, barbero, corte, reloj.en(1), "10:00")
        assert agendada.status_code == 201
        cita_id = agendada.json()["id"]
        r = client.post(f"/api/citas/{cita_id}/reprogramar", headers=h_cliente,
                        json={"fecha": reloj.en(2).isoformat(), "hora_inicio": "15:00"})
        assert r.status_code == 200
        assert client.post(f"/api/citas/{cita_id}/cancelar", headers=h_cliente).status_code == 200
        futura = crear_cita(db, otro_cliente, barbero, corte, reloj.en(3), "10:00")
        assert client.delete(f"/api/admin/barberos/{barbero.id}", headers=h_admin).status_code == 200
        assert client.post("/api/auth/recuperar", json={"email": cliente.email}).status_code == 200

    db.expire_all()
    cita = db.get(models.Cita, cita_id)
    assert (cita.estado, cita.fecha, cita.reprogramada) == ("Cancelada", reloj.en(2), True)
    assert db.get(models.Cita, futura.id).estado == "Cancelada"
    assert db.get(models.Barbero, barbero.id).activo is False
    assert db.query(models.TokenRecuperacion).count() == 1
    assert gmail.mensajes == []
    assert caplog.text.count("No se pudo enviar el correo") == 7  # los 7 correos se intentaron y fallaron sin romper nada


def test_con_smtp_disponible_cada_operacion_envia_sus_correos_por_smtp(
    client, reloj, gmail, envio_real, h_cliente, cliente, barbero, corte
):
    cita_id = agendar(client, h_cliente, barbero, corte, reloj.en(1), "10:00").json()["id"]
    assert [m["To"].addresses[0].addr_spec for m in map(mensaje_recibido, gmail.mensajes)] == [cliente.email]
    client.post(f"/api/citas/{cita_id}/cancelar", headers=h_cliente)
    destinatarios = [mensaje_recibido(m)["To"].addresses[0].addr_spec for m in gmail.mensajes[1:]]
    assert sorted(destinatarios) == sorted([cliente.email, barbero.usuario.email])
    assert all(mensaje_recibido(m).get_content_type() == "multipart/alternative" for m in gmail.mensajes)
    assert all(m["From"].addresses[0].addr_spec == CUENTA for m in map(mensaje_recibido, gmail.mensajes))


def test_solicitar_la_recuperacion_no_espera_al_servidor_de_correo(client, gmail, cliente, monkeypatch):
    """Con un servidor lento la API responde igual de rápido: así tampoco se nota si el correo existe."""
    monkeypatch.setattr(notificaciones, "enviar", ENVIAR)
    gmail.espera = threading.Event()
    try:
        inicio = time.perf_counter()
        assert client.post("/api/auth/recuperar", json={"email": cliente.email}).status_code == 200
        assert time.perf_counter() - inicio < 3  # el servidor simulado tarda hasta 10 s en aceptar el correo
        assert gmail.mensajes == []
    finally:
        gmail.espera.set()
    for _ in range(100):
        if gmail.mensajes:
            break
        time.sleep(0.05)
    assert len(gmail.mensajes) == 1


# ==========================================
# Prueba real de envío por consola (con el doble, sin Gmail)
# ==========================================
@pytest.fixture
def consola(monkeypatch):
    """La consola carga el .env del proyecto; en las pruebas no debe leer el del programador."""
    cargados = []
    monkeypatch.setattr("dotenv.find_dotenv", lambda *args, **kwargs: "")
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: cargados.append(args) or False)
    return cargados


def test_consola_envia_el_correo_de_prueba_y_no_imprime_la_contrasena(gmail, consola, capsys):
    assert notificaciones._probar_desde_consola(["destino@test.com"]) == 0
    salida = capsys.readouterr().out
    assert "Se enviará UN correo de prueba, solo a: destino@test.com" in salida
    assert "smtp.gmail.com:587" in salida and f"Autenticación aceptada para {CUENTA}" in salida
    assert "ACEPTADO" in salida and "Respuesta del servidor: 250 2.0.0 OK 1730000000 a1b2c3 - gsmtp" in salida
    assert "abcdefghijklmnop" not in salida and CLAVE_DE_APLICACION not in salida
    assert "SMTP_PASSWORD    definida (16 letras: formato de contraseña de aplicación)" in salida
    id_mensaje = gmail.mensajes[0]["Message-ID"].strip("<>")
    assert f"in:anywhere rfc822msgid:{id_mensaje}" in salida
    assert len(gmail.mensajes) == 1 and gmail.mensajes[0]["Cc"] is None and gmail.mensajes[0]["Bcc"] is None
    m = mensaje_recibido(gmail.mensajes[0])
    assert m["Subject"] == "Prueba de correo - BarberShop Pro" and m["To"].addresses[0].addr_spec == "destino@test.com"
    assert "hora de Colombia" in cuerpo_de(m, "plain")


def test_consola_explica_los_errores_de_autenticacion(gmail, consola, capsys):
    gmail.error_login = smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted")
    assert notificaciones._probar_desde_consola(["destino@test.com"]) == 1
    salida = capsys.readouterr().out
    assert "FALLÓ en la etapa: autenticación (SMTPAuthenticationError)" in salida and "contraseña de aplicación" in salida
    assert "Respuesta del servidor: 535 5.7.8 Username and Password not accepted" in salida
    assert "ACEPTADO" not in salida and "abcdefghijklmnop" not in salida


def test_consola_indica_que_env_lee_y_que_variables_del_sistema_tienen_prioridad(gmail, consola, capsys, monkeypatch):
    monkeypatch.setattr("dotenv.find_dotenv", lambda *args, **kwargs: "/proyecto/src/backend/.env")
    assert notificaciones._probar_desde_consola(["destino@test.com"]) == 0
    salida = capsys.readouterr().out
    assert "Archivo .env leído: /proyecto/src/backend/.env" in salida
    assert consola == [("/proyecto/src/backend/.env",)]
    # gmail define las variables en el entorno antes de cargar el .env: son las que usaría el backend
    assert "SMTP_HOST ya está definida en las variables de entorno del sistema" in salida


def test_consola_avisa_si_no_hay_env_o_si_windows_lo_guardo_como_env_txt(smtp, consola, capsys, monkeypatch):
    monkeypatch.setattr(notificaciones.os.path, "exists", lambda ruta: ruta.endswith(".env.txt"))
    assert notificaciones._probar_desde_consola(["destino@test.com"]) == 2
    salida = capsys.readouterr().out
    assert "No se encontró ningún archivo .env" in salida and ".env.txt" in salida


def test_consola_avisa_si_la_contrasena_no_parece_de_aplicacion_sin_mostrarla(gmail, consola, capsys, monkeypatch):
    configurar(monkeypatch, SMTP_PASSWORD="MiClaveNormal.2026")
    notificaciones._probar_desde_consola(["destino@test.com"])
    salida = capsys.readouterr().out
    assert "NO tiene el formato de una contraseña de aplicación" in salida and "MiClaveNormal" not in salida


def test_consola_recuerda_que_un_correo_a_si_mismo_puede_quedar_solo_en_enviados(gmail, consola, capsys):
    assert notificaciones._probar_desde_consola([CUENTA]) == 0
    assert "solo en Enviados" in capsys.readouterr().out


def test_consola_avisa_si_gmail_va_a_cambiar_el_remitente(gmail, consola, capsys, monkeypatch):
    configurar(monkeypatch, SMTP_FROM_EMAIL="otra.direccion@gmail.test")
    assert notificaciones._probar_desde_consola(["destino@test.com"]) == 0
    assert "Gmail reemplaza el remitente" in capsys.readouterr().out


@pytest.mark.parametrize("argumentos", [
    [], ["sin-arroba"], ["a@test.com", "b@test.com"], ["a@test.com,b@test.com"], ["a@test.com;b@test.com"],
    ["a@test.com b@test.com"], ["Ana <a@test.com>"],
])
def test_consola_solo_acepta_una_direccion(gmail, consola, capsys, argumentos):
    assert notificaciones._probar_desde_consola(argumentos) == 2
    assert "Uso:" in capsys.readouterr().out
    assert gmail.conexiones == [] and gmail.mensajes == []


def test_consola_sin_smtp_host_o_con_configuracion_invalida_no_intenta_enviar(smtp, consola, capsys, monkeypatch):
    assert notificaciones._probar_desde_consola(["destino@test.com"]) == 2
    assert "SMTP_HOST está vacío" in capsys.readouterr().out
    configurar(monkeypatch, SMTP_HOST="smtp.gmail.com", SMTP_PORT="abc")
    assert notificaciones._probar_desde_consola(["destino@test.com"]) == 2
    assert "SMTP_PORT" in capsys.readouterr().out
    assert smtp.conexiones == []


# ==========================================
# RNF-10: la plantilla de configuración no trae credenciales
# ==========================================
def test_env_example_declara_las_variables_smtp_sin_credenciales():
    import os
    from conftest import BACKEND_DIR
    with open(os.path.join(BACKEND_DIR, ".env.example"), encoding="utf-8") as f:
        lineas = dict(l.split("=", 1) for l in f.read().splitlines() if "=" in l and not l.startswith("#"))
    for variable in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM_EMAIL", "SMTP_FROM_NAME"):
        assert variable in lineas, variable
    assert [lineas[v] for v in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM_EMAIL")] == [""] * 4
    assert "SMTP_FROM" not in lineas  # el nombre antiguo ya no se anuncia (sigue aceptándose en el código)
