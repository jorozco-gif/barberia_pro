"""Capa de servicios (RNF-09): reglas de negocio y único acceso a la base de datos.

main.py solo recibe las peticiones, valida la sesión y el rol, y llama a estas funciones. Aquí se
aplican las reglas de docs/especificacion.md y se lanzan errores de dominio (sin depender de FastAPI)
que main.py traduce a códigos HTTP. Las fechas y horas son las de Colombia (RNF-05).
"""
import calendar
import datetime
import logging
import os
import threading
import uuid
from contextlib import contextmanager
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import and_, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, lazyload

import notificaciones
import politicas
import schemas
import security
from models import (
    ahora_colombia,
    Barbero, Bloqueo, Cita, CitaServicio, Disponibilidad, Servicio, Sesion, TokenRecuperacion, Usuario,
    ROL_ADMIN, ROL_BARBERO, ROL_CLIENTE,
    ESTADO_CANCELADA, ESTADO_INASISTENCIA, ESTADO_PROGRAMADA,
)

logger = logging.getLogger("barberia.services")


# ==========================================
# Errores de dominio (main.py los traduce a HTTP)
# ==========================================
class ErrorDeNegocio(Exception):
    status_code = 400

    def __init__(self, detalle: str, **datos):
        super().__init__(detalle)
        self.detalle = detalle
        self.datos = datos  # campos adicionales para la respuesta (por ejemplo, la fecha de reactivación)


class ReglaIncumplida(ErrorDeNegocio):
    status_code = 400


class NoAutorizado(ErrorDeNegocio):
    status_code = 401


class Prohibido(ErrorDeNegocio):
    status_code = 403


class NoEncontrado(ErrorDeNegocio):
    status_code = 404


class Conflicto(ErrorDeNegocio):
    status_code = 409


# ==========================================
# Utilidades de tiempo y de cálculo
# ==========================================
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


def generar_codigo_reserva() -> str:
    """Genera un código único alfanumérico amigable de 6 caracteres con prefijo BSP."""
    token = uuid.uuid4().hex[:6].upper()
    return f"BSP-{token}"


def sumar_meses(fecha: datetime.date, meses: int) -> datetime.date:
    """Suma (o resta) meses calendario. Si el día no existe en el mes destino, usa el último día del mes."""
    indice = fecha.year * 12 + (fecha.month - 1) + meses
    anio, mes = divmod(indice, 12)
    mes += 1
    return fecha.replace(year=anio, month=mes, day=min(fecha.day, calendar.monthrange(anio, mes)[1]))


def _inicio_de_cita(cita: Cita) -> datetime.datetime:
    return datetime.datetime.combine(cita.fecha, cita.hora_inicio)


def _normalizar_email(email: str) -> str:
    return email.strip().lower()


def _notificar(enviar_correo, *args) -> None:
    """Los correos se envían después de confirmar la operación y un fallo nunca la deshace."""
    try:
        enviar_correo(*args)
    except Exception:
        logger.exception("No se pudo enviar la notificación")


# ==========================================
# Búsquedas comunes
# ==========================================
def _correo_en_uso(db: Session, email: str) -> bool:
    return db.query(Usuario.id).filter(func.lower(Usuario.email) == email).first() is not None


def _barbero_activo(db: Session, barbero_id: int) -> Barbero:
    barbero = db.query(Barbero).filter(Barbero.id == barbero_id, Barbero.activo == True).first()  # noqa: E712
    if barbero is None:
        raise NoEncontrado("El barbero no existe o no está activo.")
    return barbero


def _barbero_de_usuario(db: Session, usuario: Usuario) -> Barbero:
    barbero = db.query(Barbero).filter(Barbero.usuario_id == usuario.id, Barbero.activo == True).first()  # noqa: E712
    if barbero is None:
        raise Prohibido("Tu cuenta no tiene un perfil de barbero activo.")
    return barbero


def _servicio_activo(db: Session, servicio_id: int) -> Servicio:
    servicio = db.query(Servicio).filter(Servicio.id == servicio_id, Servicio.activo == True).first()  # noqa: E712
    if servicio is None:
        raise NoEncontrado("El servicio no existe o no está disponible.")
    return servicio


def _obtener_cita(db: Session, cita_id: int, bloquear: bool = False) -> Cita:
    consulta = db.query(Cita).filter(Cita.id == cita_id)
    if bloquear:
        consulta = consulta.with_for_update()
    cita = consulta.first()
    if cita is None:
        raise NoEncontrado("La cita no existe.")
    return cita


