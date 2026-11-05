"""Envío de correos (RF-04, RF-07, RF-21 y RF-25).

Usa smtplib de la biblioteca estándar. Si SMTP_HOST no está configurado (entorno de desarrollo o
pruebas), el correo no se envía y el registro lo avisa (sin su contenido, que puede llevar enlaces privados).
Este módulo arma y envía los mensajes (plantillas_correo.py da su presentación); decidir cuándo
enviarlos es trabajo de services.py, que lo hace siempre después de guardar la operación.

Variables de entorno (ver .env.example):
    SMTP_HOST, SMTP_PORT (587 con STARTTLS o 465 con SSL), SMTP_USER, SMTP_PASSWORD,
    SMTP_FROM_EMAIL y SMTP_FROM_NAME. SMTP_FROM sigue funcionando como nombre antiguo de SMTP_FROM_EMAIL.

Envío:
    enviar()   no hace esperar a quien lo llama: la entrega ocurre en un hilo aparte.
    entregar() hace la entrega completa y espera el resultado (la usan el hilo y la prueba de consola).
Un fallo de correo se registra pero nunca se propaga: no debe deshacer una operación ya guardada.

Registro (consola del backend): cada correo lleva un número y se anotan sus etapas (en cola, conexión,
cifrado, autenticación) y el resultado: ACEPTADO con la respuesta del servidor, o el error con la etapa en
que ocurrió. Nunca se registran la contraseña, el contenido del correo ni la dirección completa del
destinatario.

Prueba real de envío (desde src/backend, con el .env configurado):
    python notificaciones.py destinatario@ejemplo.com
"""
import datetime
import logging
import os
import smtplib
import ssl
import sys
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from decimal import Decimal
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import formatdate, getaddresses, make_msgid, parseaddr
from typing import List, Optional, Tuple

import plantillas_correo
import politicas
from plantillas_correo import ContenidoCorreo, NOMBRE_NEGOCIO

logger = logging.getLogger("barberia.notificaciones")


class _SoloSinOtroRegistro(logging.Filter):
    """uvicorn no configura el registro raíz de Python, así que los mensajes INFO de este módulo (correo
    aceptado, etapas del envío) no se verían en la consola. Este manejador los muestra solo en ese caso: si la
    aplicación o pytest configuran el registro, se usa el suyo y no se duplican los mensajes."""

    def filter(self, record: logging.LogRecord) -> bool:
        return not logging.getLogger().handlers


if not any(isinstance(f, _SoloSinOtroRegistro) for h in logger.handlers for f in h.filters):
    _consola = logging.StreamHandler()  # stderr, como los mensajes de uvicorn
    _consola.setFormatter(logging.Formatter("%(asctime)s [correo] %(levelname)s: %(message)s", "%Y-%m-%d %H:%M:%S"))
    _consola.addFilter(_SoloSinOtroRegistro())
    logger.addHandler(_consola)
    if logger.level == logging.NOTSET:
        logger.setLevel(logging.INFO)

TIMEOUT_SEGUNDOS = 10
REMITENTE_POR_DEFECTO = "no-responder@barbershop.pro"
HOSTS_GMAIL = ("smtp.gmail.com", "smtp.googlemail.com")
VARIABLES_SMTP = ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM_EMAIL", "SMTP_FROM_NAME", "SMTP_FROM")


# ==========================================
# Formato (las fechas y horas son las de Colombia, RNF-05)
# ==========================================
_DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


def _fecha(fecha: datetime.date) -> str:
    return fecha.strftime("%d/%m/%Y")


def _fecha_con_dia(fecha: datetime.date) -> str:
    return f"{_DIAS[fecha.weekday()]} {_fecha(fecha)}"


def _hora(hora: datetime.time) -> str:
    sufijo = "a. m." if hora.hour < 12 else "p. m."
    return f"{hora.hour % 12 or 12}:{hora.minute:02d} {sufijo}"


def _dinero(valor: Decimal) -> str:
    return f"${valor:,.0f}".replace(",", ".")


def _duracion(minutos: int) -> str:
    horas, resto = divmod(minutos, 60)
    if not horas:
        return f"{minutos} minutos"
    partes = [f"{horas} {'hora' if horas == 1 else 'horas'}"]
    if resto:
        partes.append(f"{resto} minutos")
    return " ".join(partes)


