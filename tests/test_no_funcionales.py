"""Requisitos no funcionales verificables por inspección o por ejecución: RNF-01, RNF-05, RNF-07, RNF-09, RNF-10,
datos iniciales (PN-13) y arranque de la aplicación."""
import ast
import datetime
import logging
import os
import ssl
import subprocess

import pytest
from sqlalchemy.exc import IntegrityError

import database
import models
import notificaciones
import politicas
import security
import seed
from conftest import BACKEND_DIR, ENVIAR_REAL
from helpers import CLAVE, crear_cita

RAIZ = os.path.abspath(os.path.join(BACKEND_DIR, "..", ".."))


# ---------- RNF-01 ----------
def test_cp_rnf01_hash_argon2_con_sal_y_verificacion():
    h1, h2 = security.hash_password(CLAVE), security.hash_password(CLAVE)
    assert h1 != h2  # cada hash lleva su propia sal
    assert security.verify_password(CLAVE, h1) and not security.verify_password("otra", h1)
    assert not security.verify_password(CLAVE, "no-es-un-hash")


def test_tokens_aleatorios_y_hash_estable():
    t1, h1 = security.generar_token()
    t2, _ = security.generar_token()
    assert t1 != t2 and len(h1) == 64
    assert security.hash_token(t1) == h1


# ---------- RNF-05 ----------
def test_cp_rnf05_la_hora_del_sistema_es_utc_menos_5():
    esperado = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(hours=5)
    assert abs((models.ahora_colombia() - esperado).total_seconds()) < 5


# ---------- RNF-07 ----------
def test_cp_rnf07_las_claves_foraneas_se_aplican(db, cliente, barbero, corte, reloj):
    cita = crear_cita(db, cliente, barbero, corte, reloj.en(1), "10:00")
    huerfana = models.Cita(
        codigo_reserva="BSP-AAAAAA", cliente_id=999, barbero_id=barbero.id, fecha=reloj.en(1),
        hora_inicio=datetime.time(11, 0), hora_fin=datetime.time(11, 30), estado=models.ESTADO_PROGRAMADA, total=1,
    )
    db.add(huerfana)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    # RESTRICT: no se puede borrar un servicio, un barbero ni un usuario con citas
    for entidad in (corte, barbero, cliente):
        db.delete(entidad)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    assert db.get(models.Cita, cita.id) is not None


def test_el_esquema_tiene_las_nueve_tablas_esperadas():
    assert set(database.Base.metadata.tables) == {
        "usuarios", "barberos", "servicios", "citas", "citas_servicios",
        "disponibilidades", "bloqueos", "tokens_recuperacion", "sesiones",
    }


def test_el_codigo_de_reserva_es_unico(db, cliente, barbero, corte, reloj):
    crear_cita(db, cliente, barbero, corte, reloj.en(1), "10:00", codigo="BSP-ABCDEF")
    with pytest.raises(IntegrityError):
        crear_cita(db, cliente, barbero, corte, reloj.en(1), "11:00", codigo="BSP-ABCDEF")
    db.rollback()


# ---------- RNF-09 ----------
def test_cp_rnf09_1_capas_separadas():
    for archivo in ("models.py", "schemas.py", "services.py", "main.py", "politicas.py", "notificaciones.py"):
        assert os.path.isfile(os.path.join(BACKEND_DIR, archivo)), archivo


def test_cp_rnf09_2_las_rutas_no_acceden_a_la_base_de_datos():
    """En main.py la sesión de base de datos solo se recibe y se entrega a services.py: ninguna ruta la usa."""
    with open(os.path.join(BACKEND_DIR, "main.py"), encoding="utf-8") as f:
        arbol = ast.parse(f.read())
    usos_de_la_sesion = [
        n.attr for n in ast.walk(arbol)
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "db"
    ]
    assert usos_de_la_sesion == []  # ni db.query, ni db.add, ni db.commit...
    sqlalchemy = [
        n for n in ast.walk(arbol)
        if (isinstance(n, ast.ImportFrom) and (n.module or "").startswith("sqlalchemy"))
        or (isinstance(n, ast.Import) and any(a.name.startswith("sqlalchemy") for a in n.names))
    ]
    # Solo se importa Session, como tipo de la dependencia; no se construyen consultas ni expresiones SQL.
    assert all(isinstance(i, ast.ImportFrom) and i.module == "sqlalchemy.orm"
               and [a.name for a in i.names] == ["Session"] for i in sqlalchemy)


