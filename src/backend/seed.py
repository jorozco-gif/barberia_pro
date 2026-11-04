import datetime
import os
import secrets
import sys
from decimal import Decimal

try:  # Si está python-dotenv, se leen las variables del archivo .env (RNF-10: el .env no se versiona)
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from sqlalchemy import inspect

from database import SessionLocal, engine, Base
import models
from security import hash_password

# Horario de ejemplo de los barberos: lunes a sábado de 09:00 a 20:00 (el horario comercial de la v1.0).
# Cada barbero lo puede cambiar luego desde su cuenta (RF-11).
DIAS_ATENCION = range(0, 6)  # 0 = lunes ... 5 = sábado
HORA_APERTURA = datetime.time(9, 0)
HORA_CIERRE = datetime.time(20, 0)

# (nombre, correo, teléfono)
BARBEROS_EJEMPLO = [
    ("Mateo 'El Maestro' Sánchez", "mateo@barbershop.pro", "3101234567"),
    ("Carlos 'The Beard' Delgado", "carlos@barbershop.pro", "3119876543"),
    ("Lucas 'Urban' Romero", "lucas@barbershop.pro", "3125558899"),
]

# (nombre, duración en minutos, precio en pesos). Precios de ejemplo, el dueño de la barbería los confirma (PN-12).
SERVICIOS_EJEMPLO = [
    ("Corte Clásico", 30, Decimal("20000")),
    ("Barba Spa", 30, Decimal("15000")),
    ("Combo Corte + Barba", 45, Decimal("30000")),
    ("Perfilado y Cejas", 30, Decimal("10000")),
    ("Colorimetría y Platinado", 45, Decimal("45000")),
]


def _verificar_base_v11():
    """Si la base viene de la v1.0, create_all no la actualiza y fallaría más adelante de forma confusa."""
    inspector = inspect(engine)
    if inspector.has_table("barberos"):
        columnas = {c["name"] for c in inspector.get_columns("barberos")}
        if "nombre" in columnas:
            print(
                "Esta base de datos es de la v1.0. Borra el archivo .db y vuelve a ejecutar el seed.",
                file=sys.stderr,
            )
            sys.exit(1)


def _obtener_password(variable: str, para: str) -> str:
    """RNF-10: las contraseñas no van en el código. Se leen de una variable de entorno;
    si no existe, se genera una aleatoria y se muestra una sola vez en consola."""
    valor = os.getenv(variable)
    if valor:
        if len(valor) < 8:
            raise ValueError(f"{variable} debe tener al menos 8 caracteres.")
        return valor
    generada = secrets.token_urlsafe(12)
    print(f"Contraseña generada para {para}: {generada}  (guárdala, no se vuelve a mostrar)")
    return generada


def crear_administrador(db):
    # PN-13: la cuenta inicial del administrador la crea el programador y se la entrega al administrador
    email = os.getenv("SEED_ADMIN_EMAIL", "admin@barbershop.pro")
    if db.query(models.Usuario).filter_by(email=email).first():
        print(f"El administrador {email} ya existe.")
        return
    password = _obtener_password("SEED_ADMIN_PASSWORD", f"el administrador ({email})")
    db.add(models.Usuario(
        nombre="Administrador",
        email=email,
        password_hash=hash_password(password),
        rol=models.ROL_ADMIN,
        activo=True,
    ))
    print(f"Administrador creado: {email}")


def crear_barberos(db):
    password = None  # se pide solo si hay algún barbero por crear
    for nombre, email, telefono in BARBEROS_EJEMPLO:
        if db.query(models.Usuario).filter_by(email=email).first():
            continue
        if password is None:
            password = _obtener_password("SEED_BARBEROS_PASSWORD", "los barberos de ejemplo")
        usuario = models.Usuario(
            nombre=nombre,
            telefono=telefono,
            email=email,
            password_hash=hash_password(password),
            rol=models.ROL_BARBERO,
            activo=True,
        )
        barbero = models.Barbero(usuario=usuario, activo=True)
        barbero.disponibilidades = [
            models.Disponibilidad(dia_semana=dia, hora_inicio=HORA_APERTURA, hora_fin=HORA_CIERRE)
            for dia in DIAS_ATENCION
        ]
        db.add(barbero)
        print(f"Barbero agregado: {nombre}")


def crear_servicios(db):
    for nombre, duracion, precio in SERVICIOS_EJEMPLO:
        if db.query(models.Servicio).filter_by(nombre=nombre).first():
            continue
        db.add(models.Servicio(nombre=nombre, duracion_minutos=duracion, precio=precio, activo=True))
        print(f"Servicio agregado: {nombre}")


def poblar_datos_iniciales():
    _verificar_base_v11()
    # Asegurar que las tablas existan
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        crear_administrador(db)
        crear_barberos(db)
        crear_servicios(db)
        db.commit()
        print("Base de datos poblada exitosamente.")

    except Exception as e:
        db.rollback()
        print(f"Error al poblar la base de datos: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    poblar_datos_iniciales()