def _horas(intervalo: datetime.timedelta) -> str:
    """Un intervalo de política en palabras: 12 horas, 1 hora, 30 minutos."""
    minutos = int(intervalo.total_seconds() // 60)
    if minutos % 60 == 0:
        horas = minutos // 60
        return f"{horas} {'hora' if horas == 1 else 'horas'}"
    return f"{minutos} minutos"


def _url_frontend() -> str:
    return os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")


def _datos_cita(cita, con_cliente: bool = False) -> List[Tuple[str, str]]:
    servicios = "\n".join(f"{cs.servicio.nombre} ({_dinero(cs.precio_aplicado)})" for cs in cita.servicios)
    datos = [("Código de reserva", cita.codigo_reserva)]
    if con_cliente:
        datos.append(("Cliente", cita.cliente.nombre))
    datos += [
        ("Barbero", cita.barbero.nombre),
        ("Servicios", servicios),
        ("Fecha", _fecha_con_dia(cita.fecha)),
        ("Hora", f"{_hora(cita.hora_inicio)} a {_hora(cita.hora_fin)}"),
        ("Duración", _duracion(sum(cs.duracion_minutos for cs in cita.servicios))),
        ("Total a pagar en el local", _dinero(cita.total)),
    ]
    return datos


# ==========================================
# Configuración SMTP
# ==========================================
class ConfiguracionSMTPError(ValueError):
    """Variables SMTP incompletas o inválidas. El mensaje nombra la variable, nunca su valor."""


@dataclass(frozen=True)
class ConfigSMTP:
    host: str
    puerto: int
    usuario: str
    password: str = field(repr=False)  # fuera de repr(): así no puede aparecer en un registro por accidente
    remitente_correo: str
    remitente_nombre: str


def _variable(nombre: str) -> str:
    return os.getenv(nombre, "").strip()


def cargar_config() -> Optional[ConfigSMTP]:
    """Lee las variables SMTP. Devuelve None si SMTP_HOST está vacío (modo desarrollo: solo se registra)."""
    host = _variable("SMTP_HOST")
    if not host:
        return None
    try:
        puerto = int(_variable("SMTP_PORT") or "587")
    except ValueError:
        puerto = 0
    if not 1 <= puerto <= 65535:
        raise ConfiguracionSMTPError("SMTP_PORT debe ser un número de puerto válido (587 con STARTTLS o 465 con SSL).")

    usuario = _variable("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD", "")
    if host.lower() in HOSTS_GMAIL:
        # Google muestra la contraseña de aplicación en grupos de cuatro letras separados por espacios
        password = "".join(password.split())
    if bool(usuario) != bool(password):
        faltante = "SMTP_PASSWORD" if usuario else "SMTP_USER"
        raise ConfiguracionSMTPError(f"Falta {faltante}: SMTP_USER y SMTP_PASSWORD deben definirse juntos.")

    # SMTP_FROM es el nombre que usaba la versión anterior de SMTP_FROM_EMAIL
    nombre, correo = parseaddr(_variable("SMTP_FROM_EMAIL") or _variable("SMTP_FROM") or usuario or REMITENTE_POR_DEFECTO)
    if "@" not in correo:
        raise ConfiguracionSMTPError("SMTP_FROM_EMAIL no es una dirección de correo válida.")
    return ConfigSMTP(
        host=host, puerto=puerto, usuario=usuario, password=password,
        remitente_correo=correo, remitente_nombre=_variable("SMTP_FROM_NAME") or nombre or NOMBRE_NEGOCIO,
    )


# ==========================================
# Envío
# ==========================================
def construir_mensaje(config: ConfigSMTP, destinatario: str, asunto: str, cuerpo: str, html: Optional[str] = None) -> EmailMessage:
    """Mensaje de texto plano o, si hay HTML, multipart/alternative con las dos versiones (UTF-8)."""
    if not _es_direccion_unica(destinatario):
        raise ValueError("El destinatario debe ser una sola dirección de correo.")
    mensaje = EmailMessage()
    mensaje["From"] = Address(config.remitente_nombre, addr_spec=config.remitente_correo)
    mensaje["To"] = destinatario
    mensaje["Subject"] = asunto
    mensaje["Date"] = formatdate(localtime=True)
    mensaje["Message-ID"] = make_msgid(domain=config.remitente_correo.rpartition("@")[2])
    mensaje["Auto-Submitted"] = "auto-generated"  # RFC 3834: evita que las respuestas automáticas contesten
    mensaje.set_content(cuerpo)
    if html:
        mensaje.add_alternative(html, subtype="html")
    return mensaje


def _es_direccion_unica(texto: str) -> bool:
    """Una sola dirección, sin nombre ni separadores: 'a@x.com,b@y.com' enviaría a dos personas."""
    direcciones = getaddresses([texto])
    return (
        len(direcciones) == 1 and direcciones[0][1] == texto.strip() and texto.count("@") == 1
        and not any(c in texto for c in ",;<>\r\n\t ") and "." in texto.rpartition("@")[2]
    )


def ocultar_correo(correo: str) -> str:
    """Dirección abreviada para el registro, que puede terminar copiado en otro sitio: 'ana@x.com' -> 'an***@x.com'."""
    local, arroba, dominio = correo.partition("@")
    return f"{local[:2]}***@{dominio}" if arroba else "***"


def _texto_respuesta(respuesta) -> str:
    """'235 2.7.0 Accepted' a partir de lo que devuelve smtplib: (código, bytes)."""
    if not isinstance(respuesta, tuple) or len(respuesta) != 2:
        return ""
    codigo, texto = respuesta
    if isinstance(texto, bytes):
        texto = texto.decode("utf-8", "replace")
    return " ".join(f"{codigo} {texto}".split())[:240]


def respuesta_del_error(error: BaseException, config: Optional[ConfigSMTP] = None) -> str:
    """Respuesta del servidor que acompaña al error (p. ej. '535 5.7.8 Username and Password not accepted...').
    Gmail no repite las credenciales, pero por si otro servidor lo hiciera se tapan usuario y contraseña."""
    if isinstance(error, smtplib.SMTPRecipientsRefused) and error.recipients:
        respuesta = next(iter(error.recipients.values()))
    elif isinstance(getattr(error, "smtp_code", None), int):
        respuesta = (error.smtp_code, getattr(error, "smtp_error", b""))
    else:
        return ""
    texto = _texto_respuesta(respuesta)
    if config is not None:
        for secreto in (config.password, config.usuario):
            if secreto:
                texto = texto.replace(secreto, "****")
    return texto


def _capturar_respuesta_al_mensaje(servidor) -> dict:
    """smtplib comprueba que el servidor responda 250 al mensaje pero no devuelve el texto de esa respuesta,
    que es la prueba de que lo aceptó (Gmail incluye su identificador interno y '- gsmtp'). Se guarda aquí."""
    capturada = {}
    data = getattr(servidor, "data", None)
    if callable(data):
        def data_con_respuesta(mensaje):
            respuesta = data(mensaje)
            capturada["texto"] = _texto_respuesta(respuesta)
            return respuesta
        servidor.data = data_con_respuesta
    return capturada


def _version_tls(servidor) -> str:
    version = getattr(getattr(servidor, "sock", None), "version", None)
    return (version() if callable(version) else None) or "TLS"


def _transmitir(config: ConfigSMTP, mensaje: EmailMessage, avisar=None) -> str:
    """Conexión cifrada con verificación del certificado del servidor y envío.

    `avisar(texto)` recibe cada etapa superada (nunca datos secretos). Devuelve la respuesta del servidor al
    mensaje. Si algo falla, lanza el error original con el atributo `etapa_smtp` (conexión, cifrado,
    autenticación o envío) para saber hasta dónde llegó."""
    avisar = avisar or (lambda texto: None)
    etapa = "conexión"
    try:
        # smtplib, sin contexto, cifra pero no comprueba el certificado; con el contexto por defecto sí.
        contexto = ssl.create_default_context()
        avisar(f"Conectando con {config.host}:{config.puerto} ({'SSL' if config.puerto == 465 else 'STARTTLS'})...")
        if config.puerto == 465:
            servidor = smtplib.SMTP_SSL(config.host, config.puerto, timeout=TIMEOUT_SEGUNDOS, context=contexto)
        else:
            servidor = smtplib.SMTP(config.host, config.puerto, timeout=TIMEOUT_SEGUNDOS)
        with servidor:
            etapa = "cifrado"
            if config.puerto != 465:
                servidor.starttls(context=contexto)
            avisar(f"Conexión cifrada ({_version_tls(servidor)}); certificado de {config.host} verificado.")
            if config.usuario:
                etapa = "autenticación"
                respuesta = _texto_respuesta(servidor.login(config.usuario, config.password))
                avisar(f"Autenticación aceptada para {config.usuario}" + (f" ({respuesta})." if respuesta else "."))
            etapa = "envío"
            capturada = _capturar_respuesta_al_mensaje(servidor)
            servidor.send_message(mensaje)
            return capturada.get("texto") or "250 (el servidor aceptó el mensaje)"
    except Exception as error:
        try:
            error.etapa_smtp = etapa
        except AttributeError:
            pass
        raise


def explicar_error(error: BaseException) -> str:
    """Causa probable y qué revisar, en español. Solo usa el tipo de error y el código, nunca credenciales."""
    if isinstance(error, ConfiguracionSMTPError):
        return str(error)
    if isinstance(error, smtplib.SMTPAuthenticationError):
        if error.smtp_code == 534 or b"5.7.9" in (error.smtp_error or b""):
            return (
                f"Gmail exige una contraseña de aplicación (código {error.smtp_code}): SMTP_PASSWORD parece ser la "
                "contraseña normal de la cuenta. Crea una contraseña de aplicación en la cuenta de SMTP_USER "
                "(requiere verificación en 2 pasos) y ponla en SMTP_PASSWORD."
            )
        return (
            f"el servidor rechazó el usuario o la contraseña (código {error.smtp_code}). Con Gmail, SMTP_USER debe ser "
            "la dirección completa y SMTP_PASSWORD una contraseña de aplicación de 16 caracteres "
            "(requiere verificación en 2 pasos), no la contraseña normal de la cuenta. La contraseña de aplicación "
            "debe haberse creado en esa misma cuenta y seguir activa: Google las revoca todas si cambias la "
            "contraseña de la cuenta."
        )
    if isinstance(error, smtplib.SMTPNotSupportedError):
        return "el servidor no ofrece STARTTLS o autenticación en ese puerto. Usa 587 (STARTTLS) o 465 (SSL)."
    if isinstance(error, smtplib.SMTPSenderRefused):
        return "el servidor rechazó el remitente. Con Gmail, SMTP_FROM_EMAIL debe ser la misma cuenta de SMTP_USER."
    if isinstance(error, smtplib.SMTPRecipientsRefused):
        return "el servidor rechazó la dirección del destinatario."
    if isinstance(error, smtplib.SMTPDataError):
        return (
            f"el servidor rechazó el mensaje (código {error.smtp_code}). Puede ser el límite diario de envíos de la "
            "cuenta (500 mensajes en Gmail personal) o un bloqueo por contenido."
        )
    if isinstance(error, ssl.SSLCertVerificationError):
        return (
            "no se pudo verificar el certificado del servidor. Revisa la fecha y hora del equipo y si un antivirus, "
            "proxy o red corporativa intercepta las conexiones cifradas."
        )
    if isinstance(error, ssl.SSLError):
        return "falló el cifrado de la conexión. El puerto 465 usa SSL directo y el 587 usa STARTTLS."
    if isinstance(error, TimeoutError):
        return "el servidor no respondió a tiempo. Revisa la conexión a internet y que el firewall permita salir por ese puerto."
    if isinstance(error, ValueError):
        return f"los datos del mensaje no son válidos: {error}"
    if isinstance(error, (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, OSError)):
        return (
            "no se pudo conectar con el servidor de correo. Revisa SMTP_HOST y SMTP_PORT, la conexión a internet "
            "y que el firewall no bloquee el puerto."
        )
    return f"error inesperado ({type(error).__name__})."


_ERRORES_CONOCIDOS = (smtplib.SMTPException, OSError, ValueError)  # su explicación basta; sin traza
_numeracion = threading.Lock()
_ultimo_numero = 0


def _siguiente_numero() -> int:
    global _ultimo_numero
    with _numeracion:
        _ultimo_numero += 1
        return _ultimo_numero


def entregar(destinatario: str, asunto: str, cuerpo: str, html: Optional[str] = None, numero: Optional[int] = None) -> bool:
    """Envía un correo y espera el resultado. Devuelve True si el servidor lo aceptó; nunca lanza excepciones.

    Deja en el registro cada etapa y el resultado con el número del correo (sin contraseña, sin contenido y con
    la dirección del destinatario abreviada)."""
    etiqueta = f"Correo #{numero or _siguiente_numero()}"
    para = ocultar_correo(destinatario)
    try:
        config = cargar_config()
    except ConfiguracionSMTPError as error:
        logger.error("%s: No se pudo enviar el correo «%s» a %s: configuración inválida. %s", etiqueta, asunto, para, error)
        return False
    if config is None:
        logger.warning(
            "%s: Correo no enviado «%s» para %s: SMTP_HOST no está configurado en el entorno del backend. Si ya lo "
            "pusiste en src/backend/.env, reinicia el backend: el archivo solo se lee al arrancar.", etiqueta, asunto, para,
        )
        return False
    inicio = time.monotonic()
    try:
        respuesta = _transmitir(
            config, construir_mensaje(config, destinatario, asunto, cuerpo, html),
            avisar=lambda texto: logger.info("%s: %s", etiqueta, texto),
        )
    except Exception as error:
        detalle = respuesta_del_error(error, config)
        logger.error(
            "%s: No se pudo enviar el correo «%s» a %s. Falló en la etapa: %s (%s%s). %s",
            etiqueta, asunto, para, getattr(error, "etapa_smtp", "preparación"), type(error).__name__,
            f"; respuesta del servidor: {detalle}" if detalle else "", explicar_error(error),
            exc_info=not isinstance(error, _ERRORES_CONOCIDOS),
        )
        return False
    logger.info("%s: ACEPTADO por %s en %.1f s: «%s» para %s. Respuesta del servidor: %s",
                etiqueta, config.host, time.monotonic() - inicio, asunto, para, respuesta)
    return True


# Conectarse a Gmail, cifrar, autenticar y enviar tarda uno o dos segundos, y hasta 10 si el servidor no
# responde. Se hace en un hilo aparte para que la respuesta de la API no espere al correo (una baja de
# barbero con varias citas enviaría varios seguidos) y para que solicitar la recuperación de contraseña
# tarde lo mismo exista o no el correo en el sistema. Son pocos hilos para no abrir muchas conexiones a la vez.
_ejecutor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="correo")


