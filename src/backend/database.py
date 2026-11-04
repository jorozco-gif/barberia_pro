import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

# Si no se define DATABASE_URL en el entorno, se usa SQLite local automáticamente
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./barberia.db")

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args)

if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def activar_claves_foraneas(dbapi_connection, connection_record):
        # RNF-07: SQLite no aplica las claves foráneas por defecto. Sin esto, el RESTRICT
        # de barberos y servicios con citas y las claves foráneas de las citas no se cumplirían.
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """Generador de sesión de base de datos para inyección de dependencias."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
