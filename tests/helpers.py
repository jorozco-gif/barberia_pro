"""Funciones auxiliares para armar los datos de las pruebas."""
import datetime
from decimal import Decimal

import models
import security

CLAVE = "Clave#1234"


def hora(texto: str) -> datetime.time:
    return datetime.time.fromisoformat(texto)


def _crear_usuario(db, rol, email, nombre, telefono=None, password=CLAVE) -> models.Usuario:
    usuario = models.Usuario(
        nombre=nombre, telefono=telefono, email=email,
        password_hash=security.hash_password(password), rol=rol, activo=True,
    )
    db.add(usuario)
    db.commit()
    return usuario


def crear_cliente(db, email="cliente@test.com", nombre="Ana Cliente") -> models.Usuario:
    return _crear_usuario(db, models.ROL_CLIENTE, email, nombre, telefono="3001234567")


def crear_admin(db, email="admin@test.com") -> models.Usuario:
    return _crear_usuario(db, models.ROL_ADMIN, email, "Administrador")


def crear_barbero(db, email="mateo@test.com", nombre="Mateo Maestro", horario=True) -> models.Barbero:
    """Barbero activo. Con horario=True atiende de lunes a sábado de 08:00 a 20:00."""
    usuario = models.Usuario(
        nombre=nombre, email=email, password_hash=security.hash_password(CLAVE),
        rol=models.ROL_BARBERO, activo=True,
    )
    barbero = models.Barbero(usuario=usuario, activo=True)
    if horario:
        barbero.disponibilidades = [
            models.Disponibilidad(dia_semana=d, hora_inicio=hora("08:00"), hora_fin=hora("20:00"))
            for d in range(0, 6)
        ]
    db.add(barbero)
    db.commit()
    return barbero


def crear_servicio(db, nombre="Corte", duracion=30, precio="20000") -> models.Servicio:
    servicio = models.Servicio(nombre=nombre, duracion_minutos=duracion, precio=Decimal(precio), activo=True)
    db.add(servicio)
    db.commit()
    return servicio


def crear_cita(
    db, cliente, barbero, servicios, fecha, hora_inicio, estado=models.ESTADO_PROGRAMADA, codigo=None,
) -> models.Cita:
    """Inserta una cita directamente en la base de datos, sin pasar por las reglas de agendamiento."""
    if isinstance(hora_inicio, str):
        hora_inicio = hora(hora_inicio)
    if not isinstance(servicios, (list, tuple)):
        servicios = [servicios]
    duracion = sum(s.duracion_minutos for s in servicios)
    fin = (datetime.datetime.combine(fecha, hora_inicio) + datetime.timedelta(minutes=duracion)).time()
    cita = models.Cita(
        codigo_reserva=codigo or f"BSP-{abs(hash((fecha, hora_inicio, barbero.id, cliente.id, estado))) % 16**6:06X}",
        cliente_id=cliente.id, barbero_id=barbero.id,
        fecha=fecha, hora_inicio=hora_inicio, hora_fin=fin, estado=estado,
        total=sum((s.precio for s in servicios), Decimal("0")),
        servicios=[
            models.CitaServicio(servicio_id=s.id, precio_aplicado=s.precio, duracion_minutos=s.duracion_minutos)
            for s in servicios
        ],
    )
    db.add(cita)
    db.commit()
    return cita


def iniciar_sesion(client, email, password=CLAVE) -> dict:
    """Inicia sesión por la API y devuelve las cabeceras de autorización."""
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def agendar(client, headers, barbero, servicios, fecha, hora_inicio, **extra):
    """POST /api/citas. `servicios` puede ser un servicio o una lista."""
    if not isinstance(servicios, (list, tuple)):
        servicios = [servicios]
    cuerpo = {
        "barbero_id": barbero.id,
        "servicios_ids": [s.id for s in servicios],
        "fecha": fecha.isoformat(),
        "hora_inicio": hora_inicio,
    }
    cuerpo.update(extra)
    return client.post("/api/citas", json=cuerpo, headers=headers)