# ---------- RNF-10 ----------
def test_cp_rnf10_1_el_repositorio_no_contiene_env_y_existe_env_example():
    ejemplo = os.path.join(BACKEND_DIR, ".env.example")
    assert os.path.isfile(ejemplo)
    with open(ejemplo, encoding="utf-8") as f:
        lineas = dict(l.split("=", 1) for l in f.read().splitlines() if "=" in l and not l.startswith("#"))
    for variable in ("DATABASE_URL", "FRONTEND_URL", "SMTP_HOST", "SMTP_PASSWORD", "SEED_ADMIN_PASSWORD",
                     "SEED_BARBEROS_PASSWORD"):
        assert variable in lineas, variable
    assert lineas["SMTP_PASSWORD"] == "" and lineas["SEED_ADMIN_PASSWORD"] == "" and lineas["SEED_BARBEROS_PASSWORD"] == ""
    with open(os.path.join(RAIZ, ".gitignore"), encoding="utf-8") as f:
        assert ".env" in f.read().splitlines()
    try:
        versionados = subprocess.run(["git", "ls-files"], cwd=RAIZ, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git no está disponible")
    assert not [r for r in versionados.splitlines() if os.path.basename(r) == ".env"]


def test_cp_rnf10_3_el_codigo_no_contiene_contrasenas_escritas():
    for archivo in ("seed.py", "main.py", "services.py", "security.py", "notificaciones.py"):
        with open(os.path.join(BACKEND_DIR, archivo), encoding="utf-8") as f:
            texto = f.read()
        assert "admin123" not in texto and "password123" not in texto.lower(), archivo


# ---------- Datos iniciales (PN-13) ----------
def test_seed_con_contrasenas_de_entorno_es_idempotente(client, db, monkeypatch):
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "AdminSeed#2030")
    monkeypatch.setenv("SEED_BARBEROS_PASSWORD", "BarberoSeed#2030")
    seed.poblar_datos_iniciales()
    seed.poblar_datos_iniciales()
    assert db.query(models.Usuario).filter_by(rol=models.ROL_ADMIN).count() == 1
    assert db.query(models.Barbero).count() == len(seed.BARBEROS_EJEMPLO)
    assert db.query(models.Servicio).count() == len(seed.SERVICIOS_EJEMPLO)
    assert db.query(models.Disponibilidad).count() > 0
    r = client.post("/api/auth/login", json={"email": "admin@barbershop.pro", "password": "AdminSeed#2030"})
    assert r.status_code == 200 and r.json()["usuario"]["rol"] == models.ROL_ADMIN
    email_barbero = seed.BARBEROS_EJEMPLO[0][1]
    assert client.post("/api/auth/login", json={"email": email_barbero, "password": "BarberoSeed#2030"}).status_code == 200


def test_seed_sin_contrasenas_las_genera_y_las_muestra_una_vez(client, monkeypatch, capsys):
    monkeypatch.delenv("SEED_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("SEED_BARBEROS_PASSWORD", raising=False)
    seed.poblar_datos_iniciales()
    salida = capsys.readouterr().out
    linea = [l for l in salida.splitlines() if "Contraseña generada para el administrador" in l][0]
    generada = linea.split(": ", 1)[1].split("  (")[0]
    assert len(generada) >= 8
    assert client.post("/api/auth/login", json={"email": "admin@barbershop.pro", "password": generada}).status_code == 200


def test_seed_rechaza_contrasenas_cortas(monkeypatch):
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "corta")
    with pytest.raises(SystemExit):
        seed.poblar_datos_iniciales()