def _avisar_si_el_hilo_fallo(futuro: Future) -> None:
    # entregar() no lanza excepciones; si aun así una escapara, el Future la guardaría sin que nadie la viera.
    if not futuro.cancelled() and futuro.exception() is not None:
        logger.error("El envío en segundo plano terminó con un error inesperado.", exc_info=futuro.exception())


def enviar(destinatario: str, asunto: str, cuerpo: str, html: Optional[str] = None) -> Optional[Future]:
    """Entrega el correo sin hacer esperar a quien lo llama. `cuerpo` es el texto plano; `html` es opcional.

    Devuelve el Future de la entrega (su resultado es True o False), o None si no hay SMTP configurado:
    en ese caso solo se registra que no se envió, lo cual es inmediato."""
    if not _variable("SMTP_HOST"):
        entregar(destinatario, asunto, cuerpo, html)
        return None
    numero = _siguiente_numero()
    logger.info("Correo #%d: en cola «%s» para %s (se envía en segundo plano).", numero, asunto, ocultar_correo(destinatario))
    try:
        futuro = _ejecutor.submit(entregar, destinatario, asunto, cuerpo, html, numero)
    except RuntimeError:  # el intérprete se está cerrando y ya no acepta tareas nuevas
        entregar(destinatario, asunto, cuerpo, html, numero)
        return None
    futuro.add_done_callback(_avisar_si_el_hilo_fallo)
    return futuro


