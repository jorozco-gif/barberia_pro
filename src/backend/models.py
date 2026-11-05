import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, Numeric, Date, Time, DateTime,
    ForeignKey, Text, Index,
)
from sqlalchemy.orm import relationship
from database import Base

# RNF-05: todas las fechas y horas se manejan en la zona horaria de Colombia (UTC-5).
# Colombia no tiene horario de verano, por eso basta un desfase fijo.
COLOMBIA_TZ = datetime.timezone(datetime.timedelta(hours=-5))


def ahora_colombia() -> datetime.datetime:
    """Fecha y hora actual de Colombia, sin zona, para guardar y comparar de forma uniforme."""
    return datetime.datetime.now(COLOMBIA_TZ).replace(tzinfo=None)


# Roles de usuario (RF-02)
ROL_CLIENTE = "cliente"
ROL_BARBERO = "barbero"
ROL_ADMIN = "administrador"

# Estados de una cita (sección 2 de la v1.1)
ESTADO_PROGRAMADA = "Programada"
ESTADO_ATENDIDA = "Atendida"
ESTADO_CANCELADA = "Cancelada"
ESTADO_INASISTENCIA = "Inasistencia"


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(120), nullable=False)
    telefono = Column(String(25), nullable=True)  # obligatorio solo para clientes (se valida en el esquema)
    email = Column(String(120), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)  # RNF-01: la contraseña nunca se guarda en claro
    rol = Column(String(20), nullable=False, index=True)  # 'cliente', 'barbero' o 'administrador'
    suspendido_hasta = Column(Date, nullable=True)  # RF-29: fecha en que termina la suspensión
    activo = Column(Boolean, default=True, nullable=False)

    barbero = relationship("Barbero", back_populates="usuario", uselist=False)
    citas = relationship("Cita", back_populates="cliente")
    tokens_recuperacion = relationship(
        "TokenRecuperacion", back_populates="usuario", cascade="all, delete-orphan"
    )
    sesiones = relationship("Sesion", back_populates="usuario", cascade="all, delete-orphan")


class Barbero(Base):
    __tablename__ = "barberos"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(
        Integer, ForeignKey("usuarios.id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    foto_url = Column(String(255), nullable=True)
    activo = Column(Boolean, default=True, nullable=False)  # RF-07: eliminación lógica

    usuario = relationship("Usuario", back_populates="barbero", lazy="joined")
    # Sin cascade: el historial de citas se conserva aunque el barbero quede inactivo
    citas = relationship("Cita", back_populates="barbero")
    disponibilidades = relationship(
        "Disponibilidad", back_populates="barbero", cascade="all, delete-orphan"
    )
    bloqueos = relationship("Bloqueo", back_populates="barbero", cascade="all, delete-orphan")

    # Atajos para que las respuestas sigan mostrando nombre, correo y teléfono del barbero
    @property
    def nombre(self):
        return self.usuario.nombre

    @property
    def email(self):
        return self.usuario.email

    @property
    def telefono(self):
        return self.usuario.telefono


class Servicio(Base):
    __tablename__ = "servicios"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    duracion_minutos = Column(Integer, nullable=False)  # Ej: 30, 45, 60
    precio = Column(Numeric(10, 2), nullable=False)  # Ej: 15000.00
    activo = Column(Boolean, default=True, nullable=False)  # RF-10: eliminación lógica

    citas_servicios = relationship("CitaServicio", back_populates="servicio")


class Cita(Base):
    __tablename__ = "citas"
    __table_args__ = (Index("ix_citas_barbero_fecha", "barbero_id", "fecha"),)

    id = Column(Integer, primary_key=True, index=True)
    codigo_reserva = Column(String(20), unique=True, index=True, nullable=False)

    # Claves foráneas (RNF-07)
    cliente_id = Column(
        Integer, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    barbero_id = Column(Integer, ForeignKey("barberos.id", ondelete="RESTRICT"), nullable=False)

    # Horario de la reserva
    fecha = Column(Date, nullable=False, index=True)
    hora_inicio = Column(Time, nullable=False)
    hora_fin = Column(Time, nullable=False)

    # Estado: 'Programada', 'Atendida', 'Cancelada' o 'Inasistencia'
    estado = Column(String(30), default=ESTADO_PROGRAMADA, nullable=False, index=True)
    total = Column(Numeric(10, 2), default=0, nullable=False)
    reprogramada = Column(Boolean, default=False, nullable=False)  # PN-05: una sola reprogramación
    notas = Column(Text, nullable=True)
    creada_el = Column(DateTime, default=ahora_colombia, nullable=False)

    cliente = relationship("Usuario", back_populates="citas")
    barbero = relationship("Barbero", back_populates="citas")
    servicios = relationship("CitaServicio", back_populates="cita", cascade="all, delete-orphan")


class CitaServicio(Base):
    """Un servicio dentro de una cita. Guarda el precio y la duración vigentes al reservar,
    para que modificar el servicio (RF-09) no cambie las citas ya agendadas."""

    __tablename__ = "citas_servicios"

    id = Column(Integer, primary_key=True, index=True)
    cita_id = Column(Integer, ForeignKey("citas.id", ondelete="CASCADE"), nullable=False, index=True)
    servicio_id = Column(Integer, ForeignKey("servicios.id", ondelete="RESTRICT"), nullable=False)
    precio_aplicado = Column(Numeric(10, 2), nullable=False)
    duracion_minutos = Column(Integer, nullable=False)

    cita = relationship("Cita", back_populates="servicios")
    servicio = relationship("Servicio", back_populates="citas_servicios")


class Disponibilidad(Base):
    """Horario semanal que define el barbero (RF-11)."""

    __tablename__ = "disponibilidades"

    id = Column(Integer, primary_key=True, index=True)
    barbero_id = Column(
        Integer, ForeignKey("barberos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dia_semana = Column(Integer, nullable=False)  # 0 = lunes ... 6 = domingo (igual que date.weekday())
    hora_inicio = Column(Time, nullable=False)
    hora_fin = Column(Time, nullable=False)

    barbero = relationship("Barbero", back_populates="disponibilidades")


class Bloqueo(Base):
    """Día u horas en que el barbero no atiende (RF-12).
    Si hora_inicio y hora_fin son nulas, se bloquea el día completo."""

    __tablename__ = "bloqueos"

    id = Column(Integer, primary_key=True, index=True)
    barbero_id = Column(
        Integer, ForeignKey("barberos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    fecha = Column(Date, nullable=False, index=True)
    hora_inicio = Column(Time, nullable=True)
    hora_fin = Column(Time, nullable=True)

    barbero = relationship("Barbero", back_populates="bloqueos")


class TokenRecuperacion(Base):
    """Enlace de recuperación de contraseña (RF-04). Se guarda solo el hash del token."""

    __tablename__ = "tokens_recuperacion"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(
        Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash = Column(String(64), unique=True, index=True, nullable=False)
    expira_en = Column(DateTime, nullable=False)  # PN-01: 1 hora de vigencia
    usado = Column(Boolean, default=False, nullable=False)

    usuario = relationship("Usuario", back_populates="tokens_recuperacion")


class Sesion(Base):
    """Sesión abierta de un usuario (RF-02, RF-03, RNF-02). Se guarda solo el hash del token.
    La sesión expira cuando pasan 15 minutos desde la última actividad (PN-07)."""

    __tablename__ = "sesiones"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(
        Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash = Column(String(64), unique=True, index=True, nullable=False)
    creada_el = Column(DateTime, nullable=False)
    ultima_actividad = Column(DateTime, nullable=False)

    usuario = relationship("Usuario", back_populates="sesiones")