def obtener_servicios_activos(db: Session, servicios_ids: List[int]) -> List[Servicio]:
    """Servicios elegidos (RF-14), en el orden en que se pidieron. Uno eliminado se rechaza (CA-10.2)."""
    if len(set(servicios_ids)) != len(servicios_ids):
        raise ReglaIncumplida("No repitas el mismo servicio.")
    encontrados = {
        s.id: s
        for s in db.query(Servicio).filter(Servicio.id.in_(servicios_ids), Servicio.activo == True).all()  # noqa: E712
    }
    if len(encontrados) != len(servicios_ids):
        raise NoEncontrado("Uno o más servicios no existen o no están disponibles.")
    return [encontrados[i] for i in servicios_ids]


# ==========================================
# Cuentas y acceso (RF-01 a RF-04, RNF-02)
# ==========================================
def registrar_cliente(db: Session, datos: schemas.RegistroCliente) -> Usuario:
    email = _normalizar_email(datos.email)
    if _correo_en_uso(db, email):
        raise ReglaIncumplida("El correo ya está registrado.")
    usuario = Usuario(
        nombre=datos.nombre,
        telefono=datos.telefono,
        email=email,
        password_hash=security.hash_password(datos.password),
        rol=ROL_CLIENTE,
        activo=True,
    )
    db.add(usuario)
    try:
        db.commit()
    except IntegrityError:  # otro registro con el mismo correo ganó la carrera
        db.rollback()
        raise ReglaIncumplida("El correo ya está registrado.")
    return usuario


def _cuenta_activa(usuario: Usuario) -> bool:
    """RF-07 (CA-07.2): un barbero eliminado no puede ingresar."""
    if not usuario.activo:
        return False
    if usuario.rol == ROL_BARBERO:
        return usuario.barbero is not None and usuario.barbero.activo
    return True


def _esta_suspendido(usuario: Usuario, hoy: datetime.date) -> bool:
    """PN-10: está suspendido hasta la fecha de reactivación; ese día ya puede ingresar."""
    return usuario.rol == ROL_CLIENTE and usuario.suspendido_hasta is not None and hoy < usuario.suspendido_hasta


def _cerrar_sesiones(db: Session, usuario_id: int) -> None:
    db.query(Sesion).filter(Sesion.usuario_id == usuario_id).delete(synchronize_session=False)


def iniciar_sesion(db: Session, datos: schemas.LoginRequest):
    """Devuelve (token de sesión, usuario)."""
    usuario = db.query(Usuario).filter(func.lower(Usuario.email) == _normalizar_email(datos.email)).first()
    if usuario is None:
        raise NoAutorizado("El correo no está registrado.")  # CA-02.2
    if not security.verify_password(datos.password, usuario.password_hash):
        raise NoAutorizado("La contraseña es incorrecta.")
    if not _cuenta_activa(usuario):
        raise NoAutorizado("Esta cuenta está inactiva.")

    ahora = ahora_colombia()
    if _esta_suspendido(usuario, ahora.date()):  # CA-30.1
        raise Prohibido(
            f"Tu cuenta está suspendida hasta el {usuario.suspendido_hasta.strftime('%d/%m/%Y')}.",
            suspendido_hasta=usuario.suspendido_hasta.isoformat(),
        )

    # Se limpian las sesiones ya vencidas de este usuario para que la tabla no crezca sin límite
    db.query(Sesion).filter(
        Sesion.usuario_id == usuario.id,
        Sesion.ultima_actividad <= ahora - politicas.INACTIVIDAD_SESION,
    ).delete(synchronize_session=False)

    token, token_hash = security.generar_token()
    db.add(Sesion(usuario_id=usuario.id, token_hash=token_hash, creada_el=ahora, ultima_actividad=ahora))
    db.commit()
    return token, usuario


def autenticar_sesion(db: Session, token: str) -> Usuario:
    """Valida el token y renueva el tiempo de inactividad (RNF-02, PN-07)."""
    sesion = db.query(Sesion).filter(Sesion.token_hash == security.hash_token(token)).first()
    if sesion is None:
        raise NoAutorizado("Sesión no válida. Inicia sesión.")  # CA-03.2

    ahora = ahora_colombia()
    usuario = sesion.usuario
    if ahora - sesion.ultima_actividad >= politicas.INACTIVIDAD_SESION or not _cuenta_activa(usuario):
        db.delete(sesion)
        db.commit()
        raise NoAutorizado("Tu sesión expiró. Inicia sesión de nuevo.")

    sesion.ultima_actividad = ahora
    db.commit()
    return usuario


def cerrar_sesion(db: Session, token: str) -> None:
    db.query(Sesion).filter(Sesion.token_hash == security.hash_token(token)).delete(synchronize_session=False)
    db.commit()