# ---------- Envío de correo (RF-04, RF-07, RF-21, RF-25) ----------
def test_enviar_sin_smtp_registra_el_correo_y_no_falla(monkeypatch, caplog):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    with caplog.at_level(logging.WARNING, logger="barberia.notificaciones"):
        ENVIAR_REAL("ana@test.com", "Asunto de prueba", "Cuerpo de prueba")
    assert "Correo no enviado" in caplog.text and "ana@test.com" in caplog.text


def test_enviar_con_smtp_arma_y_entrega_el_mensaje(monkeypatch):
    registro = {}

    class SMTPFalso:
        def __init__(self, host, puerto, timeout):
            registro["conexion"] = (host, puerto, timeout)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self, context=None):
            registro["tls"] = context is not None and context.verify_mode == ssl.CERT_REQUIRED

        def login(self, usuario, password):
            registro["login"] = (usuario, password)

        def send_message(self, mensaje):
            registro["mensaje"] = mensaje

    monkeypatch.setattr(notificaciones.smtplib, "SMTP", SMTPFalso)
    for variable, valor in (("SMTP_HOST", "smtp.test"), ("SMTP_PORT", "587"), ("SMTP_USER", "usuario"),
                            ("SMTP_PASSWORD", "secreto"), ("SMTP_FROM", "citas@barbershop.test")):
        monkeypatch.setenv(variable, valor)
    ENVIAR_REAL("ana@test.com", "Asunto de prueba", "Cuerpo de prueba")
    assert registro["conexion"] == ("smtp.test", 587, 10) and registro["tls"] is True
    assert registro["login"] == ("usuario", "secreto")
    mensaje = registro["mensaje"]
    assert (mensaje["To"], mensaje["From"], mensaje["Subject"]) == (
        "ana@test.com", "BarberShop Pro <citas@barbershop.test>", "Asunto de prueba")  # nombre por defecto del remitente
    assert mensaje.get_content().strip() == "Cuerpo de prueba"


def test_un_fallo_del_servidor_de_correo_no_se_propaga(monkeypatch, caplog):
    def sin_conexion(*args, **kwargs):
        raise OSError("sin red")

    monkeypatch.setattr(notificaciones.smtplib, "SMTP", sin_conexion)
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    with caplog.at_level(logging.ERROR, logger="barberia.notificaciones"):
        ENVIAR_REAL("ana@test.com", "Asunto de prueba", "Cuerpo de prueba")  # no debe lanzar excepción
    assert "No se pudo enviar el correo" in caplog.text


# ---------- Políticas y aplicación ----------
def test_politicas_coinciden_con_la_especificacion():
    assert politicas.INTERVALO_MINUTOS == 30
    assert politicas.VIGENCIA_ENLACE_RECUPERACION == datetime.timedelta(hours=1)
    assert politicas.ANTICIPACION_MINIMA == datetime.timedelta(hours=12)
    assert politicas.INACTIVIDAD_SESION == datetime.timedelta(minutes=15)
    assert politicas.MAX_CITAS_ACTIVAS == 2
    assert politicas.INASISTENCIAS_PARA_SUSPENDER == 2
    assert politicas.MESES_VENTANA_INASISTENCIAS == 3 and politicas.MESES_SUSPENSION == 1
    t = datetime.time
    assert politicas.FRANJAS == {"Mañana": (t(6), t(12)), "Tarde": (t(12), t(18)), "Noche": (t(18), t(22))}


def test_la_documentacion_openapi_se_genera(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    rutas = r.json()["paths"]
    for ruta in ("/api/auth/login", "/api/citas", "/api/citas/{cita_id}/reprogramar", "/api/disponibilidad",
                 "/api/admin/barberos", "/api/barbero/agenda"):
        assert ruta in rutas, ruta


def test_la_aplicacion_arranca_y_responde_la_salud(client):
    r = client.get("/")
    assert r.status_code == 200