def _enviar_contenido(destinatario: str, contenido: ContenidoCorreo) -> None:
    enviar(destinatario, contenido.asunto, plantillas_correo.a_texto(contenido), plantillas_correo.a_html(contenido))


# ==========================================
# Mensajes
# ==========================================
def recuperacion_password(usuario, enlace: str) -> None:
    # RNF-01 (CP-RNF01-2): el correo lleva solo el enlace, nunca la contraseña
    vigencia = _horas(politicas.VIGENCIA_ENLACE_RECUPERACION)
    _enviar_contenido(usuario.email, ContenidoCorreo(
        asunto=f"Recupera tu contraseña - {NOMBRE_NEGOCIO}",
        titulo="Recupera tu contraseña",
        saludo=f"Hola {usuario.nombre},",
        parrafos=[
            f"Recibimos una solicitud para cambiar la contraseña de tu cuenta en {NOMBRE_NEGOCIO}.",
            f"Para elegir una nueva, usa el siguiente enlace. Es de un solo uso y vence en {vigencia}.",
        ],
        boton=("Restablecer contraseña", enlace),
        avisos=[
            "Si no solicitaste este cambio, ignora este mensaje: tu contraseña actual seguirá funcionando.",
            "Por tu seguridad, no compartas este enlace con nadie.",
        ],
        resumen=f"Enlace para restablecer tu contraseña. Vence en {vigencia}.",
    ))


