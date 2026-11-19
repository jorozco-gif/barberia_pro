"""Actualiza el esquema de la base de datos de la v1.1 a la v1.2 sin borrar datos (RNF-07).

Base.metadata.create_all crea las tablas que faltan, pero no agrega columnas a las tablas que ya existen.
Una base creada con la v1.1 necesita estos cambios, que aquí se aplican solo si faltan:

1. Tabla estilos (RF-33).
2. Columna servicios.descripcion (RF-08, RF-09).
3. Columna citas.estilo_id, con su índice y su clave foránea hacia estilos (RF-34).

La columna citas.notas se conserva: las citas anteriores a la v1.2 guardan ahí lo que escribió el cliente.

Es idempotente: se puede ejecutar varias veces, y la aplicación y el seed lo ejecutan al arrancar.
Funciona con SQLite y con MySQL/MariaDB. Los mismos cambios, en SQL, están en migraciones/v1_2_mysql.sql
y migraciones/v1_2_sqlite.sql, por si se prefiere aplicarlos a mano.

Uso manual (desde src/backend):  python migrar.py
"""
import sys
from typing import List

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from database import Base, engine as engine_por_defecto
import models  # noqa: F401  registra todas las tablas en Base.metadata


def _columnas(engine: Engine, tabla: str) -> set:
    return {c["name"] for c in inspect(engine).get_columns(tabla)}


def actualizar_esquema(engine: Engine = engine_por_defecto) -> List[str]:
    """Aplica los cambios pendientes y devuelve la descripción de cada cambio aplicado
    (lista vacía si la base ya estaba al día)."""
    tablas_antes = set(inspect(engine).get_table_names())
    Base.metadata.create_all(bind=engine)  # crea estilos y cualquier otra tabla que falte
    if not tablas_antes:
        return ["Base de datos nueva creada con el esquema v1.2."]

    aplicados = []
    if "estilos" not in tablas_antes:
        aplicados.append("Tabla estilos creada.")

    es_mysql = engine.dialect.name in ("mysql", "mariadb")
    if "descripcion" not in _columnas(engine, "servicios"):
        with engine.begin() as conexion:
            conexion.execute(text("ALTER TABLE servicios ADD COLUMN descripcion TEXT NULL"))
        aplicados.append("Columna servicios.descripcion agregada.")

    if "estilo_id" not in _columnas(engine, "citas"):
        with engine.begin() as conexion:
            if es_mysql:
                conexion.execute(text(
                    "ALTER TABLE citas ADD COLUMN estilo_id INTEGER NULL, "
                    "ADD INDEX ix_citas_estilo_id (estilo_id), "
                    "ADD CONSTRAINT fk_citas_estilo FOREIGN KEY (estilo_id) REFERENCES estilos (id) ON DELETE RESTRICT"
                ))
            else:
                # SQLite solo admite la clave foránea al agregar la columna, y exige que su valor por defecto sea NULL.
                conexion.execute(text(
                    "ALTER TABLE citas ADD COLUMN estilo_id INTEGER REFERENCES estilos (id) ON DELETE RESTRICT"
                ))
                conexion.execute(text("CREATE INDEX IF NOT EXISTS ix_citas_estilo_id ON citas (estilo_id)"))
        aplicados.append("Columna citas.estilo_id agregada, con su índice y su clave foránea.")
    return aplicados


if __name__ == "__main__":
    try:
        cambios = actualizar_esquema()
    except Exception as error:  # se muestra el motivo sin la traza completa
        print(f"No se pudo actualizar la base de datos: {error}", file=sys.stderr)
        sys.exit(1)
    if cambios:
        for cambio in cambios:
            print(cambio)
    else:
        print("La base de datos ya estaba en la v1.2. No se aplicó ningún cambio.")
