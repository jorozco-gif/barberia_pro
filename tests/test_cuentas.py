"""RF-01 a RF-04 (cuentas, sesión y recuperación de contraseña), RNF-01, RNF-02, RNF-06 y RNF-10."""
import re

import models
from helpers import CLAVE, iniciar_sesion

REGISTRO = {
    "nombre": "Juan Pérez",
    "telefono": "3001234567",
    "email": "juan@test.com",
    "password": CLAVE,
    "acepta_tratamiento_datos": True,
}


def registrar(client, **cambios):
    return client.post("/api/auth/registro", json={**REGISTRO, **cambios})


# ---------- RF-01 Registro ----------
def test_cp_rf01_1_registro_valido_y_luego_inicia_sesion(client, db):
    r = registrar(client)
    assert r.status_code == 201
    assert r.json()["rol"] == "cliente"
    assert "password" not in r.json() and "password_hash" not in r.json()
    assert client.post("/api/auth/login", json={"email": "juan@test.com", "password": CLAVE}).status_code == 200
    assert db.query(models.Usuario).filter_by(email="juan@test.com").one().rol == models.ROL_CLIENTE


def test_cp_rf01_2_correo_duplicado_se_rechaza_sin_importar_mayusculas(client, db):
    assert registrar(client).status_code == 201
    assert registrar(client).status_code == 400
    assert registrar(client, email="JUAN@Test.com").status_code == 400
    assert db.query(models.Usuario).count() == 1


def test_cp_rf01_3_correo_invalido(client):
    assert registrar(client, email="juan.test.com").status_code == 422


def test_cp_rf01_4_contrasena_corta(client):
    assert registrar(client, password="Ab#1234").status_code == 422


def test_cp_rf01_5_campos_obligatorios(client):
    for campo in ("nombre", "telefono", "email", "password"):
        datos = {k: v for k, v in REGISTRO.items() if k != campo}
        assert client.post("/api/auth/registro", json=datos).status_code == 422, campo


def test_cp_rf01_6_correo_se_guarda_en_minusculas_y_el_login_no_distingue_mayusculas(client, db):
    registrar(client, email="Juan@Test.COM")
    assert db.query(models.Usuario).one().email == "juan@test.com"
    r = client.post("/api/auth/login", json={"email": "JUAN@test.com", "password": CLAVE})
    assert r.status_code == 200


# ---------- RNF-06 Consentimiento ----------
def test_cp_rnf06_1_registro_con_consentimiento(client):
    assert registrar(client, acepta_tratamiento_datos=True).status_code == 201


def test_cp_rnf06_2_registro_sin_consentimiento(client, db):
    assert registrar(client, acepta_tratamiento_datos=False).status_code == 422
    assert client.post("/api/auth/registro", json={
        k: v for k, v in REGISTRO.items() if k != "acepta_tratamiento_datos"}).status_code == 422
    assert db.query(models.Usuario).count() == 0


# ---------- RNF-01 Contraseñas cifradas ----------
def test_cp_rnf01_1_contrasena_guardada_con_hash_argon2(client, db):
    registrar(client)
    guardado = db.query(models.Usuario).one().password_hash
    assert guardado != CLAVE and CLAVE not in guardado
    assert guardado.startswith("$argon2")


# ---------- RF-02 Inicio de sesión ----------
def test_cp_rf02_1_login_de_cada_rol(client, cliente, barbero, admin):
    for usuario, rol in ((cliente, models.ROL_CLIENTE), (barbero.usuario, models.ROL_BARBERO), (admin, models.ROL_ADMIN)):
        r = client.post("/api/auth/login", json={"email": usuario.email, "password": CLAVE})
        assert r.status_code == 200
        cuerpo = r.json()
        assert cuerpo["token_type"] == "bearer" and cuerpo["access_token"]
        assert cuerpo["usuario"]["rol"] == rol


def test_cp_rf02_2_correo_no_registrado(client):
    r = client.post("/api/auth/login", json={"email": "nadie@test.com", "password": CLAVE})
    assert r.status_code == 401
    assert "registrado" in r.json()["detail"]


