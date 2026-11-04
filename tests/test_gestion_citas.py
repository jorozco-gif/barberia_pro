"""RF-22 a RF-25: consulta, cancelación y reprogramación de citas del cliente, y sus correos."""
import models
from helpers import agendar, crear_cita, hora


def cancelar(client, h, cita):
    return client.post(f"/api/citas/{cita.id}/cancelar", headers=h)


def reprogramar(client, h, cita, fecha, hora_inicio):
    return client.post(f"/api/citas/{cita.id}/reprogramar", headers=h,
                       json={"fecha": fecha.isoformat(), "hora_inicio": hora_inicio})


# ---------- RF-22 Mis citas ----------
def test_cp_rf22_1_mis_citas_agendadas_e_historial(
    client, db, reloj, h_cliente, cliente, otro_cliente, barbero, corte
):
    futura = crear_cita(db, cliente, barbero, corte, reloj.en(2), "10:00")
    proxima = crear_cita(db, cliente, barbero, corte, reloj.en(1), "09:00")
    pasada = crear_cita(db, cliente, barbero, corte, reloj.en(-3), "10:00", estado=models.ESTADO_ATENDIDA)
    crear_cita(db, otro_cliente, barbero, corte, reloj.en(1), "15:00")  # de otro cliente

    r = client.get("/api/citas/mias", headers=h_cliente)
    assert r.status_code == 200
    # Más recientes primero
    assert [c["id"] for c in r.json()] == [futura.id, proxima.id, pasada.id]
    assert {c["estado"] for c in r.json()} == {"Programada", "Atendida"}
    assert r.json()[0]["barbero"]["nombre"] == "Mateo Maestro"


def test_cp_rf22_2_cita_ajena(client, db, reloj, h_cliente, h_otro_cliente, h_admin, otro_cliente, barbero, corte):
    ajena = crear_cita(db, otro_cliente, barbero, corte, reloj.en(1), "10:00")
    assert client.get(f"/api/citas/{ajena.id}", headers=h_cliente).status_code == 403
    assert client.get(f"/api/citas/{ajena.id}", headers=h_otro_cliente).status_code == 200
    assert client.get(f"/api/citas/{ajena.id}", headers=h_admin).status_code == 200
    assert client.get("/api/citas/999", headers=h_cliente).status_code == 404
    assert cancelar(client, h_cliente, ajena).status_code == 403
    assert reprogramar(client, h_cliente, ajena, reloj.en(2), "10:00").status_code == 403


def test_cp_rf22_3_el_barbero_de_la_cita_la_puede_consultar(client, db, reloj, h_barbero, cliente, barbero, corte):
    cita = crear_cita(db, cliente, barbero, corte, reloj.en(1), "10:00")
    assert client.get(f"/api/citas/{cita.id}", headers=h_barbero).status_code == 200


# ---------- RF-23 Cancelación ----------
def test_cp_rf23_1_cancelar_con_12_horas_y_1_minuto(client, db, reloj, h_cliente, h_otro_cliente, cliente, barbero, corte):
    cita = crear_cita(db, cliente, barbero, corte, reloj.en(0), "20:01")  # ahora 08:00: faltan 12 h 01 min
    r = cancelar(client, h_cliente, cita)
    assert r.status_code == 200 and r.json()["estado"] == "Cancelada"
    # el horario del barbero queda libre
    assert agendar(client, h_otro_cliente, barbero, corte, reloj.en(1), "10:00").status_code == 201


def test_cp_rf23_2_cancelar_con_11_horas_y_59_minutos(client, db, reloj, h_cliente, cliente, barbero, corte, correos):
    cita = crear_cita(db, cliente, barbero, corte, reloj.en(0), "19:59")
    r = cancelar(client, h_cliente, cita)
    assert r.status_code == 400 and "12" in r.json()["detail"]
    db.expire_all()
    assert db.get(models.Cita, cita.id).estado == models.ESTADO_PROGRAMADA
    assert correos == []  # CP-RF25-2


