"""Envío de correos (RF-04, RF-07, RF-21 y RF-25).

Usa smtplib de la biblioteca estándar. Si SMTP_HOST no está configurado (entorno de desarrollo o
pruebas), el correo no se envía: se escribe en el registro del servidor para poder ver su contenido.
Este módulo solo arma y envía mensajes; decidir cuándo enviarlos es trabajo de services.py.
"""
import datetime
import logging
import os
import smtplib
from decimal import Decimal
from email.message import EmailMessage

logger = logging.getLogger("barberia.notificaciones")


# ==========================================
# Formato (las fechas y horas son las de Colombia, RNF-05)
# ==========================================
def _fecha(fecha: datetime.date) -> str:
    return fecha.strftime("%d/%m/%Y")


def _hora(hora: datetime.time) -> str:
    sufijo = "a. m." if hora.hour < 12 else "p. m."
    return f"{hora.hour % 12 or 12}:{hora.minute:02d} {sufijo}"


def _dinero(valor: Decimal) -> str:
    return f"${valor:,.0f}".replace(",", ".")


def _detalle_cita(cita) -> str:
    servicios = ", ".join(cs.servicio.nombre for cs in cita.servicios)
    return (
        f"Código de reserva: {cita.codigo_reserva}\n"
        f"Barbero: {cita.barbero.nombre}\n"
        f"Servicios: {servicios}\n"
        f"Fecha: {_fecha(cita.fecha)}\n"
        f"Hora: {_hora(cita.hora_inicio)}\n"
        f"Total a pagar en el local: {_dinero(cita.total)}"
    )


# ==========================================
# Envío
# ==========================================
def enviar(destinatario: str, asunto: str, cuerpo: str) -> None:
    """Envía un correo. Un fallo se registra pero no se propaga: el correo nunca debe deshacer una operación."""
    host = os.getenv("SMTP_HOST")
    if not host:
        logger.warning("SMTP_HOST no está configurado. Correo no enviado.\nPara: %s\nAsunto: %s\n%s",
                       destinatario, asunto, cuerpo)
        return

    remitente = os.getenv("SMTP_FROM") or os.getenv("SMTP_USER") or "no-responder@barbershop.pro"
    mensaje = EmailMessage()
    mensaje["From"] = remitente
    mensaje["To"] = destinatario
    mensaje["Subject"] = asunto
    mensaje.set_content(cuerpo)

    try:
        puerto = int(os.getenv("SMTP_PORT", "587"))
        if puerto == 465:
            servidor = smtplib.SMTP_SSL(host, puerto, timeout=10)
        else:
            servidor = smtplib.SMTP(host, puerto, timeout=10)
        with servidor:
            if puerto != 465:
                servidor.starttls()
            usuario = os.getenv("SMTP_USER")
            if usuario:
                servidor.login(usuario, os.getenv("SMTP_PASSWORD", ""))
            servidor.send_message(mensaje)
    except Exception:
        logger.exception("No se pudo enviar el correo '%s' a %s", asunto, destinatario)


# ==========================================
# Mensajes
# ==========================================
def recuperacion_password(usuario, enlace: str) -> None:
    # RNF-01 (CP-RNF01-2): el correo lleva solo el enlace, nunca la contraseña
    enviar(
        usuario.email,
        "Recupera tu contraseña - BarberShop Pro",
        f"Hola {usuario.nombre},\n\n"
        "Recibimos una solicitud para cambiar tu contraseña. Abre este enlace para definir una nueva "
        f"(vence en 1 hora):\n{enlace}\n\n"
        "Si no fuiste tú, ignora este mensaje.",
    )


def confirmacion_cita(cita) -> None:
    enviar(
        cita.cliente.email,
        f"Cita confirmada {cita.codigo_reserva} - BarberShop Pro",
        f"Hola {cita.cliente.nombre},\n\nTu cita quedó agendada.\n\n{_detalle_cita(cita)}",
    )


def cita_cancelada(cita) -> None:
    """Al cliente y al barbero (RF-25)."""
    cuerpo = f"La siguiente cita fue cancelada.\n\n{_detalle_cita(cita)}"
    enviar(cita.cliente.email, f"Cita cancelada {cita.codigo_reserva} - BarberShop Pro",
           f"Hola {cita.cliente.nombre},\n\n{cuerpo}")
    enviar(cita.barbero.email, f"Cita cancelada {cita.codigo_reserva} - BarberShop Pro",
           f"Hola {cita.barbero.nombre},\n\n{cuerpo}")


def cita_reprogramada(cita, fecha_anterior: datetime.date, hora_anterior: datetime.time) -> None:
    """Al cliente y al barbero (RF-25)."""
    cuerpo = (
        f"La cita {cita.codigo_reserva} fue reprogramada.\n"
        f"Horario anterior: {_fecha(fecha_anterior)} a las {_hora(hora_anterior)}\n\n"
        f"Nuevo horario:\n{_detalle_cita(cita)}"
    )
    enviar(cita.cliente.email, f"Cita reprogramada {cita.codigo_reserva} - BarberShop Pro",
           f"Hola {cita.cliente.nombre},\n\n{cuerpo}")
    enviar(cita.barbero.email, f"Cita reprogramada {cita.codigo_reserva} - BarberShop Pro",
           f"Hola {cita.barbero.nombre},\n\n{cuerpo}")


def cita_cancelada_por_baja_del_barbero(cita) -> None:
    """Al cliente cuya cita futura se cancela porque el barbero fue eliminado (RF-07, PN-08)."""
    enviar(
        cita.cliente.email,
        f"Tu cita {cita.codigo_reserva} fue cancelada - BarberShop Pro",
        f"Hola {cita.cliente.nombre},\n\nTu cita fue cancelada porque el barbero ya no atiende en la barbería. "
        "Puedes agendar una nueva con otro barbero.\n\n" + _detalle_cita(cita),
    )
