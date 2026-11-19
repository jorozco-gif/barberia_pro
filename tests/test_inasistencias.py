"""RF-29 (sanción por inasistencias), RF-30 (cuenta suspendida) y PN-10."""
import datetime

import models
import services
from helpers import CLAVE, agendar, crear_cita

HOY = datetime.date(2030, 1, 7)  # el reloj de las pruebas arranca el lunes 7/01/2030 a las 08:00
UN_DIA = datetime.timedelta(days=1)


def inasistencia_antigua(db, cliente, barbero, corte, fecha):
    return crear_cita(db, cliente, barbero, corte, fecha, "10:00", estado=models.ESTADO_INASISTENCIA)


def marcar_inasistencia_hoy(client, db, h_barbero, cliente, barbero, corte, hora_cita="07:00"):
    cita = crear_cita(db, cliente, barbero, corte, HOY, hora_cita)
    return client.patch(f"/api/citas/{cita.id}/estado", headers=h_barbero, json={"estado": "Inasistencia"})


def suspendido_hasta(db, cliente):
    db.expire_all()
    return db.get(models.Usuario, cliente.id).suspendido_hasta


# ---------- Cálculo de meses ----------
def test_sumar_meses_ajusta_al_ultimo_dia_del_mes():
    assert services.sumar_meses(datetime.date(2029, 1, 31), 1) == datetime.date(2029, 2, 28)
    assert services.sumar_meses(datetime.date(2028, 1, 31), 1) == datetime.date(2028, 2, 29)
    assert services.sumar_meses(datetime.date(2030, 3, 31), -1) == datetime.date(2030, 2, 28)
    assert services.sumar_meses(datetime.date(2030, 1, 7), -3) == datetime.date(2029, 10, 7)
    assert services.sumar_meses(datetime.date(2030, 12, 15), 1) == datetime.date(2031, 1, 15)


# ---------- RF-29 Sanción ----------
def test_cp_rf29_1_segunda_inasistencia_dentro_de_3_meses_suspende_1_mes(
    client, db, h_barbero, cliente, barbero, corte
):
    hace_2_meses_29_dias = services.sumar_meses(HOY, -2) - 29 * UN_DIA
    inasistencia_antigua(db, cliente, barbero, corte, hace_2_meses_29_dias)
    r = marcar_inasistencia_hoy(client, db, h_barbero, cliente, barbero, corte)
    assert r.status_code == 200 and r.json()["estado"] == "Inasistencia"
    assert suspendido_hasta(db, cliente) == datetime.date(2030, 2, 7)


def test_cp_rf29_2_inasistencia_de_hace_3_meses_y_1_dia_ya_no_cuenta(client, db, h_barbero, cliente, barbero, corte):
    hace_3_meses_1_dia = services.sumar_meses(HOY, -3) - UN_DIA
    inasistencia_antigua(db, cliente, barbero, corte, hace_3_meses_1_dia)
    assert marcar_inasistencia_hoy(client, db, h_barbero, cliente, barbero, corte).status_code == 200
    assert suspendido_hasta(db, cliente) is None


def test_cp_rf29_2b_el_limite_de_exactamente_3_meses_si_cuenta(client, db, h_barbero, cliente, barbero, corte):
    inasistencia_antigua(db, cliente, barbero, corte, services.sumar_meses(HOY, -3))
    marcar_inasistencia_hoy(client, db, h_barbero, cliente, barbero, corte)
    assert suspendido_hasta(db, cliente) == datetime.date(2030, 2, 7)


def test_cp_rf29_3_primera_inasistencia_no_suspende(client, db, h_barbero, cliente, barbero, corte):
    assert marcar_inasistencia_hoy(client, db, h_barbero, cliente, barbero, corte).status_code == 200
    assert suspendido_hasta(db, cliente) is None


def test_cp_rf29_4_tras_la_suspension_el_contador_vuelve_a_cero(client, db, h_barbero, cliente, barbero, corte):
    cliente.suspendido_hasta = datetime.date(2030, 1, 1)  # la suspensión terminó hace 6 días
    db.commit()
    inasistencia_antigua(db, cliente, barbero, corte, datetime.date(2029, 12, 1))
    inasistencia_antigua(db, cliente, barbero, corte, datetime.date(2029, 12, 15))

    assert marcar_inasistencia_hoy(client, db, h_barbero, cliente, barbero, corte, "07:00").status_code == 200
    assert suspendido_hasta(db, cliente) == datetime.date(2030, 1, 1)  # no se suspendió de nuevo
    # El contador empezó de cero: la siguiente inasistencia sí completa dos.
    assert marcar_inasistencia_hoy(client, db, h_barbero, cliente, barbero, corte, "07:30").status_code == 200
    assert suspendido_hasta(db, cliente) == datetime.date(2030, 2, 7)


