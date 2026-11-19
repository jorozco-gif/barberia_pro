import datetime
from decimal import Decimal
from typing import List, Literal, Optional
from pydantic import (
    BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator,
)

from politicas import INTERVALO_MINUTOS  # PN-02

# RF-17: franja del día (las horas de cada franja, PN-03, van en la capa de servicios). Desde la v1.2 el cliente
# ya no la elige al reservar (ve todos los turnos del día); se conserva como filtro opcional de la API.
Franja = Literal["Mañana", "Tarde", "Noche"]

# RF-27: estados que puede marcar el barbero sobre una cita
ESTADOS_QUE_MARCA_EL_BARBERO = ("Atendida", "Cancelada", "Inasistencia")

LEER_DESDE_ORM = ConfigDict(from_attributes=True)


def _no_vacio(v: str, mensaje: str = "El campo no puede estar vacío ni contener solo espacios.") -> str:
    v = v.strip()
    if not v:
        raise ValueError(mensaje)
    return v


def _texto_opcional(v: Optional[str]) -> Optional[str]:
    """Quita espacios a un texto opcional. Un texto vacío o solo con espacios se guarda como nulo."""
    if v is None:
        return None
    v = v.strip()
    return v or None


def _validar_intervalo(v: datetime.time) -> datetime.time:
    if v.minute % INTERVALO_MINUTOS != 0 or v.second or v.microsecond:
        raise ValueError(
            f"La hora debe coincidir con intervalos de {INTERVALO_MINUTOS} minutos (ej. 08:00, 08:30)."
        )
    return v


# ==========================================
# Cuentas y acceso (RF-01 a RF-04)
# ==========================================
class RegistroCliente(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=120)
    telefono: str = Field(..., min_length=7, max_length=25)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    # RNF-06: autorización para tratar datos personales (Ley 1581 de 2012)
    acepta_tratamiento_datos: bool

    @field_validator("nombre", "telefono")
    @classmethod
    def validar_texto(cls, v: str) -> str:
        return _no_vacio(v)

    @field_validator("acepta_tratamiento_datos")
    @classmethod
    def exigir_autorizacion(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Debes autorizar el tratamiento de tus datos personales para registrarte.")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class UsuarioResponse(BaseModel):
    id: int
    nombre: str
    telefono: Optional[str] = None
    email: str
    rol: str
    model_config = LEER_DESDE_ORM


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioResponse


class SolicitudRecuperacion(BaseModel):
    email: EmailStr


class RestablecerPassword(BaseModel):
    token: str = Field(..., min_length=1, max_length=200)
    nueva_password: str = Field(..., min_length=8, max_length=128)


# ==========================================
# Barberos (RF-05 a RF-07, RF-13)
# ==========================================
class BarberoCreate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    foto_url: Optional[str] = Field(None, max_length=255)

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, v: str) -> str:
        return _no_vacio(v, "El nombre es obligatorio.")


class BarberoUpdate(BaseModel):
    """Solo se modifican los campos enviados (RF-06, v1.2: nombre, correo, contraseña y foto).
    El nombre no puede quedar vacío ni nulo (CA-06.2); el correo y la contraseña no se pueden enviar nulos.
    La foto sí admite nulo o vacío para quitarla."""

    nombre: Optional[str] = Field(None, min_length=2, max_length=120)
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=8, max_length=128)
    foto_url: Optional[str] = Field(None, max_length=255)

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, v: Optional[str]) -> str:
        if v is None:
            raise ValueError("El nombre es obligatorio.")
        return _no_vacio(v, "El nombre es obligatorio.")

    @field_validator("email", "password")
    @classmethod
    def rechazar_nulos(cls, v):
        if v is None:
            raise ValueError("El campo no puede enviarse vacío.")
        return v

    @field_validator("foto_url")
    @classmethod
    def validar_foto(cls, v: Optional[str]) -> Optional[str]:
        return _texto_opcional(v)


class BarberoResponse(BaseModel):
    """Vista completa, para el administrador."""

    id: int
    nombre: str
    email: str
    telefono: Optional[str] = None
    foto_url: Optional[str] = None
    activo: bool
    model_config = LEER_DESDE_ORM


class BarberoPublico(BaseModel):
    """Vista para el cliente al elegir barbero: solo nombre y foto (RF-13)."""

    id: int
    nombre: str
    foto_url: Optional[str] = None
    model_config = LEER_DESDE_ORM


