-- =====================================================================
-- BarberShop Pro - Migración v1.1 -> v1.2 (SQLite 3.35+)
-- =====================================================================
-- Mismos cambios que v1_2_mysql.sql (RF-08, RF-09, RF-33, RF-34, RNF-07).
-- La columna citas.notas se conserva para las citas anteriores a la v1.2.
--
-- Equivale a ejecutar `python migrar.py` (idempotente; la aplicación también
-- lo hace al arrancar). Para aplicarlo a mano UNA sola vez:
--   sqlite3 barberia.db < migraciones/v1_2_sqlite.sql
-- Haz una copia del archivo .db antes.
-- =====================================================================

PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS estilos (
    id INTEGER NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    descripcion TEXT NOT NULL,
    foto_url VARCHAR(255),
    activo BOOLEAN NOT NULL DEFAULT 1,
    PRIMARY KEY (id)
);
CREATE INDEX IF NOT EXISTS ix_estilos_id ON estilos (id);

ALTER TABLE servicios ADD COLUMN descripcion TEXT;

-- SQLite solo admite la clave foránea al agregar la columna, y exige que su valor por defecto sea NULL.
ALTER TABLE citas ADD COLUMN estilo_id INTEGER REFERENCES estilos (id) ON DELETE RESTRICT;
CREATE INDEX IF NOT EXISTS ix_citas_estilo_id ON citas (estilo_id);

-- Catálogo inicial de estilos (opcional; el seed hace lo mismo). Mientras haya
-- estilos activos, el cliente debe elegir uno al reservar (PN-14).
INSERT INTO estilos (nombre, descripcion, activo) VALUES
    ('Fade bajo', 'Degradado que empieza muy cerca de la oreja y la nuca. Discreto y fácil de mantener.', 1),
    ('Pompadour', 'Laterales cortos y volumen peinado hacia atrás en la parte superior.', 1),
    ('Buzz cut', 'Corte uniforme a máquina en toda la cabeza. Práctico y sin necesidad de peinado.', 1),
    ('Crop texturizado', 'Parte superior con textura y flequillo corto hacia adelante, laterales degradados.', 1),
    ('Clásico de tijera', 'Corte tradicional a tijera, con raya lateral y acabado natural.', 1);

COMMIT;