def test_cp_rf23_3_exactamente_12_horas_se_permite(client, db, reloj, h_cliente, cliente, barbero, corte):
    cita = crear_cita(db, cliente, barbero, corte, reloj.en(0), "20:00")
    assert cancelar(client, h_cliente, cita).status_code == 200


def test_cp_rf23_4_estados_terminales(client, db, reloj, h_cliente, cliente, barbero, corte):
    for i, estado in enumerate((models.ESTADO_CANCELADA, models.ESTADO_ATENDIDA, models.ESTADO_INASISTENCIA)):
        cita = crear_cita(db, cliente, barbero, corte, reloj.en(3 + i), "10:00", estado=estado)
        assert cancelar(client, h_cliente, cita).status_code == 400


def test_cp_rf23_5_el_barbero_y_el_administrador_no_usan_la_cancelacion_del_cliente(
    client, db, reloj, h_barbero, h_admin, cliente, barbero, corte
):
    cita = crear_cita(db, cliente, barbero, corte, reloj.en(3), "10:00")
    assert cancelar(client, h_barbero, cita).status_code == 403
    assert cancelar(client, h_admin, cita).status_code == 403


# ---------- RF-24 Reprogramación ----------
def test_cp_rf24_1_primera_reprogramacion(client, db, reloj, h_cliente, h_otro_cliente, cliente, barbero, corte):
    cita = crear_cita(db, cliente, barbero, corte, reloj.en(1), "10:00")
    r = reprogramar(client, h_cliente, cita, reloj.en(2), "15:00")
    assert r.status_code == 200
    nueva = r.json()
    assert nueva["fecha"] == reloj.en(2).isoformat() and nueva["hora_inicio"] == "15:00:00"
    assert nueva["hora_fin"] == "15:30:00" and nueva["reprogramada"] is True
    assert nueva["estado"] == "Programada" and nueva["codigo_reserva"] == cita.codigo_reserva
    # el horario anterior queda libre y el nuevo ocupado
    assert agendar(client, h_otro_cliente, barbero, corte, reloj.en(1), "10:00").status_code == 201
    assert agendar(client, h_otro_cliente, barbero, corte, reloj.en(2), "15:00").status_code == 409


def test_cp_rf24_2_segunda_reprogramacion(client, db, reloj, h_cliente, cliente, barbero, corte):
    cita = crear_cita(db, cliente, barbero, corte, reloj.en(1), "10:00")
    assert reprogramar(client, h_cliente, cita, reloj.en(2), "15:00").status_code == 200
    r = reprogramar(client, h_cliente, cita, reloj.en(3), "15:00")
    assert r.status_code == 400 and "ya fue reprogramada" in r.json()["detail"]


def test_cp_rf24_3_reprogramar_con_11_horas_y_59_minutos(client, db, reloj, h_cliente, cliente, barbero, corte, correos):
    cita = crear_cita(db, cliente, barbero, corte, reloj.en(0), "19:59")
    assert reprogramar(client, h_cliente, cita, reloj.en(2), "10:00").status_code == 400
    assert correos == []
    db.expire_all()
    assert db.get(models.Cita, cita.id).reprogramada is False


def test_cp_rf24_4_reprogramar_sobre_otra_cita_del_barbero(client, db, reloj, h_cliente, cliente, otro_cliente, barbero, corte):
    cita = crear_cita(db, cliente, barbero, corte, reloj.en(1), "10:00")
    crear_cita(db, otro_cliente, barbero, corte, reloj.en(2), "15:00")
    assert reprogramar(client, h_cliente, cita, reloj.en(2), "15:00").status_code == 409
    assert reprogramar(client, h_cliente, cita, reloj.en(2), "14:45").status_code == 409  # solape (14:45 a 15:15)
    db.expire_all()
    assert db.get(models.Cita, cita.id).fecha == reloj.en(1) and db.get(models.Cita, cita.id).reprogramada is False


def test_cp_rf24_5_la_cita_no_choca_consigo_misma_al_desplazarse_poco(client, db, reloj, h_cliente, cliente, barbero, corte):
    cita = crear_cita(db, cliente, barbero, corte, reloj.en(1), "10:00")
    assert reprogramar(client, h_cliente, cita, reloj.en(1), "10:30").status_code == 200  # contiguo al horario que deja