def confirmacion_cita(cita) -> None:
    anticipacion = _horas(politicas.ANTICIPACION_MINIMA)
    _enviar_contenido(cita.cliente.email, ContenidoCorreo(
        asunto=f"Cita confirmada {cita.codigo_reserva} - {NOMBRE_NEGOCIO}",
        titulo="Tu cita está confirmada",
        saludo=f"Hola {cita.cliente.nombre},",
        parrafos=["Tu cita quedó agendada. Estos son los datos de tu reserva:"],
        datos=_datos_cita(cita),
        titulo_datos="Detalle de tu cita",
        boton=(f"Abrir {NOMBRE_NEGOCIO}", _url_frontend()),
        avisos=[
            f"Puedes cancelar tu cita o reprogramarla una sola vez hasta {anticipacion} antes de su hora de inicio.",
        ],
        resumen=f"Tu cita del {_fecha(cita.fecha)} a las {_hora(cita.hora_inicio)} quedó confirmada.",
    ))


def cita_cancelada(cita) -> None:
    """Al cliente y al barbero (RF-25)."""
    resumen = f"La cita {cita.codigo_reserva} del {_fecha(cita.fecha)} fue cancelada."
    _enviar_contenido(cita.cliente.email, ContenidoCorreo(
        asunto=f"Cita cancelada {cita.codigo_reserva} - {NOMBRE_NEGOCIO}",
        titulo="Tu cita fue cancelada",
        saludo=f"Hola {cita.cliente.nombre},",
        parrafos=["La siguiente cita fue cancelada y el horario quedó libre."],
        datos=_datos_cita(cita),
        titulo_datos="Cita cancelada",
        boton=("Agendar una nueva cita", _url_frontend()),
        resumen=resumen,
    ))
    _enviar_contenido(cita.barbero.email, ContenidoCorreo(
        asunto=f"Cita cancelada {cita.codigo_reserva} - {NOMBRE_NEGOCIO}",
        titulo="Una cita de tu agenda fue cancelada",
        saludo=f"Hola {cita.barbero.nombre},",
        parrafos=["La siguiente cita fue cancelada y el horario quedó libre en tu agenda."],
        datos=_datos_cita(cita, con_cliente=True),
        titulo_datos="Cita cancelada",
        resumen=resumen,
    ))