def test_cp_rf29_5_las_inasistencias_de_otro_cliente_no_suman(client, db, h_barbero, cliente, otro_cliente, barbero, corte):
    inasistencia_antigua(db, otro_cliente, barbero, corte, HOY - 10 * UN_DIA)
    marcar_inasistencia_hoy(client, db, h_barbero, cliente, barbero, corte)
    assert suspendido_hasta(db, cliente) is None


def test_cp_rf29_6_al_suspender_se_cierran_las_sesiones_del_cliente(client, db, h_barbero, h_cliente, cliente, barbero, corte):
    inasistencia_antigua(db, cliente, barbero, corte, HOY - 10 * UN_DIA)
    assert client.get("/api/citas/mias", headers=h_cliente).status_code == 200
    marcar_inasistencia_hoy(client, db, h_barbero, cliente, barbero, corte)
    assert client.get("/api/citas/mias", headers=h_cliente).status_code == 401


def test_cp_rf29_7_una_inasistencia_durante_la_suspension_no_la_extiende(client, db, h_barbero, cliente, barbero, corte):
    inasistencia_antigua(db, cliente, barbero, corte, HOY - 10 * UN_DIA)
    cliente.suspendido_hasta = datetime.date(2030, 1, 20)
    db.commit()
    marcar_inasistencia_hoy(client, db, h_barbero, cliente, barbero, corte)
    assert suspendido_hasta(db, cliente) == datetime.date(2030, 1, 20)


def test_cp_rf29_8_solo_inasistencia_cuenta_no_cancelada_ni_atendida(client, db, h_barbero, cliente, barbero, corte):
    crear_cita(db, cliente, barbero, corte, HOY - 10 * UN_DIA, "10:00", estado=models.ESTADO_CANCELADA)
    crear_cita(db, cliente, barbero, corte, HOY - 9 * UN_DIA, "10:00", estado=models.ESTADO_ATENDIDA)
    marcar_inasistencia_hoy(client, db, h_barbero, cliente, barbero, corte)
    assert suspendido_hasta(db, cliente) is None


# ---------- RF-30 Cuenta suspendida ----------
def suspender(db, cliente, hasta):
    cliente.suspendido_hasta = hasta
    db.commit()


def test_cp_rf30_1_login_de_un_cliente_suspendido(client, db, cliente):
    suspender(db, cliente, datetime.date(2030, 2, 7))
    r = client.post("/api/auth/login", json={"email": cliente.email, "password": CLAVE})
    assert r.status_code == 403
    assert "suspendida" in r.json()["detail"] and "07/02/2030" in r.json()["detail"]
    assert r.json()["suspendido_hasta"] == "2030-02-07"


def test_cp_rf30_2_login_cuando_la_suspension_ya_termino(client, db, cliente):
    suspender(db, cliente, HOY)  # el día de reactivación ya puede ingresar
    assert client.post("/api/auth/login", json={"email": cliente.email, "password": CLAVE}).status_code == 200
    suspender(db, cliente, HOY - 5 * UN_DIA)
    assert client.post("/api/auth/login", json={"email": cliente.email, "password": CLAVE}).status_code == 200
    suspender(db, cliente, HOY + UN_DIA)  # falta un día
    assert client.post("/api/auth/login", json={"email": cliente.email, "password": CLAVE}).status_code == 403


def test_cp_rf30_3_un_cliente_suspendido_no_puede_agendar(client, db, reloj, h_cliente, cliente, barbero, corte):
    suspender(db, cliente, datetime.date(2030, 2, 7))  # la sesión ya estaba abierta
    r = agendar(client, h_cliente, barbero, corte, reloj.en(1), "10:00")
    assert r.status_code == 403 and "suspendida" in r.json()["detail"]
    assert db.query(models.Cita).count() == 0


def test_cp_rf30_4_el_login_no_revela_la_suspension_con_una_contrasena_incorrecta(client, db, cliente):
    suspender(db, cliente, datetime.date(2030, 2, 7))
    r = client.post("/api/auth/login", json={"email": cliente.email, "password": "incorrecta1"})
    assert r.status_code == 401
