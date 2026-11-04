import uuid
import datetime
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import and_

from models import Cita, Barbero, Servicio


def calcular_hora_fin(hora_inicio: datetime.time, duracion_minutos: int) -> datetime.time:
    """
    Suma la duración en minutos a la hora de inicio para obtener la hora de fin.
    Maneja el desbordamiento seguro dentro del mismo día.
    """
    dt = datetime.datetime.combine(datetime.date.today(), hora_inicio)
    dt_fin = dt + datetime.timedelta(minutes=duracion_minutos)
    return dt_fin.time()


def hay_solapamiento(inicio_a: datetime.time, fin_a: datetime.time, inicio_b: datetime.time, fin_b: datetime.time) -> bool:
    """
    Determina matemáticamente si dos intervalos de tiempo se solapan.
    Regla: Dos intervalos [InicioA, FinA) e [InicioB, FinB) se cruzan si:
           max(InicioA, InicioB) < min(FinA, FinB)
    
    Nota de Calidad: Si FinA == InicioB (citas consecutivas), NO hay solapamiento.
    """
    return max(inicio_a, inicio_b) < min(fin_a, fin_b)


def verificar_disponibilidad_barbero(
    db: Session,
    barbero_id: int,
    fecha: datetime.date,
    hora_inicio: datetime.time,
    hora_fin: datetime.time,
    excluir_cita_id: Optional[int] = None
) -> bool:
    """
    Consulta la base de datos para verificar si el barbero está libre en el rango especificado.
    Ignora citas que hayan sido marcadas como 'Cancelada'.
    Retorna True si está disponible, False si hay colisión.
    """
    query = db.query(Cita).filter(
        Cita.barbero_id == barbero_id,
        Cita.fecha == fecha,
        Cita.estado != "Cancelada"
    )

    if excluir_cita_id:
        query = query.filter(Cita.id != excluir_cita_id)

    citas_existentes = query.all()

    for cita in citas_existentes:
        if hay_solapamiento(hora_inicio, hora_fin, cita.hora_inicio, cita.hora_fin):
            return False  # Hay choque de horario

    return True  # El barbero está disponible


def generar_codigo_reserva() -> str:
    """Genera un código único alfanumérico amigable de 6 caracteres con prefijo BSP."""
    token = uuid.uuid4().hex[:6].upper()
    return f"BSP-{token}"


def generar_slots_del_dia(
    db: Session,
    barbero_id: int,
    fecha: datetime.date,
    duracion_minutos: int,
    hora_apertura: datetime.time = datetime.time(9, 0),
    hora_cierre: datetime.time = datetime.time(20, 0)
) -> List[Dict]:
    """
    Calcula los turnos disponibles en el horario comercial según la duración del servicio.
    Devuelve lista de objetos indicando hora inicio, hora fin y disponibilidad (True/False).
    """
    slots = []
    
    dt_cursor = datetime.datetime.combine(fecha, hora_apertura)
    dt_limite = datetime.datetime.combine(fecha, hora_cierre)

    # Citas ya reservadas para este barbero en esta fecha
    citas_activas = db.query(Cita).filter(
        Cita.barbero_id == barbero_id,
        Cita.fecha == fecha,
        Cita.estado != "Cancelada"
    ).all()

    while dt_cursor + datetime.timedelta(minutes=duracion_minutos) <= dt_limite:
        slot_inicio = dt_cursor.time()
        slot_fin = (dt_cursor + datetime.timedelta(minutes=duracion_minutos)).time()

        # Comprobar si choca con alguna cita
        ocupado = any(
            hay_solapamiento(slot_inicio, slot_fin, cita.hora_inicio, cita.hora_fin)
            for cita in citas_activas
        )

        slots.append({
            "hora_inicio": slot_inicio.strftime("%H:%M"),
            "hora_fin": slot_fin.strftime("%H:%M"),
            "disponible": not ocupado,
            "motivo": "Ocupado" if ocupado else "Libre"
        })

        # Avanzamos el cursor por intervalos regulares de 30 min para dar opciones flexibles
        dt_cursor += datetime.timedelta(minutes=30)

    return slots