def solicitar_recuperacion(db: Session, email: str) -> None:
    """RF-04. No revela si el correo existe: la respuesta es la misma siempre."""
    usuario = db.query(Usuario).filter(func.lower(Usuario.email) == _normalizar_email(email)).first()
    if usuario is None or not _cuenta_activa(usuario):
        return
    token, token_hash = security.generar_token()
    db.add(TokenRecuperacion(
        usuario_id=usuario.id,
        token_hash=token_hash,
        expira_en=ahora_colombia() + politicas.VIGENCIA_ENLACE_RECUPERACION,
        usado=False,
    ))
    db.commit()
    frontend = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    _notificar(notificaciones.recuperacion_password, usuario, f"{frontend}/restablecer?token={token}")


def validar_token_recuperacion(db: Session, token: str) -> TokenRecuperacion:
    registro = db.query(TokenRecuperacion).filter(TokenRecuperacion.token_hash == security.hash_token(token)).first()
    if registro is None or registro.usado:
        raise ReglaIncumplida("El enlace no es válido.")
    if ahora_colombia() > registro.expira_en:  # CA-04.2
        raise ReglaIncumplida("El enlace caducó. Solicita uno nuevo.")
    return registro


def restablecer_password(db: Session, token: str, nueva_password: str) -> None:
    registro = validar_token_recuperacion(db, token)
    registro.usuario.password_hash = security.hash_password(nueva_password)
    registro.usado = True
    _cerrar_sesiones(db, registro.usuario_id)  # una sesión abierta con la contraseña anterior ya no debe valer
    db.commit()


# ==========================================
# Barberos y servicios (RF-05 a RF-10, RF-13, RF-14)
# ==========================================
def listar_barberos(db: Session, solo_activos: bool = True) -> List[Barbero]:
    consulta = db.query(Barbero)
    if solo_activos:
        consulta = consulta.filter(Barbero.activo == True)  # noqa: E712
    return consulta.order_by(Barbero.id).all()


def crear_barbero(db: Session, datos: schemas.BarberoCreate) -> Barbero:
    email = _normalizar_email(datos.email)
    if _correo_en_uso(db, email):
        raise ReglaIncumplida(f"Ya existe una cuenta registrada con el correo '{email}'.")  # CA-05.2
    barbero = Barbero(
        usuario=Usuario(
            nombre=datos.nombre,
            email=email,
            password_hash=security.hash_password(datos.password),
            rol=ROL_BARBERO,
            activo=True,
        ),
        foto_url=datos.foto_url,
        activo=True,
    )
    db.add(barbero)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ReglaIncumplida(f"Ya existe una cuenta registrada con el correo '{email}'.")
    return barbero


def actualizar_barbero(db: Session, barbero_id: int, datos: schemas.BarberoUpdate) -> Barbero:
    barbero = _barbero_activo(db, barbero_id)
    cambios = datos.model_dump(exclude_unset=True)
    if "nombre" in cambios:
        barbero.usuario.nombre = cambios["nombre"]
    if "foto_url" in cambios:
        barbero.foto_url = cambios["foto_url"]
    db.commit()
    return barbero


def eliminar_barbero(db: Session, barbero_id: int) -> Barbero:
    """RF-07 y PN-08: eliminación lógica. Las citas futuras se cancelan y se avisa a los clientes."""
    barbero = _barbero_activo(db, barbero_id)
    ahora = ahora_colombia()
    futuras = db.query(Cita).filter(
        Cita.barbero_id == barbero.id,
        Cita.estado == ESTADO_PROGRAMADA,
        or_(Cita.fecha > ahora.date(), and_(Cita.fecha == ahora.date(), Cita.hora_inicio > ahora.time())),
    ).all()
    for cita in futuras:
        cita.estado = ESTADO_CANCELADA
    barbero.activo = False
    barbero.usuario.activo = False  # el correo queda reservado y la cuenta no puede ingresar (CA-07.2)
    _cerrar_sesiones(db, barbero.usuario_id)
    db.commit()
    for cita in futuras:
        _notificar(notificaciones.cita_cancelada_por_baja_del_barbero, cita)
    return barbero


def listar_servicios(db: Session, solo_activos: bool = True) -> List[Servicio]:
    consulta = db.query(Servicio)
    if solo_activos:
        consulta = consulta.filter(Servicio.activo == True)  # noqa: E712
    return consulta.order_by(Servicio.id).all()


def crear_servicio(db: Session, datos: schemas.ServicioCreate) -> Servicio:
    servicio = Servicio(**datos.model_dump(), activo=True)
    db.add(servicio)
    db.commit()
    return servicio


