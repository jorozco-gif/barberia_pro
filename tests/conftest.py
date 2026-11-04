"""Configuración común de las pruebas (docs/plan-de-pruebas.md, sección 4).

- Base de datos SQLite temporal, distinta a la de desarrollo. Se define DATABASE_URL antes de importar el
  backend para que database.py cree el motor con la base de pruebas y aplique el PRAGMA de claves foráneas (RNF-07).
  Se usa un archivo temporal y no ':memory:' porque el cliente de pruebas atiende cada petición en otro hilo
  y cada hilo vería su propia base de datos en memoria.
- Reloj controlado: todas las reglas de tiempo (12 horas, 15 minutos, 1 hora, 3 meses) usan services.ahora_colombia().
- Correo: no se envía; los mensajes se guardan en la lista del fixture `correos`.
"""
import datetime
import os
import sys
import tempfile

import pytest

_DIRECTORIO_TEMPORAL = tempfile.mkdtemp(prefix="barbershop_pruebas_")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_DIRECTORIO_TEMPORAL, 'pruebas.db')}"

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from argon2 import PasswordHasher  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import database  # noqa: E402
import notificaciones  # noqa: E402
import security  # noqa: E402
import services  # noqa: E402
from main import app  # noqa: E402

import helpers  # noqa: E402

ENVIAR_REAL = notificaciones.enviar  # la función de envío sin sustituir, para probarla por separado

# Argon2 con parámetros mínimos solo para que las pruebas sean rápidas. Los hashes que genera siguen siendo
# Argon2id y se verifican igual; en producción se usan los parámetros por defecto de security.py.
security._hasher = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)


class Reloj:
    """Lunes 7 de enero de 2030, 8:00 a. m. (hora de Colombia)."""

    def __init__(self):
        self.ahora = datetime.datetime(2030, 1, 7, 8, 0)

    def avanzar(self, **kwargs):
        self.ahora += datetime.timedelta(**kwargs)

    def en(self, dias=0, hora=None):
        """Fecha (o fecha y hora) relativa a ahora."""
        dia = self.ahora.date() + datetime.timedelta(days=dias)
        return dia if hora is None else datetime.datetime.combine(dia, hora)


@pytest.fixture(autouse=True)
def reloj(monkeypatch):
    r = Reloj()
    monkeypatch.setattr(services, "ahora_colombia", lambda: r.ahora)
    return r


@pytest.fixture(autouse=True)
def correos(monkeypatch):
    enviados = []
    monkeypatch.setattr(
        notificaciones, "enviar",
        lambda para, asunto, cuerpo: enviados.append({"para": para, "asunto": asunto, "cuerpo": cuerpo}),
    )
    return enviados


@pytest.fixture(autouse=True)
def base_limpia():
    database.Base.metadata.drop_all(bind=database.engine)
    database.Base.metadata.create_all(bind=database.engine)
    yield
    database.Base.metadata.drop_all(bind=database.engine)


@pytest.fixture
def db():
    sesion = database.SessionLocal()
    try:
        yield sesion
    finally:
        sesion.close()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def cliente(db):
    return helpers.crear_cliente(db, "cliente@test.com", "Ana Cliente")


@pytest.fixture
def otro_cliente(db):
    return helpers.crear_cliente(db, "otro@test.com", "Beto Cliente")


@pytest.fixture
def barbero(db):
    return helpers.crear_barbero(db, "mateo@test.com", "Mateo Maestro")


@pytest.fixture
def otro_barbero(db):
    return helpers.crear_barbero(db, "carlos@test.com", "Carlos Barba")


@pytest.fixture
def admin(db):
    return helpers.crear_admin(db, "admin@test.com")


@pytest.fixture
def corte(db):
    """Servicio de 30 minutos y $20.000."""
    return helpers.crear_servicio(db, "Corte", 30, "20000")


@pytest.fixture
def barba(db):
    """Servicio de 15 minutos y $10.000."""
    return helpers.crear_servicio(db, "Barba", 15, "10000")


@pytest.fixture
def h_cliente(client, cliente):
    return helpers.iniciar_sesion(client, cliente.email)


@pytest.fixture
def h_otro_cliente(client, otro_cliente):
    return helpers.iniciar_sesion(client, otro_cliente.email)


@pytest.fixture
def h_barbero(client, barbero):
    return helpers.iniciar_sesion(client, barbero.email)


@pytest.fixture
def h_otro_barbero(client, otro_barbero):
    return helpers.iniciar_sesion(client, otro_barbero.email)


@pytest.fixture
def h_admin(client, admin):
    return helpers.iniciar_sesion(client, admin.email)