# ==========================================
# Servicios (RF-08 a RF-10)
# ==========================================
class ServicioCreate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=100)
    duracion_minutos: int = Field(..., gt=0, le=240, description="Mayor a 0 y hasta 4 horas")
    precio: Decimal = Field(..., ge=0, description="No puede ser negativo")
    descripcion: Optional[str] = Field(None, max_length=1000, description="Opcional (v1.2): se muestra en un modal")

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, v: str) -> str:
        return _no_vacio(v, "El nombre del servicio es obligatorio.")

    @field_validator("descripcion")
    @classmethod
    def validar_descripcion(cls, v: Optional[str]) -> Optional[str]:
        return _texto_opcional(v)


class ServicioUpdate(BaseModel):
    """Solo se modifican los campos enviados (RF-09). Nombre, duración y precio no pueden enviarse nulos;
    la descripción sí (nula o vacía la quita)."""

    nombre: Optional[str] = Field(None, min_length=2, max_length=100)
    duracion_minutos: Optional[int] = Field(None, gt=0, le=240)
    precio: Optional[Decimal] = Field(None, ge=0)
    descripcion: Optional[str] = Field(None, max_length=1000)

    @field_validator("descripcion")
    @classmethod
    def validar_descripcion(cls, v: Optional[str]) -> Optional[str]:
        return _texto_opcional(v)

    @field_validator("nombre", "duracion_minutos", "precio")
    @classmethod
    def rechazar_nulos(cls, v):
        if v is None:
            raise ValueError("El campo no puede enviarse vacío.")
        return v

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, v: str) -> str:
        return _no_vacio(v, "El nombre del servicio es obligatorio.")


class ServicioResponse(BaseModel):
    id: int
    nombre: str
    duracion_minutos: int
    precio: Decimal
    descripcion: Optional[str] = None
    activo: bool
    model_config = LEER_DESDE_ORM


# ==========================================
# Estilos (v1.2: RF-33 y RF-34)
# ==========================================
class EstiloCreate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=100)
    descripcion: str = Field(..., min_length=1, max_length=1000, description="Se muestra al cliente en un modal")
    foto_url: Optional[str] = Field(None, max_length=255)

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, v: str) -> str:
        return _no_vacio(v, "El nombre del estilo es obligatorio.")

    @field_validator("descripcion")
    @classmethod
    def validar_descripcion(cls, v: str) -> str:
        return _no_vacio(v, "La descripción del estilo es obligatoria.")

    @field_validator("foto_url")
    @classmethod
    def validar_foto(cls, v: Optional[str]) -> Optional[str]:
        return _texto_opcional(v)


class EstiloUpdate(BaseModel):
    """Solo se modifican los campos enviados. Nombre y descripción no pueden quedar nulos ni vacíos;
    la foto sí (nula o vacía la quita)."""

    nombre: Optional[str] = Field(None, min_length=2, max_length=100)
    descripcion: Optional[str] = Field(None, min_length=1, max_length=1000)
    foto_url: Optional[str] = Field(None, max_length=255)

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, v: Optional[str]) -> str:
        if v is None:
            raise ValueError("El nombre del estilo es obligatorio.")
        return _no_vacio(v, "El nombre del estilo es obligatorio.")

    @field_validator("descripcion")
    @classmethod
    def validar_descripcion(cls, v: Optional[str]) -> str:
        if v is None:
            raise ValueError("La descripción del estilo es obligatoria.")
        return _no_vacio(v, "La descripción del estilo es obligatoria.")

    @field_validator("foto_url")
    @classmethod
    def validar_foto(cls, v: Optional[str]) -> Optional[str]:
        return _texto_opcional(v)


class EstiloResponse(BaseModel):
    id: int
    nombre: str
    descripcion: str
    foto_url: Optional[str] = None
    activo: bool
    model_config = LEER_DESDE_ORM


class EstiloEnCita(BaseModel):
    """Estilo que se muestra junto a la cita (confirmación, consulta, agenda del barbero)."""

    id: int
    nombre: str
    foto_url: Optional[str] = None
    model_config = LEER_DESDE_ORM


# ==========================================
# Disponibilidad y bloqueos del barbero (RF-11, RF-12)
# ==========================================
class DisponibilidadCreate(BaseModel):
    dia_semana: int = Field(..., ge=0, le=6, description="0 = lunes ... 6 = domingo")
    hora_inicio: datetime.time
    hora_fin: datetime.time

    @field_validator("hora_inicio", "hora_fin")
    @classmethod
    def validar_intervalo(cls, v: datetime.time) -> datetime.time:
        return _validar_intervalo(v)

    @model_validator(mode="after")
    def validar_rango(self):
        if self.hora_fin <= self.hora_inicio:
            raise ValueError("La hora de fin debe ser posterior a la hora de inicio.")
        return self