def actualizar_servicio(db: Session, servicio_id: int, datos: schemas.ServicioUpdate) -> Servicio:
    """Las citas ya agendadas conservan su precio y duración porque CitaServicio los copia al reservar (RF-09)."""
    servicio = _servicio_activo(db, servicio_id)
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(servicio, campo, valor)
    db.commit()
    return servicio


def eliminar_servicio(db: Session, servicio_id: int) -> Servicio:
    servicio = _servicio_activo(db, servicio_id)
    servicio.activo = False
    db.commit()
    return servicio


def calcular_resumen(db: Session, servicios_ids: List[int]) -> dict:
    """RF-15: total a pagar y duración total de los servicios elegidos."""
    servicios = obtener_servicios_activos(db, servicios_ids)
    return {
        "servicios": servicios,
        "total": sum((s.precio for s in servicios), Decimal("0")),
        "duracion_total_minutos": sum(s.duracion_minutos for s in servicios),
    }


# ==========================================
# Disponibilidad y bloqueos del barbero (RF-11, RF-12)
# ==========================================
def listar_disponibilidad(db: Session, usuario: Usuario) -> List[Disponibilidad]:
    barbero = _barbero_de_usuario(db, usuario)
    return db.query(Disponibilidad).filter(Disponibilidad.barbero_id == barbero.id).order_by(
        Disponibilidad.dia_semana, Disponibilidad.hora_inicio
    ).all()


def agregar_disponibilidad(db: Session, usuario: Usuario, datos: schemas.DisponibilidadCreate) -> Disponibilidad:
    """Un rango que se solapa con otro del mismo día se rechaza; uno contiguo se une al existente."""
    barbero = _barbero_de_usuario(db, usuario)
    existentes = db.query(Disponibilidad).filter(
        Disponibilidad.barbero_id == barbero.id, Disponibilidad.dia_semana == datos.dia_semana
    ).all()
    if any(hay_solapamiento(datos.hora_inicio, datos.hora_fin, d.hora_inicio, d.hora_fin) for d in existentes):
        raise Conflicto("Ese horario se cruza con otro que ya definiste para el mismo día.")

    inicio, fin = datos.hora_inicio, datos.hora_fin
    for d in existentes:
        if d.hora_fin == inicio:
            inicio = d.hora_inicio
            db.delete(d)
        elif d.hora_inicio == fin:
            fin = d.hora_fin
            db.delete(d)
    nueva = Disponibilidad(barbero_id=barbero.id, dia_semana=datos.dia_semana, hora_inicio=inicio, hora_fin=fin)
    db.add(nueva)
    db.commit()
    return nueva


def eliminar_disponibilidad(db: Session, usuario: Usuario, disponibilidad_id: int) -> None:
    barbero = _barbero_de_usuario(db, usuario)
    registro = db.query(Disponibilidad).filter(
        Disponibilidad.id == disponibilidad_id, Disponibilidad.barbero_id == barbero.id
    ).first()
    if registro is None:
        raise NoEncontrado("El horario no existe.")
    db.delete(registro)
    db.commit()


def listar_bloqueos(db: Session, usuario: Usuario) -> List[Bloqueo]:
    """Bloqueos de hoy en adelante."""
    barbero = _barbero_de_usuario(db, usuario)
    return db.query(Bloqueo).filter(
        Bloqueo.barbero_id == barbero.id, Bloqueo.fecha >= ahora_colombia().date()
    ).order_by(Bloqueo.fecha, Bloqueo.hora_inicio).all()


def agregar_bloqueo(db: Session, usuario: Usuario, datos: schemas.BloqueoCreate) -> Bloqueo:
    barbero = _barbero_de_usuario(db, usuario)
    if datos.fecha < ahora_colombia().date():
        raise ReglaIncumplida("La fecha no es válida: ya pasó.")  # CA-12.2

    # No se bloquea un horario donde ya hay citas programadas: el barbero no puede cancelarlas antes de su hora (PN-06)
    citas = db.query(Cita).filter(
        Cita.barbero_id == barbero.id, Cita.fecha == datos.fecha, Cita.estado == ESTADO_PROGRAMADA
    ).all()
    en_conflicto = [
        c.codigo_reserva for c in citas
        if datos.hora_inicio is None or hay_solapamiento(datos.hora_inicio, datos.hora_fin, c.hora_inicio, c.hora_fin)
    ]
    if en_conflicto:
        raise Conflicto(
            "No se puede bloquear: hay citas programadas en ese horario (" + ", ".join(en_conflicto) + ").",
            codigos=en_conflicto,
        )

    bloqueo = Bloqueo(
        barbero_id=barbero.id, fecha=datos.fecha, hora_inicio=datos.hora_inicio, hora_fin=datos.hora_fin
    )
    db.add(bloqueo)
    db.commit()
    return bloqueo