def cita_reprogramada(cita, fecha_anterior: datetime.date, hora_anterior: datetime.time) -> None:
    """Al cliente y al barbero (RF-25). El detalle es el del nuevo horario; el anterior se indica aparte."""
    anterior = ("Horario anterior (ya no vigente)", f"{_fecha_con_dia(fecha_anterior)}, {_hora(hora_anterior)}")
    resumen = f"La cita {cita.codigo_reserva} pasó al {_fecha(cita.fecha)} a las {_hora(cita.hora_inicio)}."
    _enviar_contenido(cita.cliente.email, ContenidoCorreo(
        asunto=f"Cita reprogramada {cita.codigo_reserva} - {NOMBRE_NEGOCIO}",
        titulo="Tu cita fue reprogramada",
        saludo=f"Hola {cita.cliente.nombre},",
        parrafos=[f"Tu cita {cita.codigo_reserva} cambió de horario. Este es tu nuevo horario:"],
        datos=_datos_cita(cita) + [anterior],
        titulo_datos="Nuevo horario de tu cita",
        boton=(f"Abrir {NOMBRE_NEGOCIO}", _url_frontend()),
        avisos=[
            "Cada cita se puede reprogramar una sola vez. Si necesitas cambiarla de nuevo, "
            f"cancélala con al menos {_horas(politicas.ANTICIPACION_MINIMA)} de anticipación y agenda otra.",
        ],
        resumen=resumen,
    ))
    _enviar_contenido(cita.barbero.email, ContenidoCorreo(
        asunto=f"Cita reprogramada {cita.codigo_reserva} - {NOMBRE_NEGOCIO}",
        titulo="Una cita de tu agenda fue reprogramada",
        saludo=f"Hola {cita.barbero.nombre},",
        parrafos=[f"La cita {cita.codigo_reserva} cambió de horario. El horario anterior quedó libre."],
        datos=_datos_cita(cita, con_cliente=True) + [anterior],
        titulo_datos="Nuevo horario de la cita",
        resumen=resumen,
    ))