def test_cp_rf02_3_contrasena_incorrecta(client, cliente):
    r = client.post("/api/auth/login", json={"email": cliente.email, "password": "otraClave99"})
    assert r.status_code == 401


def test_cp_rf02_4_cuenta_inactiva(client, db, cliente):
    cliente.activo = False
    db.commit()
    r = client.post("/api/auth/login", json={"email": cliente.email, "password": CLAVE})
    assert r.status_code == 401


def test_cp_rnf10_2_inyeccion_sql_en_el_login(client, cliente):
    r = client.post("/api/auth/login", json={"email": "' OR '1'='1", "password": "x"})
    assert r.status_code in (401, 422)
    r = client.post("/api/auth/login", json={"email": cliente.email, "password": "' OR '1'='1"})
    assert r.status_code == 401


# ---------- RF-03 Cierre de sesión y acceso protegido ----------
def test_cp_rf03_1_logout_invalida_el_token(client, cliente):
    h = iniciar_sesion(client, cliente.email)
    assert client.get("/api/citas/mias", headers=h).status_code == 200
    assert client.post("/api/auth/logout", headers=h).status_code == 200
    assert client.get("/api/citas/mias", headers=h).status_code == 401


def test_cp_rf03_2_acceso_sin_sesion(client):
    assert client.get("/api/citas/mias").status_code == 401
    assert client.get("/api/barberos").status_code == 401
    assert client.get("/api/citas/mias", headers={"Authorization": "Bearer inventado"}).status_code == 401


def test_cp_rf03_3_dos_sesiones_son_independientes(client, cliente):
    h1, h2 = iniciar_sesion(client, cliente.email), iniciar_sesion(client, cliente.email)
    client.post("/api/auth/logout", headers=h1)
    assert client.get("/api/citas/mias", headers=h1).status_code == 401
    assert client.get("/api/citas/mias", headers=h2).status_code == 200


def test_cp_rnf01_3_el_token_no_se_guarda_en_claro(client, db, cliente):
    h = iniciar_sesion(client, cliente.email)
    token = h["Authorization"].split()[1]
    sesion = db.query(models.Sesion).one()
    assert sesion.token_hash != token and len(sesion.token_hash) == 64


# ---------- RNF-02 Inactividad de 15 minutos ----------
def test_cp_rnf02_1_sesion_expira_tras_15_minutos_sin_actividad(client, reloj, cliente):
    h = iniciar_sesion(client, cliente.email)
    reloj.avanzar(minutes=15, seconds=1)
    r = client.get("/api/citas/mias", headers=h)
    assert r.status_code == 401
    assert "sesión" in r.json()["detail"].lower()


def test_cp_rnf02_2_sesion_vigente_a_los_14_minutos(client, reloj, cliente):
    h = iniciar_sesion(client, cliente.email)
    reloj.avanzar(minutes=14)
    assert client.get("/api/citas/mias", headers=h).status_code == 200


def test_cp_rnf02_3_la_actividad_renueva_la_sesion(client, reloj, cliente):
    h = iniciar_sesion(client, cliente.email)
    for _ in range(3):
        reloj.avanzar(minutes=14)
        assert client.get("/api/citas/mias", headers=h).status_code == 200


def test_cp_rnf02_4_limite_exacto_de_15_minutos(client, reloj, cliente):
    h = iniciar_sesion(client, cliente.email)
    reloj.avanzar(minutes=15)
    assert client.get("/api/citas/mias", headers=h).status_code == 401


def test_cp_rnf02_5_sesion_expirada_se_elimina(client, reloj, db, cliente):
    h = iniciar_sesion(client, cliente.email)
    reloj.avanzar(minutes=16)
    client.get("/api/citas/mias", headers=h)
    assert db.query(models.Sesion).count() == 0


# ---------- RF-04 Recuperación de contraseña ----------
def token_del_correo(correos):
    cuerpo = correos[-1]["cuerpo"]
    return re.search(r"token=([\w\-]+)", cuerpo).group(1)