def eliminar_bloqueo(db: Session, usuario: Usuario, bloqueo_id: int) -> None:
    barbero = _barbero_de_usuario(db, usuario)
    registro = db.query(Bloqueo).filter(Bloqueo.id == bloqueo_id, Bloqueo.barbero_id == barbero.id).first()
    if registro is None:
        raise NoEncontrado("El bloqueo no existe.")
    db.delete(registro)
    db.commit()


# ==========================================
# Horarios libres y agendamiento (RF-16 a RF-21)
# ==========================================
def _cargar_agenda(
    db: Session, barbero_id: int, fecha: datetime.date,
    excluir_cita_id: Optional[int] = None, bloquear: bool = False,
):
    """Disponibilidad, bloqueos y citas del barbero en un día. Una cita cancelada libera el horario;
    las atendidas y las de inasistencia siguen ocupándolo. Con bloquear=True las citas se leen con
    SELECT ... FOR UPDATE, para ver lo último confirmado por otras reservas (en SQLite no tiene efecto)."""
    rangos = db.query(Disponibilidad).filter(
        Disponibilidad.barbero_id == barbero_id, Disponibilidad.dia_semana == fecha.weekday()
    ).all()
    bloqueos = db.query(Bloqueo).filter(Bloqueo.barbero_id == barbero_id, Bloqueo.fecha == fecha).all()
    consulta = db.query(Cita).filter(
        Cita.barbero_id == barbero_id, Cita.fecha == fecha, Cita.estado != ESTADO_CANCELADA
    )
    if excluir_cita_id is not None:
        consulta = consulta.filter(Cita.id != excluir_cita_id)
    if bloquear:
        consulta = consulta.with_for_update()
    return rangos, bloqueos, consulta.all()


def _motivo_no_disponible(agenda, inicio: datetime.time, fin: datetime.time) -> Optional[str]:
    """Única regla de "horario libre", compartida por la consulta (RF-18) y por el agendamiento (RF-20)."""
    rangos, bloqueos, citas = agenda
    if not any(r.hora_inicio <= inicio and fin <= r.hora_fin for r in rangos):
        return "El barbero no atiende en ese horario."
    for b in bloqueos:
        if b.hora_inicio is None or hay_solapamiento(inicio, fin, b.hora_inicio, b.hora_fin):
            return "El barbero tiene bloqueado ese horario."
    if any(hay_solapamiento(inicio, fin, c.hora_inicio, c.hora_fin) for c in citas):
        return "El horario ya no está disponible."
    return None


def _exigir_intervalo(hora_inicio: datetime.time) -> None:
    """PN-02. Se valida después del solapamiento para que 10:15 sobre una cita de 10:00 a 10:30 responda 409 (CA-20.3)."""
    if hora_inicio.minute % politicas.INTERVALO_MINUTOS or hora_inicio.second or hora_inicio.microsecond:
        raise ReglaIncumplida(
            f"La hora de inicio debe coincidir con intervalos de {politicas.INTERVALO_MINUTOS} minutos (ej. 08:00, 08:30)."
        )


def _horarios_libres(
    db: Session, barbero_id: int, fecha: datetime.date, franja: str, duracion_minutos: int,
    excluir_cita_id: Optional[int] = None,
) -> List[dict]:
    ahora = ahora_colombia()
    if fecha < ahora.date():
        raise ReglaIncumplida("No se pueden consultar horarios de una fecha que ya pasó.")  # CA-16.2
    _barbero_activo(db, barbero_id)

    agenda = _cargar_agenda(db, barbero_id, fecha, excluir_cita_id)
    inicio_franja, fin_franja = politicas.FRANJAS[franja]
    duracion = datetime.timedelta(minutes=duracion_minutos)
    paso = datetime.timedelta(minutes=politicas.INTERVALO_MINUTOS)

    libres = {}
    for rango in agenda[0]:
        cursor = datetime.datetime.combine(fecha, rango.hora_inicio)
        limite = datetime.datetime.combine(fecha, rango.hora_fin)
        while cursor + duracion <= limite:
            inicio, fin = cursor.time(), (cursor + duracion).time()
            if (
                inicio_franja <= inicio < fin_franja  # la franja se decide por la hora de inicio (PN-03)
                and cursor > ahora
                and _motivo_no_disponible(agenda, inicio, fin) is None
            ):
                libres[inicio] = {
                    "hora_inicio": inicio.strftime("%H:%M"),
                    "hora_fin": fin.strftime("%H:%M"),
                    "disponible": True,
                    "motivo": None,
                }
            cursor += paso
    return [libres[hora] for hora in sorted(libres)]