def cita_cancelada_por_baja_del_barbero(cita) -> None:
    """Al cliente cuya cita futura se cancela porque el barbero fue eliminado (RF-07, PN-08)."""
    _enviar_contenido(cita.cliente.email, ContenidoCorreo(
        asunto=f"Tu cita {cita.codigo_reserva} fue cancelada - {NOMBRE_NEGOCIO}",
        titulo="Tu cita fue cancelada",
        saludo=f"Hola {cita.cliente.nombre},",
        parrafos=[
            "Lamentamos informarte que tu cita fue cancelada porque el barbero ya no atiende en la barbería.",
            "Puedes agendar una nueva cita con otro barbero cuando quieras.",
        ],
        datos=_datos_cita(cita),
        titulo_datos="Cita cancelada",
        boton=("Agendar una nueva cita", _url_frontend()),
        resumen=f"Tu cita {cita.codigo_reserva} fue cancelada porque el barbero ya no atiende.",
    ))


# ==========================================
# Prueba real de envío: python notificaciones.py destinatario@ejemplo.com (una sola dirección)
# ==========================================
def _correo_de_prueba(config: ConfigSMTP) -> ContenidoCorreo:
    colombia = datetime.timezone(datetime.timedelta(hours=-5))  # RNF-05: UTC-5, sin horario de verano
    ahora = datetime.datetime.now(colombia)
    return ContenidoCorreo(
        asunto=f"Prueba de correo - {NOMBRE_NEGOCIO}",
        titulo="Prueba de envío de correo",
        saludo="Hola,",
        parrafos=[
            f"Si estás leyendo este mensaje, {NOMBRE_NEGOCIO} puede enviar correos con la configuración SMTP actual.",
            "No necesitas hacer nada con él.",
        ],
        datos=[
            ("Servidor", f"{config.host}:{config.puerto}"),
            ("Remitente", f"{config.remitente_nombre} <{config.remitente_correo}>"),
            ("Enviado el", f"{_fecha(ahora.date())}, {_hora(ahora.time())} (hora de Colombia)"),
        ],
        titulo_datos="Datos de la prueba",
    )


def _cargar_env() -> Tuple[Optional[str], List[str]]:
    """Carga el mismo .env que el backend: database.py llama a load_dotenv() desde esta carpeta, que busca
    .env aquí y, si no lo hay, en las carpetas superiores. Devuelve la ruta y las variables SMTP que ya estaban
    en el entorno del sistema: load_dotenv no las sustituye, así que tienen prioridad sobre el .env."""
    previas = [v for v in VARIABLES_SMTP if v in os.environ]
    try:
        from dotenv import find_dotenv, load_dotenv
    except ImportError:
        return None, previas
    ruta = find_dotenv()
    if ruta:
        load_dotenv(ruta)
    return ruta or None, previas


def _estado_password(config: ConfigSMTP) -> str:
    """Si la contraseña parece una contraseña de aplicación de Google, sin mostrarla ni dar pistas de su valor."""
    if not config.password:
        return "(sin autenticación)"
    if config.host.lower() not in HOSTS_GMAIL:
        return "definida"
    if len(config.password) == 16 and config.password.isascii() and config.password.isalpha():
        return "definida (16 letras: formato de contraseña de aplicación)"
    return ("definida, pero NO tiene el formato de una contraseña de aplicación de Google (16 letras). "
            "Revisa que no sea la contraseña normal de la cuenta, que esté completa y sin comillas.")


