import sys
import os
import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Agregar src/backend al PYTHONPATH para importar módulos
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from database import Base, get_db
from main import app
import models


# Base de datos SQLite en memoria compartida para pruebas ultrarrápidas
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Crea una base de datos limpia para cada prueba unitaria."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Cliente HTTP de pruebas de FastAPI con inyección de la base de datos de test."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def setup_datos_base(db_session):
    """Crea un barbero y un servicio iniciales para agilizar las pruebas de citas."""
    barbero1 = models.Barbero(
        nombre="Mateo Maestro",
        especialidad="Cortes clásicos",
        email="mateo@test.com",
        telefono="3001112233",
        activo=True
    )
    barbero2 = models.Barbero(
        nombre="Carlos Barba",
        especialidad="Barba Spa",
        email="carlos@test.com",
        telefono="3004445566",
        activo=True
    )
    servicio = models.Servicio(
        nombre="Corte de Cabello",
        descripcion="Corte regular 30 minutos",
        duracion_minutos=30,
        precio=Decimal("15.00"),
        activo=True
    )
    db_session.add_all([barbero1, barbero2, servicio])
    db_session.commit()
    db_session.refresh(barbero1)
    db_session.refresh(barbero2)
    db_session.refresh(servicio)

    return {
        "barbero1": barbero1,
        "barbero2": barbero2,
        "servicio": servicio
    }
