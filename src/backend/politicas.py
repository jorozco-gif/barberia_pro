"""Políticas del negocio (sección 6 de docs/especificacion.md).

Los valores están aquí para poder cambiarlos sin tocar la lógica de services.py. Varios están
marcados como "propuesto" en la especificación y falta que el dueño de la barbería los confirme.
"""
import datetime

# PN-01: vigencia del enlace de recuperación de contraseña (propuesto)
VIGENCIA_ENLACE_RECUPERACION = datetime.timedelta(hours=1)

# PN-02: intervalo de los horarios disponibles, en minutos (propuesto)
INTERVALO_MINUTOS = 30

# PN-03: horas de cada franja del día, como (inicio, fin). Un horario pertenece a la franja
# según su hora de inicio: el inicio se incluye y el fin no (propuesto)
FRANJAS = {
    "Mañana": (datetime.time(6, 0), datetime.time(12, 0)),
    "Tarde": (datetime.time(12, 0), datetime.time(18, 0)),
    "Noche": (datetime.time(18, 0), datetime.time(22, 0)),
}

# PN-04 y PN-05: anticipación mínima para cancelar y para reprogramar una cita.
# Con exactamente 12 horas de anticipación sí se permite.
ANTICIPACION_MINIMA = datetime.timedelta(hours=12)

# PN-07: tiempo de inactividad tras el cual se cierra la sesión
INACTIVIDAD_SESION = datetime.timedelta(minutes=15)

# PN-09: máximo de citas activas (estado Programada) por cliente
MAX_CITAS_ACTIVAS = 2

# PN-10: con 2 inasistencias dentro de 3 meses, el cliente queda suspendido 1 mes
INASISTENCIAS_PARA_SUSPENDER = 2
MESES_VENTANA_INASISTENCIAS = 3
MESES_SUSPENSION = 1