def _probar_desde_consola(argumentos: List[str]) -> int:
    """Envía UN correo de prueba, solo a la dirección indicada, con la configuración real del .env, y muestra
    cada etapa. No usa la base de datos ni los flujos de la aplicación. Códigos de salida:
    0 el servidor aceptó el mensaje, 1 falló el envío, 2 faltan datos o la configuración es inválida."""
    if len(argumentos) != 1 or not _es_direccion_unica(argumentos[0]):
        print("Uso: python notificaciones.py destinatario@ejemplo.com   (una sola dirección)")
        return 2
    destinatario = argumentos[0].strip()
    ruta_env, previas = _cargar_env()

    print("Prueba de envío real de BarberShop Pro. No usa la base de datos ni la aplicación.")
    print(f"Se enviará UN correo de prueba, solo a: {destinatario}\n")
    if ruta_env:
        print(f"Archivo .env leído: {ruta_env}")
    else:
        print("No se encontró ningún archivo .env (debe estar en src/backend y llamarse exactamente .env).")
    if ruta_env is None or os.path.dirname(os.path.abspath(ruta_env)) != os.path.dirname(os.path.abspath(__file__)):
        if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env.txt")):
            print("  Aviso: hay un archivo .env.txt en src/backend; Windows pudo haber añadido la extensión. Renómbralo a .env.")
    for variable in previas:
        print(f"  Aviso: {variable} ya está definida en las variables de entorno del sistema y tiene prioridad sobre el .env.")

    try:
        config = cargar_config()
    except ConfiguracionSMTPError as error:
        print(f"\nConfiguración inválida: {error}")
        return 2
    if config is None:
        print("\nSMTP_HOST está vacío: sin servidor de correo no hay nada que probar. Completa el archivo .env (ver .env.example).")
        return 2

    print("\nConfiguración SMTP que usará el backend:")
    print(f"  SMTP_HOST        {config.host}")
    print(f"  SMTP_PORT        {config.puerto} ({'SSL' if config.puerto == 465 else 'STARTTLS'})")
    print(f"  SMTP_USER        {config.usuario or '(sin autenticación)'}")
    print(f"  SMTP_PASSWORD    {_estado_password(config)}")
    print(f"  Remitente        {config.remitente_nombre} <{config.remitente_correo}>  (SMTP_FROM_NAME y SMTP_FROM_EMAIL)")
    if config.host.lower() in HOSTS_GMAIL and config.usuario and config.remitente_correo.lower() != config.usuario.lower():
        print("  Aviso: Gmail reemplaza el remitente por la cuenta autenticada; SMTP_FROM_EMAIL debería ser igual a SMTP_USER.")

    contenido = _correo_de_prueba(config)
    mensaje = construir_mensaje(
        config, destinatario, contenido.asunto, plantillas_correo.a_texto(contenido), plantillas_correo.a_html(contenido),
    )
    print("\nEnvío:")
    try:
        respuesta = _transmitir(config, mensaje, avisar=lambda texto: print(f"  {texto}"))
    except Exception as error:
        detalle = respuesta_del_error(error, config)
        print(f"\nFALLÓ en la etapa: {getattr(error, 'etapa_smtp', 'preparación')} ({type(error).__name__}).")
        if detalle:
            print(f"  Respuesta del servidor: {detalle}")
        print(f"  Qué revisar: {explicar_error(error)}")
        return 1

    id_mensaje = mensaje["Message-ID"].strip("<>")
    print(f"\nACEPTADO: el servidor aceptó el mensaje.\n  Respuesta del servidor: {respuesta}")
    print(f"  Message-ID: {id_mensaje}")
    print("\nCómo comprobar que llegó:")
    print(f"  1. Abre el correo de {destinatario} y busca: in:anywhere rfc822msgid:{id_mensaje}")
    print(f"     (o el asunto \"{contenido.asunto}\"). in:anywhere incluye Spam y Papelera.")
    if config.usuario and destinatario.lower() == config.usuario.lower():
        print("  2. Como el destinatario es la misma cuenta que envía, Gmail puede guardarlo solo en Enviados o en")
        print("     Todos, sin mostrarlo en Recibidos. La búsqueda anterior lo encuentra igual.")
    else:
        print(f"  2. En la cuenta {config.usuario or config.remitente_correo}, la carpeta Enviados debería tener una copia.")
    print("  Aceptado por el servidor no garantiza la entrega: si no aparece en unos minutos, revisa Spam y el")
    print("  mensaje de rebote que Gmail enviaría a la cuenta remitente.")
    return 0


if __name__ == "__main__":
    sys.exit(_probar_desde_consola(sys.argv[1:]))