class DisponibilidadResponse(BaseModel):
    id: int
    dia_semana: int
    hora_inicio: datetime.time
    hora_fin: datetime.time
    model_config = LEER_DESDE_ORM


class BloqueoCreate(BaseModel):
    """Sin horas se bloquea el día completo. La fecha no puede ser pasada: se valida en el servicio."""

    fecha: datetime.date
    hora_inicio: Optional[datetime.time] = None
    hora_fin: Optional[datetime.time] = None

    @model_validator(mode="after")
    def validar_rango(self):
        if (self.hora_inicio is None) != (self.hora_fin is None):
            raise ValueError("Indica hora de inicio y de fin, o ninguna para bloquear el día completo.")
        if self.hora_inicio is not None and self.hora_fin <= self.hora_inicio:
            raise ValueError("La hora de fin debe ser posterior a la hora de inicio.")
        return self


class BloqueoResponse(BaseModel):
    id: int
    fecha: datetime.date
    hora_inicio: Optional[datetime.time] = None
    hora_fin: Optional[datetime.time] = None
    model_config = LEER_DESDE_ORM


# ==========================================
# Citas (RF-14 a RF-20, RF-22 a RF-28)
# ==========================================
class CitaCreate(BaseModel):
    """El cliente sale de la sesión, no del cuerpo. La fecha pasada (HTTP 400) y el intervalo de PN-02 se validan
    en el servicio: una hora fuera del intervalo que choca con otra cita debe responder 409, no 422 (CA-20.3).
    v1.2: se elimina el campo de notas; la personalización es el estilo (RF-34). Es obligatorio solo si el
    catálogo tiene estilos activos (PN-14), por eso esa regla también se valida en el servicio."""

    barbero_id: int = Field(..., gt=0)
    servicios_ids: List[int] = Field(..., min_length=1, description="Uno o varios servicios (RF-14)")
    estilo_id: Optional[int] = Field(None, gt=0, description="Estilo elegido (RF-34)")
    fecha: datetime.date
    hora_inicio: datetime.time

    @field_validator("servicios_ids")
    @classmethod
    def validar_servicios(cls, v: List[int]) -> List[int]:
        if any(i <= 0 for i in v):
            raise ValueError("Identificador de servicio no válido.")
        if len(set(v)) != len(v):
            raise ValueError("No repitas el mismo servicio.")
        return v


class CitaReprogramar(BaseModel):
    """Nuevo horario del mismo barbero (RF-24). Igual que en CitaCreate, el intervalo de PN-02 se valida en el servicio."""

    fecha: datetime.date
    hora_inicio: datetime.time


class CitaEstadoUpdate(BaseModel):
    estado: str = Field(..., description="Atendida, Cancelada o Inasistencia")

    @field_validator("estado")
    @classmethod
    def validar_estado(cls, v: str) -> str:
        if v not in ESTADOS_QUE_MARCA_EL_BARBERO:
            raise ValueError(
                f"Estado '{v}' no es válido. Estados permitidos: {', '.join(ESTADOS_QUE_MARCA_EL_BARBERO)}"
            )
        return v


class CitaServicioResponse(BaseModel):
    id: int
    servicio_id: int
    precio_aplicado: Decimal
    duracion_minutos: int
    servicio: Optional[ServicioResponse] = None
    model_config = LEER_DESDE_ORM


class CitaResponse(BaseModel):
    id: int
    codigo_reserva: str
    cliente_id: int
    barbero_id: int
    fecha: datetime.date
    hora_inicio: datetime.time
    hora_fin: datetime.time
    estado: str
    total: Decimal
    reprogramada: bool
    estilo_id: Optional[int] = None
    notas: Optional[str] = None  # legado v1.1: solo las citas anteriores a la v1.2 pueden tenerlas
    creada_el: datetime.datetime
    cliente: Optional[UsuarioResponse] = None
    barbero: Optional[BarberoPublico] = None
    estilo: Optional[EstiloEnCita] = None
    servicios: List[CitaServicioResponse] = []
    model_config = LEER_DESDE_ORM


# ==========================================
# Disponibilidad de horarios (RF-18)
# ==========================================
class SlotHorario(BaseModel):
    hora_inicio: str
    hora_fin: str
    disponible: bool
    motivo: Optional[str] = None


# ==========================================
# Respuestas auxiliares
# ==========================================
class MensajeResponse(BaseModel):
    detail: str


class ResumenCitaResponse(BaseModel):
    """Total y duración de los servicios elegidos (RF-15)."""

    servicios: List[ServicioResponse]
    total: Decimal
    duracion_total_minutos: int
