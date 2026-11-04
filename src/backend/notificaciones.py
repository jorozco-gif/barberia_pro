"""Envío de correos (RF-04, RF-07, RF-21 y RF-25).

Usa smtplib de la biblioteca estándar. Si SMTP_HOST no está configurado (entorno de desarrollo o
pruebas), el correo no se envía: se escribe en el registro del servidor para poder ver su contenido.
Este módulo arma y envía los mensajes (plantillas_correo.py da su presentación); decidir cuándo
enviarlos es trabajo de services.py, que lo hace siempre después de guardar la operación.

Variables de entorno (ver .env.example):
    SMTP_HOST, SMTP_PORT (587 con STARTTLS o 465 con SSL), SMTP_USER, SMTP_PASSWORD,
    SMTP_FROM_EMAIL y SMTP_FROM_NAME. SMTP_FROM sigue funcionando como nombre antiguo de SMTP_FROM_EMAIL.

Envío:
    enviar()   no hace esperar a quien lo llama: la entrega ocurre en un hilo aparte.
    entregar() hace la entrega completa y espera el resultado (la usan el hilo y la prueba de consola).
Un fallo de correo se registra pero nunca se propaga: no debe deshacer una operación ya guardada.

Prueba real de envío (desde src/backend, con el .env configurado):
    python notificaciones.py destinatario@ejemplo.com
"""
import datetime
import logging
import os
import smtplib
import ssl
import sys
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from decimal import Decimal
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr
from typing import List, Optional, Tuple

import plantillas_correo
import politicas
from plantillas_correo import ContenidoCorreo, NOMBRE_NEGOCIO

logger = logging.getLogger("barberia.notificaciones")

TIMEOUT_SEGUNDOS = 10
REMITENTE_POR_DEFECTO = "no-responder@barbershop.pro"
HOSTS_GMAIL = ("smtp.gmail.com", "smtp.googlemail.com")


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


def _transmitir(config: ConfigSMTP, mensaje: EmailMessage) -> None:
    """Conexión cifrada con verificación del certificado del servidor y envío. Lanza el error que ocurra."""
    # smtplib, sin contexto, cifra pero no comprueba el certificado; con el contexto por defecto sí.
    contexto = ssl.create_default_context()
    if config.puerto == 465:
        servidor = smtplib.SMTP_SSL(config.host, config.puerto, timeout=TIMEOUT_SEGUNDOS, context=contexto)
    else:
        servidor = smtplib.SMTP(config.host, config.puerto, timeout=TIMEOUT_SEGUNDOS)
    with servidor:
        if config.puerto != 465:
            servidor.starttls(context=contexto)
        if config.usuario:
            servidor.login(config.usuario, config.password)
        servidor.send_message(mensaje)


def explicar_error(error: BaseException) -> str:
    """Causa probable y qué revisar, en español. Solo usa el tipo de error y el código, nunca credenciales."""
    if isinstance(error, ConfiguracionSMTPError):
        return str(error)
    if isinstance(error, smtplib.SMTPAuthenticationError):
        return (
            f"el servidor rechazó el usuario o la contraseña (código {error.smtp_code}). Con Gmail, SMTP_USER debe ser "
            "la dirección completa y SMTP_PASSWORD una contraseña de aplicación de 16 caracteres "
            "(requiere verificación en 2 pasos), no la contraseña normal de la cuenta."
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
    if isinstance(error, (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, OSError)):
        return (
            "no se pudo conectar con el servidor de correo. Revisa SMTP_HOST y SMTP_PORT, la conexión a internet "
            "y que el firewall no bloquee el puerto."
        )
    return f"error inesperado ({type(error).__name__})."


def entregar(destinatario: str, asunto: str, cuerpo: str, html: Optional[str] = None) -> bool:
    """Envía un correo y espera el resultado. Devuelve True si el servidor lo aceptó; nunca lanza excepciones."""
    try:
        config = cargar_config()
    except ConfiguracionSMTPError as error:
        logger.error("Configuración de correo inválida: %s Correo '%s' a %s no enviado.", error, asunto, destinatario)
        return False
    if config is None:
        logger.warning("SMTP_HOST no está configurado. Correo no enviado.\nPara: %s\nAsunto: %s\n%s",
                       destinatario, asunto, cuerpo)
        return False
    try:
        _transmitir(config, construir_mensaje(config, destinatario, asunto, cuerpo, html))
    except Exception as error:
        logger.error("No se pudo enviar el correo '%s' a %s: %s", asunto, destinatario, explicar_error(error),
                     exc_info=True)
        return False
    logger.info("Correo '%s' enviado a %s.", asunto, destinatario)
    return True


# Conectarse a Gmail, cifrar, autenticar y enviar tarda uno o dos segundos, y hasta 10 si el servidor no
# responde. Se hace en un hilo aparte para que la respuesta de la API no espere al correo (una baja de
# barbero con varias citas enviaría varios seguidos) y para que solicitar la recuperación de contraseña
# tarde lo mismo exista o no el correo en el sistema. Son pocos hilos para no abrir muchas conexiones a la vez.
_ejecutor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="correo")