def test_cp_rf24_6_destino_invalido(client, db, reloj, h_cliente, cliente, barbero, corte):
    cita = crear_cita(db, cliente, barbero, corte, reloj.en(1), "10:00")
    assert reprogramar(client, h_cliente, cita, reloj.en(-1), "10:00").status_code == 400  # fecha pasada
    assert reprogramar(client, h_cliente, cita, reloj.en(2), "21:00").status_code == 409  # fuera del horario del barbero
    assert reprogramar(client, h_cliente, cita, reloj.en(6), "10:00").status_code == 409  # domingo
    assert reprogramar(client, h_cliente, cita, reloj.en(2), "10:15").status_code == 400  # fuera del intervalo de 30 min
    db.add(models.Bloqueo(barbero_id=barbero.id, fecha=reloj.en(2), hora_inicio=hora("10:00"), hora_fin=hora("12:00")))
    db.commit()
    assert reprogramar(client, h_cliente, cita, reloj.en(2), "11:00").status_code == 409  # bloqueado


def test_cp_rf24_7_solo_citas_programadas(client, db, reloj, h_cliente, cliente, barbero, corte):
    cita = crear_cita(db, cliente, barbero, corte, reloj.en(1), "10:00", estado=models.ESTADO_CANCELADA)
    assert reprogramar(client, h_cliente, cita, reloj.en(2), "10:00").status_code == 400


def test_cp_rf24_8_horarios_disponibles_para_reprogramar(client, db, reloj, h_cliente, h_otro_cliente, cliente, otro_cliente, barbero, corte):
    cita = crear_cita(db, cliente, barbero, corte, reloj.en(1), "10:00")
    crear_cita(db, otro_cliente, barbero, corte, reloj.en(1), "10:30")
    r = client.get(f"/api/citas/{cita.id}/disponibilidad", headers=h_cliente,
                   params={"fecha": reloj.en(1).isoformat(), "franja": "Mañana"})
    assert r.status_code == 200
    inicios = [s["hora_inicio"] for s in r.json()]
    assert "10:00" in inicios and "10:30" not in inicios and "09:30" in inicios
    # otra persona no puede consultarlo
    assert client.get(f"/api/citas/{cita.id}/disponibilidad", headers=h_otro_cliente,
                      params={"fecha": reloj.en(1).isoformat(), "franja": "Mañana"}).status_code == 403
    # una cita ya reprogramada no ofrece horarios
    assert reprogramar(client, h_cliente, cita, reloj.en(2), "10:00").status_code == 200
    assert client.get(f"/api/citas/{cita.id}/disponibilidad", headers=h_cliente,
                      params={"fecha": reloj.en(1).isoformat(), "franja": "Mañana"}).status_code == 400


# ---------- RF-25 Correos de cancelación y reprogramación ----------
def test_cp_rf25_1_cancelar_avisa_al_cliente_y_al_barbero(client, db, reloj, h_cliente, cliente, barbero, corte, correos):
    cita = crear_cita(db, cliente, barbero, corte, reloj.en(1), "15:00")
    cancelar(client, h_cliente, cita)
    assert sorted(c["para"] for c in correos) == sorted([cliente.email, barbero.usuario.email])
    assert all(cita.codigo_reserva in c["cuerpo"] and "cancelada" in c["asunto"].lower() for c in correos)


def test_cp_rf25_2_reprogramar_avisa_al_cliente_y_al_barbero(client, db, reloj, h_cliente, cliente, barbero, corte, correos):
    cita = crear_cita(db, cliente, barbero, corte, reloj.en(1), "10:00")
    reprogramar(client, h_cliente, cita, reloj.en(2), "15:00")
    assert sorted(c["para"] for c in correos) == sorted([cliente.email, barbero.usuario.email])
    cuerpo = correos[0]["cuerpo"]
    assert "08/01/2030" in cuerpo and "10:00 a. m." in cuerpo  # horario anterior
    assert "09/01/2030" in cuerpo and "3:00 p. m." in cuerpo   # horario nuevo