def consultar_disponibilidad(
    db: Session, barbero_id: int, fecha: datetime.date, franja: str, servicios_ids: List[int]
) -> List[dict]:
    """RF-16 a RF-18: solo los horarios libres de la franja que alcanzan para la duración total."""
    servicios = obtener_servicios_activos(db, servicios_ids)
    return _horarios_libres(db, barbero_id, fecha, franja, sum(s.duracion_minutos for s in servicios))


# Las reservas de un mismo barbero se atienden una a la vez (RF-20, CA-20.2). El candado cubre las
# peticiones del mismo proceso (SQLite no soporta bloqueos de fila) y SELECT ... FOR UPDATE sobre la fila
# del barbero cubre varios procesos con MySQL o MariaDB.
_CANDADO_AGENDA = threading.Lock()


@contextmanager
def _seccion_critica(db: Session):
    with _CANDADO_AGENDA:
        try:
            yield
        except BaseException:
            db.rollback()  # libera los bloqueos de fila si la operación falla
            raise


def _bloquear_barbero(db: Session, barbero_id: int) -> Barbero:
    barbero = (
        db.query(Barbero).options(lazyload(Barbero.usuario))
        .filter(Barbero.id == barbero_id, Barbero.activo == True)  # noqa: E712
        .with_for_update().first()
    )
    if barbero is None:
        raise NoEncontrado("El barbero no existe o no está activo.")
    return barbero


def _generar_codigo_unico(db: Session) -> str:
    for _ in range(10):
        codigo = generar_codigo_reserva()
        if db.query(Cita.id).filter(Cita.codigo_reserva == codigo).first() is None:
            return codigo
    raise RuntimeError("No se pudo generar un código de reserva único.")


def agendar_cita(db: Session, cliente: Usuario, datos: schemas.CitaCreate) -> Cita:
    """RF-19 y RF-20. Orden de las validaciones: 404, 400 (pasado), 403 (suspendido), 409 (límite),
    409 (horario no disponible o con choque) y 400 (fuera del intervalo de PN-02)."""
    with _seccion_critica(db):
        _bloquear_barbero(db, datos.barbero_id)  # primero el bloqueo, antes de leer el resto
        servicios = obtener_servicios_activos(db, datos.servicios_ids)

        ahora = ahora_colombia()
        if datetime.datetime.combine(datos.fecha, datos.hora_inicio) <= ahora:
            raise ReglaIncumplida("No se puede agendar en una fecha u hora que ya pasó.")  # CA-16.2
        if _esta_suspendido(cliente, ahora.date()):
            raise Prohibido(
                f"Tu cuenta está suspendida hasta el {cliente.suspendido_hasta.strftime('%d/%m/%Y')}.",
                suspendido_hasta=cliente.suspendido_hasta.isoformat(),
            )  # CA-30.3
        activas = db.query(func.count(Cita.id)).filter(
            Cita.cliente_id == cliente.id, Cita.estado == ESTADO_PROGRAMADA
        ).scalar()
        if activas >= politicas.MAX_CITAS_ACTIVAS:
            raise Conflicto(f"Alcanzaste el límite de {politicas.MAX_CITAS_ACTIVAS} citas activas.")  # CA-19.2

        duracion = sum(s.duracion_minutos for s in servicios)
        hora_fin = calcular_hora_fin(datos.hora_inicio, duracion)  # CA-19.3
        if hora_fin <= datos.hora_inicio:  # la cita pasaría de medianoche
            raise Conflicto("El barbero no atiende en ese horario.")
        agenda = _cargar_agenda(db, datos.barbero_id, datos.fecha, bloquear=True)
        motivo = _motivo_no_disponible(agenda, datos.hora_inicio, hora_fin)
        if motivo:
            raise Conflicto(motivo)  # CA-20.2, CA-20.3
        _exigir_intervalo(datos.hora_inicio)

        cita = Cita(
            codigo_reserva=_generar_codigo_unico(db),
            cliente_id=cliente.id,
            barbero_id=datos.barbero_id,
            fecha=datos.fecha,
            hora_inicio=datos.hora_inicio,
            hora_fin=hora_fin,
            estado=ESTADO_PROGRAMADA,
            total=sum((s.precio for s in servicios), Decimal("0")),
            notas=datos.notas,
            servicios=[
                CitaServicio(servicio_id=s.id, precio_aplicado=s.precio, duracion_minutos=s.duracion_minutos)
                for s in servicios
            ],
        )
        db.add(cita)
        db.commit()

    _notificar(notificaciones.confirmacion_cita, cita)  # RF-21: solo si la cita se creó
    return cita


