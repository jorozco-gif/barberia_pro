-- =====================================================================
-- BarberShop Pro - Migración v1.1 -> v1.2 (MySQL 8 / MariaDB 10.5+)
-- =====================================================================
-- Cambios:
--   1. Tabla estilos: catálogo que gestiona el administrador (RF-33).
--   2. servicios.descripcion: descripción opcional del servicio (RF-08, RF-09).
--   3. citas.estilo_id: estilo elegido por el cliente al reservar (RF-34),
--      con índice y clave foránea RESTRICT hacia estilos (RNF-07).
--
-- La columna citas.notas NO se elimina: las citas anteriores a la v1.2
-- guardan ahí lo que escribió el cliente.
--
-- Equivale a ejecutar `python migrar.py` (que además es idempotente y lo hace
-- la aplicación al arrancar). Este script es para aplicarlo a mano UNA sola vez:
--   mysql -u <usuario> -p <base_de_datos> < migraciones/v1_2_mysql.sql
-- Haz una copia de seguridad antes (mysqldump).
-- =====================================================================

CREATE TABLE IF NOT EXISTS estilos (
    id INTEGER NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(100) NOT NULL,
    descripcion TEXT NOT NULL,
    foto_url VARCHAR(255) NULL,
    activo BOOL NOT NULL DEFAULT 1,
    PRIMARY KEY (id),
    INDEX ix_estilos_id (id)
);

ALTER TABLE servicios
    ADD COLUMN descripcion TEXT NULL;

ALTER TABLE citas
    ADD COLUMN estilo_id INTEGER NULL,
    ADD INDEX ix_citas_estilo_id (estilo_id),
    ADD CONSTRAINT fk_citas_estilo FOREIGN KEY (estilo_id) REFERENCES estilos (id) ON DELETE RESTRICT;

-- Catálogo inicial de estilos (opcional; el seed hace lo mismo). Mientras haya
-- estilos activos, el cliente debe elegir uno al reservar (PN-14).
INSERT INTO estilos (nombre, descripcion, activo) VALUES
    ('Fade bajo', 'Degradado que empieza muy cerca de la oreja y la nuca. Discreto y fácil de mantener.', 1),
    ('Pompadour', 'Laterales cortos y volumen peinado hacia atrás en la parte superior.', 1),
    ('Buzz cut', 'Corte uniforme a máquina en toda la cabeza. Práctico y sin necesidad de peinado.', 1),
    ('Crop texturizado', 'Parte superior con textura y flequillo corto hacia adelante, laterales degradados.', 1),
    ('Clásico de tijera', 'Corte tradicional a tijera, con raya lateral y acabado natural.', 1);
