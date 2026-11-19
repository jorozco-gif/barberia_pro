"""Migración v1.1 -> v1.2 (migrar.py y migraciones/v1_2_sqlite.sql) sobre una base SQLite con datos reales.

La base v1.1 se arma con el esquema actual sin lo que agrega la v1.2: la tabla estilos y las columnas
servicios.descripcion y citas.estilo_id.
"""
import os
import sqlite3

import pytest
from sqlalchemy import MetaData, Table, create_engine, event, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import database
import migrar
import models
import seed

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "backend"))
NUEVAS_COLUMNAS = {("servicios", "descripcion"), ("citas", "estilo_id")}


def _motor(ruta):
    motor = create_engine(f"sqlite:///{ruta}")

    @event.listens_for(motor, "connect")
    def activar_claves_foraneas(conexion, _registro):  # igual que database.py (RNF-07)
        conexion.execute("PRAGMA foreign_keys=ON")

    return motor


def _crear_base_v11(motor):
    viejo = MetaData()
    for nombre, tabla in database.Base.metadata.tables.items():
        if nombre == "estilos":
            continue
        Table(nombre, viejo, *[c._copy() for c in tabla.columns if (nombre, c.name) not in NUEVAS_COLUMNAS])
    viejo.create_all(motor)
    with motor.begin() as con:
        con.execute(text(
            "INSERT INTO usuarios (id, nombre, email, password_hash, rol, activo) VALUES "
            "(1, 'Ana', 'ana@test.com', 'x', 'cliente', 1), (2, 'Mateo', 'mateo@test.com', 'x', 'barbero', 1)"))
        con.execute(text("INSERT INTO barberos (id, usuario_id, activo) VALUES (1, 2, 1)"))
        con.execute(text(
            "INSERT INTO servicios (id, nombre, duracion_minutos, precio, activo) VALUES (1, 'Corte', 30, 20000, 1)"))
        con.execute(text(
            "INSERT INTO citas (id, codigo_reserva, cliente_id, barbero_id, fecha, hora_inicio, hora_fin, estado, "
            "total, reprogramada, notas, creada_el) VALUES (1, 'BSP-AAAAAA', 1, 1, '2030-01-08', '10:00:00.000000', "
            "'10:30:00.000000', 'Programada', 20000, 0, 'Degradado', '2030-01-07 08:00:00.000000')"))


def _columnas(motor, tabla):
    return {c["name"] for c in inspect(motor).get_columns(tabla)}


def _esquema_igual_al_modelo(motor):
    for tabla in ("estilos", "servicios", "citas"):
        assert _columnas(motor, tabla) == set(database.Base.metadata.tables[tabla].columns.keys()), tabla
    claves = inspect(motor).get_foreign_keys("citas")
    assert any(fk["referred_table"] == "estilos" and fk["constrained_columns"] == ["estilo_id"] for fk in claves)
    assert "ix_citas_estilo_id" in {i["name"] for i in inspect(motor).get_indexes("citas")}


def test_migrar_actualiza_una_base_v11_sin_perder_datos(tmp_path):
    motor = _motor(tmp_path / "v11.db")
    _crear_base_v11(motor)
    assert "estilos" not in inspect(motor).get_table_names()

    cambios = migrar.actualizar_esquema(motor)
    assert len(cambios) == 3, cambios
    _esquema_igual_al_modelo(motor)

    with Session(motor) as sesion:
        cita = sesion.get(models.Cita, 1)
        assert cita.notas == "Degradado" and cita.estilo_id is None  # el historial se conserva
        assert sesion.get(models.Servicio, 1).descripcion is None
        # El ORM de la v1.2 funciona sobre la base migrada
        estilo = models.Estilo(nombre="Fade bajo", descripcion="Degradado bajo.", activo=True)
        sesion.add(estilo)
        sesion.flush()
        cita.estilo_id = estilo.id
        sesion.get(models.Servicio, 1).descripcion = "Corte a tijera."
        sesion.commit()
        assert sesion.get(models.Cita, 1).estilo.nombre == "Fade bajo"
        cita.estilo_id = 999  # la clave foránea agregada por la migración se aplica
        with pytest.raises(IntegrityError):
            sesion.commit()
        sesion.rollback()

    assert migrar.actualizar_esquema(motor) == []  # idempotente


def test_migrar_sobre_una_base_vacia_la_crea_completa(tmp_path):
    motor = _motor(tmp_path / "nueva.db")
    assert migrar.actualizar_esquema(motor) == ["Base de datos nueva creada con el esquema v1.2."]
    _esquema_igual_al_modelo(motor)
    assert set(inspect(motor).get_table_names()) == set(database.Base.metadata.tables)
    assert migrar.actualizar_esquema(motor) == []


def test_el_script_sql_de_sqlite_deja_el_mismo_esquema(tmp_path):
    ruta = tmp_path / "manual.db"
    motor = _motor(ruta)
    _crear_base_v11(motor)
    motor.dispose()
    with open(os.path.join(BACKEND_DIR, "migraciones", "v1_2_sqlite.sql"), encoding="utf-8") as f:
        script = f.read()
    conexion = sqlite3.connect(ruta)
    try:
        conexion.executescript(script)
        assert conexion.execute("SELECT COUNT(*) FROM estilos WHERE activo = 1").fetchone()[0] == len(seed.ESTILOS_EJEMPLO)
        assert conexion.execute("SELECT notas, estilo_id FROM citas WHERE id = 1").fetchone() == ("Degradado", None)
    finally:
        conexion.close()
    _esquema_igual_al_modelo(motor)
    assert migrar.actualizar_esquema(motor) == []  # migrar.py reconoce la base ya migrada a mano


def test_el_script_sql_de_mysql_tiene_los_mismos_cambios():
    with open(os.path.join(BACKEND_DIR, "migraciones", "v1_2_mysql.sql"), encoding="utf-8") as f:
        script = " ".join(f.read().split())
    for cambio in ("CREATE TABLE IF NOT EXISTS estilos", "descripcion TEXT NOT NULL", "foto_url VARCHAR(255) NULL",
                   "ALTER TABLE servicios ADD COLUMN descripcion TEXT NULL", "ADD COLUMN estilo_id INTEGER NULL",
                   "ADD INDEX ix_citas_estilo_id (estilo_id)",
                   "FOREIGN KEY (estilo_id) REFERENCES estilos (id) ON DELETE RESTRICT"):
        assert cambio in script, cambio
    assert "DROP COLUMN notas" not in script  # el historial de notas se conserva