# ==========================================
# Gestión de citas del cliente (RF-22 a RF-25)
# ==========================================
def listar_mis_citas(db: Session, cliente: Usuario) -> List[Cita]:
    return db.query(Cita).filter(Cita.cliente_id == cliente.id).order_by(
        Cita.fecha.desc(), Cita.hora_inicio.desc()
    ).all()


def obtener_cita_visible(db: Session, usuario: Usuario, cita_id: int) -> Cita:
    """El cliente solo ve las suyas y el barbero las de su agenda (CA-22.2); el administrador ve todas."""
    cita = _obtener_cita(db, cita_id)
    if usuario.rol == ROL_ADMIN:
        return cita
    if usuario.rol == ROL_CLIENTE and cita.cliente_id == usuario.id:
        return cita
    if usuario.rol == ROL_BARBERO and cita.barbero.usuario_id == usuario.id:
        return cita
    raise Prohibido("No tienes permiso para ver esta cita.")


def _obtener_cita_del_cliente(db: Session, cliente: Usuario, cita_id: int, bloquear: bool = False) -> Cita:
    cita = _obtener_cita(db, cita_id, bloquear)
    if cita.cliente_id != cliente.id:
        raise Prohibido("No tienes permiso para modificar esta cita.")
    return cita


def _exigir_anticipacion(cita: Cita, ahora: datetime.datetime, accion: str) -> None:
    """PN-04 y PN-05: con exactamente 12 horas de anticipación sí se permite."""
    if _inicio_de_cita(cita) - ahora < politicas.ANTICIPACION_MINIMA:
        horas = int(politicas.ANTICIPACION_MINIMA.total_seconds() // 3600)
        raise ReglaIncumplida(f"El límite para {accion} expiró: debe hacerse con al menos {horas} horas de anticipación.")


def cancelar_cita(db: Session, cliente: Usuario, cita_id: int) -> Cita:
    cita = _obtener_cita_del_cliente(db, cliente, cita_id)
    if cita.estado != ESTADO_PROGRAMADA:
        raise ReglaIncumplida(f"La cita está en estado '{cita.estado}' y ya no se puede cancelar.")  # CP-RF23-3
    _exigir_anticipacion(cita, ahora_colombia(), "cancelar")  # CA-23.2
    cita.estado = ESTADO_CANCELADA
    db.commit()
    _notificar(notificaciones.cita_cancelada, cita)  # RF-25: no se envía si se rechazó (CA-25.2)
    return cita


def _exigir_reprogramable(cita: Cita, ahora: datetime.datetime) -> None:
    if cita.estado != ESTADO_PROGRAMADA:
        raise ReglaIncumplida(f"La cita está en estado '{cita.estado}' y ya no se puede reprogramar.")
    if cita.reprogramada:
        raise ReglaIncumplida("Esta cita ya fue reprogramada una vez; no se puede reprogramar de nuevo.")  # CA-24.2
    _exigir_anticipacion(cita, ahora, "reprogramar")  # CA-24.3


def horarios_para_reprogramar(
    db: Session, cliente: Usuario, cita_id: int, fecha: datetime.date, franja: str
) -> List[dict]:
    """Horarios libres del mismo barbero para la misma duración. El horario actual de la cita cuenta como libre."""
    cita = _obtener_cita_del_cliente(db, cliente, cita_id)
    _exigir_reprogramable(cita, ahora_colombia())
    duracion = sum(cs.duracion_minutos for cs in cita.servicios)
    return _horarios_libres(db, cita.barbero_id, fecha, franja, duracion, excluir_cita_id=cita.id)


def reprogramar_cita(db: Session, cliente: Usuario, cita_id: int, datos: schemas.CitaReprogramar) -> Cita:
    with _seccion_critica(db):
        cita = _obtener_cita_del_cliente(db, cliente, cita_id, bloquear=True)
        _bloquear_barbero(db, cita.barbero_id)
        ahora = ahora_colombia()
        _exigir_reprogramable(cita, ahora)
        if datetime.datetime.combine(datos.fecha, datos.hora_inicio) <= ahora:
            raise ReglaIncumplida("No se puede reprogramar a una fecha u hora que ya pasó.")

        hora_fin = calcular_hora_fin(datos.hora_inicio, sum(cs.duracion_minutos for cs in cita.servicios))
        if hora_fin <= datos.hora_inicio:
            raise Conflicto("El barbero no atiende en ese horario.")
        agenda = _cargar_agenda(db, cita.barbero_id, datos.fecha, excluir_cita_id=cita.id, bloquear=True)
        motivo = _motivo_no_disponible(agenda, datos.hora_inicio, hora_fin)
        if motivo:
            raise Conflicto(motivo)
        _exigir_intervalo(datos.hora_inicio)

        fecha_anterior, hora_anterior = cita.fecha, cita.hora_inicio
        cita.fecha, cita.hora_inicio, cita.hora_fin = datos.fecha, datos.hora_inicio, hora_fin
        cita.reprogramada = True
        db.commit()

    _notificar(notificaciones.cita_reprogramada, cita, fecha_anterior, hora_anterior)
    return cita


# ==========================================
# Atención de citas del barbero (RF-26, RF-27, RF-29)
# ==========================================
def agenda_barbero(db: Session, usuario: Usuario, fecha: Optional[datetime.date], vista: str) -> List[Cita]:
    """Citas del barbero en orden cronológico. Sin fecha, la de hoy. La semana va de lunes a domingo."""
    barbero = _barbero_de_usuario(db, usuario)
    fecha = fecha or ahora_colombia().date()
    desde = fecha - datetime.timedelta(days=fecha.weekday()) if vista == "semana" else fecha
    hasta = desde + datetime.timedelta(days=6) if vista == "semana" else fecha
    return db.query(Cita).filter(
        Cita.barbero_id == barbero.id, Cita.fecha >= desde, Cita.fecha <= hasta
    ).order_by(Cita.fecha, Cita.hora_inicio).all()


def actualizar_estado_cita(db: Session, usuario: Usuario, cita_id: int, estado: str) -> Cita:
    barbero = _barbero_de_usuario(db, usuario)
    cita = _obtener_cita(db, cita_id)
    if cita.barbero_id != barbero.id:
        raise Prohibido("Esta cita no pertenece a tu agenda.")
    if cita.estado != ESTADO_PROGRAMADA:  # CA-27.3: Atendida, Cancelada e Inasistencia son estados terminales
        raise ReglaIncumplida(f"La cita ya está en estado '{cita.estado}' y no se puede modificar.")
    if ahora_colombia() < _inicio_de_cita(cita):  # CA-27.2, PN-06
        raise ReglaIncumplida("La cita aún no ha empezado; solo se puede cambiar su estado desde la hora de inicio.")

    cita.estado = estado
    if estado == ESTADO_INASISTENCIA:
        _aplicar_sancion(db, cita)
    db.commit()
    if estado == ESTADO_CANCELADA:
        _notificar(notificaciones.cita_cancelada, cita)
    return cita


def _aplicar_sancion(db: Session, cita: Cita) -> None:
    """RF-29 y PN-10. Cuenta las inasistencias del cliente de los últimos 3 meses (contados desde la fecha
    de esta cita, con el límite incluido) que sean posteriores al fin de la última suspensión, porque al
    terminar la suspensión el contador vuelve a cero. Con 2 o más, suspende la cuenta 1 mes. Mientras dura una
    suspensión no se suma nada, así que una inasistencia de ese tiempo no la extiende."""
    cliente = cita.cliente
    hoy = ahora_colombia().date()
    desde = sumar_meses(cita.fecha, -politicas.MESES_VENTANA_INASISTENCIAS)
    if cliente.suspendido_hasta is not None:
        desde = max(desde, cliente.suspendido_hasta)

    db.flush()  # la sesión no hace autoflush: así la consulta ya cuenta la inasistencia recién marcada
    inasistencias = db.query(func.count(Cita.id)).filter(
        Cita.cliente_id == cliente.id, Cita.estado == ESTADO_INASISTENCIA, Cita.fecha >= desde
    ).scalar()
    if inasistencias >= politicas.INASISTENCIAS_PARA_SUSPENDER:
        cliente.suspendido_hasta = sumar_meses(hoy, politicas.MESES_SUSPENSION)
        _cerrar_sesiones(db, cliente.id)  # no puede seguir usando la aplicación durante la suspensión


# ==========================================
# Consulta general (RF-28)
# ==========================================
def listar_citas(
    db: Session, barbero_id: Optional[int] = None, fecha: Optional[datetime.date] = None,
    estado: Optional[str] = None,
) -> List[Cita]:
    consulta = db.query(Cita)
    if barbero_id is not None:
        consulta = consulta.filter(Cita.barbero_id == barbero_id)
    if fecha is not None:
        consulta = consulta.filter(Cita.fecha == fecha)
    if estado is not None:
        consulta = consulta.filter(Cita.estado == estado)
    return consulta.order_by(Cita.fecha, Cita.hora_inicio).all()