def enviar(destinatario: str, asunto: str, cuerpo: str, html: Optional[str] = None) -> Optional[Future]:
    """Entrega el correo sin hacer esperar a quien lo llama. `cuerpo` es el texto plano; `html` es opcional.

    Devuelve el Future de la entrega (su resultado es True o False), o None si no hay SMTP configurado:
    en ese caso solo se registra el contenido, lo cual es inmediato."""
    if not _variable("SMTP_HOST"):
        entregar(destinatario, asunto, cuerpo, html)
        return None
    try:
        return _ejecutor.submit(entregar, destinatario, asunto, cuerpo, html)
    except RuntimeError:  # el intérprete se está cerrando y ya no acepta tareas nuevas
        entregar(destinatario, asunto, cuerpo, html)
        return None


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
# Prueba real de envío: python notificaciones.py destinatario@ejemplo.com
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


def _probar_desde_consola(argumentos: List[str]) -> int:
    """Envía un correo de prueba con la configuración real y explica el resultado. Códigos de salida:
    0 el servidor aceptó el mensaje, 1 falló el envío, 2 faltan datos o la configuración es inválida."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    if len(argumentos) != 1 or "@" not in argumentos[0]:
        print("Uso: python notificaciones.py destinatario@ejemplo.com")
        return 2
    destinatario = argumentos[0]
    try:
        config = cargar_config()
    except ConfiguracionSMTPError as error:
        print(f"Configuración inválida: {error}")
        return 2
    if config is None:
        print("SMTP_HOST está vacío: sin servidor de correo no hay nada que probar. Completa el archivo .env (ver .env.example).")
        return 2

    print("Configuración SMTP leída del entorno:")
    print(f"  Servidor    {config.host}:{config.puerto} ({'SSL' if config.puerto == 465 else 'STARTTLS'})")
    print(f"  Usuario     {config.usuario or '(sin autenticación)'}")
    print(f"  Contraseña  {'definida' if config.password else '(sin autenticación)'}")
    print(f"  Remitente   {config.remitente_nombre} <{config.remitente_correo}>")
    if config.host.lower() in HOSTS_GMAIL and config.usuario and config.remitente_correo.lower() != config.usuario.lower():
        print("  Aviso: Gmail reemplaza el remitente por la cuenta autenticada; SMTP_FROM_EMAIL debería ser igual a SMTP_USER.")

    contenido = _correo_de_prueba(config)
    print(f"\nEnviando correo de prueba a {destinatario}...")
    try:
        _transmitir(config, construir_mensaje(
            config, destinatario, contenido.asunto, plantillas_correo.a_texto(contenido), plantillas_correo.a_html(contenido),
        ))
    except Exception as error:
        print(f"FALLÓ ({type(error).__name__}): {explicar_error(error)}")
        return 1
    print("ENVIADO: el servidor aceptó el mensaje. Revisa la bandeja de entrada (y la carpeta de spam) de "
          f"{destinatario}; la aceptación del servidor no garantiza por sí sola que haya llegado.")
    return 0


if __name__ == "__main__":
    sys.exit(_probar_desde_consola(sys.argv[1:]))