def test_cp_rf04_1_flujo_completo_de_recuperacion(client, correos, cliente):
    r = client.post("/api/auth/recuperar", json={"email": cliente.email})
    assert r.status_code == 200
    assert len(correos) == 1 and correos[0]["para"] == cliente.email
    assert "http://localhost:5173" in correos[0]["cuerpo"]
    assert CLAVE not in correos[0]["cuerpo"]  # CP-RNF01-2: nunca se envía la contraseña
    token = token_del_correo(correos)

    assert client.get("/api/auth/restablecer/validar", params={"token": token}).status_code == 200
    nueva = "NuevaClave#99"
    assert client.post("/api/auth/restablecer", json={"token": token, "nueva_password": nueva}).status_code == 200
    assert client.post("/api/auth/login", json={"email": cliente.email, "password": nueva}).status_code == 200
    assert client.post("/api/auth/login", json={"email": cliente.email, "password": CLAVE}).status_code == 401


def test_cp_rf04_2_enlace_vigente_a_los_59_minutos(client, reloj, correos, cliente):
    client.post("/api/auth/recuperar", json={"email": cliente.email})
    token = token_del_correo(correos)
    reloj.avanzar(minutes=59)
    r = client.post("/api/auth/restablecer", json={"token": token, "nueva_password": "NuevaClave#99"})
    assert r.status_code == 200


def test_cp_rf04_3_enlace_vencido_a_los_61_minutos(client, reloj, correos, cliente):
    client.post("/api/auth/recuperar", json={"email": cliente.email})
    token = token_del_correo(correos)
    reloj.avanzar(minutes=61)
    assert client.get("/api/auth/restablecer/validar", params={"token": token}).status_code == 400
    r = client.post("/api/auth/restablecer", json={"token": token, "nueva_password": "NuevaClave#99"})
    assert r.status_code == 400
    assert client.post("/api/auth/login", json={"email": cliente.email, "password": CLAVE}).status_code == 200


def test_cp_rf04_4_el_enlace_se_usa_una_sola_vez(client, correos, cliente):
    client.post("/api/auth/recuperar", json={"email": cliente.email})
    token = token_del_correo(correos)
    datos = {"token": token, "nueva_password": "NuevaClave#99"}
    assert client.post("/api/auth/restablecer", json=datos).status_code == 200
    assert client.post("/api/auth/restablecer", json=datos).status_code == 400


def test_cp_rf04_5_correo_no_registrado_responde_igual_y_no_envia(client, correos):
    r = client.post("/api/auth/recuperar", json={"email": "nadie@test.com"})
    assert r.status_code == 200
    assert correos == []


def test_cp_rf04_6_token_invalido_y_contrasena_corta(client, correos, cliente):
    assert client.get("/api/auth/restablecer/validar", params={"token": "falso"}).status_code == 400
    assert client.post("/api/auth/restablecer", json={"token": "falso", "nueva_password": "NuevaClave#99"}).status_code == 400
    client.post("/api/auth/recuperar", json={"email": cliente.email})
    token = token_del_correo(correos)
    assert client.post("/api/auth/restablecer", json={"token": token, "nueva_password": "corta"}).status_code == 422


def test_cp_rf04_7_cada_solicitud_genera_un_enlace_distinto(client, correos, cliente):
    """La especificación no dice que un enlace nuevo invalide los anteriores; cada uno vale hasta usarse o vencer."""
    client.post("/api/auth/recuperar", json={"email": cliente.email})
    primero = token_del_correo(correos)
    client.post("/api/auth/recuperar", json={"email": cliente.email})
    segundo = token_del_correo(correos)
    assert primero != segundo
    assert client.get("/api/auth/restablecer/validar", params={"token": primero}).status_code == 200
    assert client.get("/api/auth/restablecer/validar", params={"token": segundo}).status_code == 200


def test_cp_rf04_8_restablecer_cierra_las_sesiones_abiertas(client, correos, cliente):
    h = iniciar_sesion(client, cliente.email)
    client.post("/api/auth/recuperar", json={"email": cliente.email})
    token = token_del_correo(correos)
    client.post("/api/auth/restablecer", json={"token": token, "nueva_password": "NuevaClave#99"})
    assert client.get("/api/citas/mias", headers=h).status_code == 401
