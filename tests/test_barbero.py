"""RF-11 (disponibilidad), RF-12 (bloqueos), RF-26 (agenda) y RF-27 (estado de las citas)."""
import models
from helpers import crear_barbero, crear_cita


def lunes_siguiente(reloj):
    """El reloj de las pruebas arranca un lunes a las 8:00; este es el lunes de la semana siguiente."""
    return reloj.en(7)


# ---------- RF-11 Disponibilidad semanal ----------
def test_cp_rf11_1_horario_guardado_y_visible_para_los_clientes(client, db, reloj, h_cliente, h_barbero, corte):
    solo_lunes = crear_barbero(db, "solo.lunes@test.com", "Solo Lunes", horario=False)
    h = {"Authorization": "Bearer " + client.post(
        "/api/auth/login", json={"email": "solo.lunes@test.com", "password": "Clave#1234"}).json()["access_token"]}
    r = client.post("/api/barbero/disponibilidad", headers=h,
                    json={"dia_semana": 0, "hora_inicio": "08:00", "hora_fin": "12:00"})
    assert r.status_code == 201
    assert r.json()["dia_semana"] == 0 and r.json()["hora_inicio"] == "08:00:00"
    assert len(client.get("/api/barbero/disponibilidad", headers=h).json()) == 1

    consulta = {"barbero_id": solo_lunes.id, "franja": "Mañana", "servicios_ids": [corte.id]}
    lunes = client.get("/api/disponibilidad", headers=h_cliente,
                       params={**consulta, "fecha": lunes_siguiente(reloj).isoformat()}).json()
    assert [s["hora_inicio"] for s in lunes] == ["08:00", "08:30", "09:00", "09:30", "10:00", "10:30", "11:00", "11:30"]
    martes = client.get("/api/disponibilidad", headers=h_cliente,
                        params={**consulta, "fecha": reloj.en(8).isoformat()}).json()
    assert martes == []


def test_cp_rf11_2_fin_anterior_o_igual_al_inicio(client, h_barbero):
    for inicio, fin in (("12:00", "08:00"), ("08:00", "08:00")):
        r = client.post("/api/barbero/disponibilidad", headers=h_barbero,
                        json={"dia_semana": 6, "hora_inicio": inicio, "hora_fin": fin})
        assert r.status_code == 422
    assert [d for d in client.get("/api/barbero/disponibilidad", headers=h_barbero).json() if d["dia_semana"] == 6] == []


def test_cp_rf11_3_hora_fuera_del_intervalo_de_30_minutos(client, h_barbero):
    for inicio, fin in (("08:10", "12:00"), ("08:00", "12:15")):
        r = client.post("/api/barbero/disponibilidad", headers=h_barbero,
                        json={"dia_semana": 6, "hora_inicio": inicio, "hora_fin": fin})
        assert r.status_code == 422


def test_cp_rf11_4_rango_solapado_se_rechaza_y_el_contiguo_se_une(client, h_barbero):
    base = {"dia_semana": 6, "hora_inicio": "08:00", "hora_fin": "12:00"}
    assert client.post("/api/barbero/disponibilidad", headers=h_barbero, json=base).status_code == 201
    solapado = client.post("/api/barbero/disponibilidad", headers=h_barbero,
                           json={"dia_semana": 6, "hora_inicio": "11:30", "hora_fin": "14:00"})
    assert solapado.status_code == 409
    contiguo = client.post("/api/barbero/disponibilidad", headers=h_barbero,
                           json={"dia_semana": 6, "hora_inicio": "12:00", "hora_fin": "14:00"})
    assert contiguo.status_code == 201
    domingo = [d for d in client.get("/api/barbero/disponibilidad", headers=h_barbero).json() if d["dia_semana"] == 6]
    assert len(domingo) == 1
    assert (domingo[0]["hora_inicio"], domingo[0]["hora_fin"]) == ("08:00:00", "14:00:00")


def test_cp_rf11_5_eliminar_un_rango_propio_y_no_uno_ajeno(client, h_barbero, h_otro_barbero, barbero, otro_barbero):
    propio = client.get("/api/barbero/disponibilidad", headers=h_barbero).json()[0]["id"]
    ajeno = client.get("/api/barbero/disponibilidad", headers=h_otro_barbero).json()[0]["id"]
    assert client.delete(f"/api/barbero/disponibilidad/{ajeno}", headers=h_barbero).status_code == 404
    assert client.delete(f"/api/barbero/disponibilidad/{propio}", headers=h_barbero).status_code == 200
    assert client.delete(f"/api/barbero/disponibilidad/{propio}", headers=h_barbero).status_code == 404


def test_cp_rf11_6_solo_el_barbero(client, h_cliente, h_admin):
    cuerpo = {"dia_semana": 0, "hora_inicio": "08:00", "hora_fin": "12:00"}
    assert client.post("/api/barbero/disponibilidad", headers=h_cliente, json=cuerpo).status_code == 403
    assert client.post("/api/barbero/disponibilidad", headers=h_admin, json=cuerpo).status_code == 403


# ---------- RF-12 Bloqueos ----------
def test_cp_rf12_1_bloquear_un_dia_futuro(client, reloj, h_cliente, h_barbero, barbero, corte):
    dia = reloj.en(3)  # jueves
    r = client.post("/api/barbero/bloqueos", headers=h_barbero, json={"fecha": dia.isoformat()})
    assert r.status_code == 201 and r.json()["hora_inicio"] is None
    for franja in ("Mañana", "Tarde", "Noche"):
        slots = client.get("/api/disponibilidad", headers=h_cliente, params={
            "barbero_id": barbero.id, "fecha": dia.isoformat(), "franja": franja, "servicios_ids": [corte.id]}).json()
        assert slots == []
    assert len(client.get("/api/barbero/bloqueos", headers=h_barbero).json()) == 1


def test_cp_rf12_2_fecha_pasada(client, reloj, h_barbero):
    r = client.post("/api/barbero/bloqueos", headers=h_barbero, json={"fecha": reloj.en(-1).isoformat()})
    assert r.status_code == 400
    assert client.get("/api/barbero/bloqueos", headers=h_barbero).json() == []


def test_cp_rf12_3_bloqueo_de_hoy_y_por_horas(client, reloj, h_cliente, h_barbero, barbero, corte):
    assert client.post("/api/barbero/bloqueos", headers=h_barbero, json={"fecha": reloj.en(0).isoformat()}).status_code == 201
    dia = reloj.en(2)
    r = client.post("/api/barbero/bloqueos", headers=h_barbero,
                    json={"fecha": dia.isoformat(), "hora_inicio": "10:00", "hora_fin": "11:00"})
    assert r.status_code == 201
    slots = client.get("/api/disponibilidad", headers=h_cliente, params={
        "barbero_id": barbero.id, "fecha": dia.isoformat(), "franja": "Mañana", "servicios_ids": [corte.id]}).json()
    inicios = [s["hora_inicio"] for s in slots]
    assert "09:30" in inicios and "11:00" in inicios
    assert "10:00" not in inicios and "10:30" not in inicios


def test_cp_rf12_4_bloqueo_con_rango_incompleto_o_invertido(client, reloj, h_barbero):
    dia = reloj.en(2).isoformat()
    assert client.post("/api/barbero/bloqueos", headers=h_barbero,
                       json={"fecha": dia, "hora_inicio": "10:00"}).status_code == 422
    assert client.post("/api/barbero/bloqueos", headers=h_barbero,
                       json={"fecha": dia, "hora_inicio": "11:00", "hora_fin": "10:00"}).status_code == 422


def test_cp_rf12_5_no_se_bloquea_donde_hay_citas_programadas(client, db, reloj, h_barbero, barbero, cliente, corte):
    cita = crear_cita(db, cliente, barbero, corte, reloj.en(2), "10:00")
    dia = reloj.en(2).isoformat()
    completo = client.post("/api/barbero/bloqueos", headers=h_barbero, json={"fecha": dia})
    assert completo.status_code == 409 and cita.codigo_reserva in completo.json()["detail"]
    en_conflicto = client.post("/api/barbero/bloqueos", headers=h_barbero,
                               json={"fecha": dia, "hora_inicio": "10:15", "hora_fin": "11:00"})
    assert en_conflicto.status_code == 409
    sin_conflicto = client.post("/api/barbero/bloqueos", headers=h_barbero,
                                json={"fecha": dia, "hora_inicio": "10:30", "hora_fin": "11:00"})
    assert sin_conflicto.status_code == 201


def test_cp_rf12_6_eliminar_bloqueo_solo_el_propio(client, reloj, h_barbero, h_otro_barbero):
    creado = client.post("/api/barbero/bloqueos", headers=h_barbero, json={"fecha": reloj.en(3).isoformat()}).json()
    assert client.delete(f"/api/barbero/bloqueos/{creado['id']}", headers=h_otro_barbero).status_code == 404
    assert client.delete(f"/api/barbero/bloqueos/{creado['id']}", headers=h_barbero).status_code == 200
    assert client.get("/api/barbero/bloqueos", headers=h_barbero).json() == []


# ---------- RF-26 Agenda del barbero ----------
def test_cp_rf26_1_agenda_por_dia_y_por_semana(client, db, reloj, h_barbero, barbero, cliente, otro_cliente, corte, barba):
    # Semana del lunes 7 al domingo 13 de enero de 2030; la siguiente empieza el 14.
    tarde = crear_cita(db, otro_cliente, barbero, corte, reloj.en(2), "15:00")
    manana = crear_cita(db, cliente, barbero, [corte, barba], reloj.en(2), "09:00")
    lunes = crear_cita(db, cliente, barbero, corte, reloj.en(0), "14:00")
    semana_siguiente = crear_cita(db, cliente, barbero, corte, reloj.en(7), "09:00")

    dia = client.get("/api/barbero/agenda", headers=h_barbero, params={"fecha": reloj.en(2).isoformat()})
    assert dia.status_code == 200
    assert [c["id"] for c in dia.json()] == [manana.id, tarde.id]  # cronológico
    primera = dia.json()[0]
    assert primera["cliente"]["nombre"] == "Ana Cliente"
    assert {s["servicio"]["nombre"] for s in primera["servicios"]} == {"Corte", "Barba"}

    semana = client.get("/api/barbero/agenda", headers=h_barbero,
                        params={"fecha": reloj.en(3).isoformat(), "vista": "semana"}).json()
    assert [c["id"] for c in semana] == [lunes.id, manana.id, tarde.id]  # lunes a domingo, sin la semana siguiente
    assert semana_siguiente.id not in [c["id"] for c in semana]

    hoy = client.get("/api/barbero/agenda", headers=h_barbero).json()  # sin fecha: hoy
    assert [c["id"] for c in hoy] == [lunes.id]


def test_cp_rf26_2_un_barbero_no_ve_la_agenda_de_otro(
    client, db, reloj, h_barbero, h_otro_barbero, barbero, otro_barbero, cliente, corte
):
    mia = crear_cita(db, cliente, barbero, corte, reloj.en(1), "10:00")
    ajena = crear_cita(db, cliente, otro_barbero, corte, reloj.en(1), "11:00")
    # La agenda siempre es la de la sesión: aunque se pida otro barbero, solo devuelve las propias.
    agenda = client.get("/api/barbero/agenda", headers=h_barbero,
                        params={"fecha": reloj.en(1).isoformat(), "barbero_id": otro_barbero.id}).json()
    assert [c["id"] for c in agenda] == [mia.id]
    # Y el detalle de una cita ajena se niega.
    assert client.get(f"/api/citas/{ajena.id}", headers=h_barbero).status_code == 403
    assert client.get(f"/api/citas/{mia.id}", headers=h_barbero).status_code == 200
    # Un barbero tampoco puede cambiar el estado de una cita ajena.
    ya_iniciada = crear_cita(db, cliente, otro_barbero, corte, reloj.en(0), "07:00")
    assert client.patch(f"/api/citas/{ya_iniciada.id}/estado", headers=h_barbero,
                        json={"estado": "Atendida"}).status_code == 403


def test_cp_rf26_3_vista_invalida(client, h_barbero):
    assert client.get("/api/barbero/agenda", headers=h_barbero, params={"vista": "mes"}).status_code == 422


# ---------- RF-27 Estado de las citas ----------
def cambiar(client, h, cita, estado):
    return client.patch(f"/api/citas/{cita.id}/estado", headers=h, json={"estado": estado})


def test_cp_rf27_1_marcar_atendida_con_la_hora_de_inicio_llegada(client, db, reloj, h_barbero, barbero, cliente, corte):
    cita = crear_cita(db, cliente, barbero, corte, reloj.en(0), "08:00")  # el reloj marca justo las 08:00
    r = cambiar(client, h_barbero, cita, "Atendida")
    assert r.status_code == 200 and r.json()["estado"] == "Atendida"


def test_cp_rf27_2_cita_que_aun_no_empieza(client, db, reloj, h_barbero, barbero, cliente, corte):
    cita = crear_cita(db, cliente, barbero, corte, reloj.en(0), "08:01")  # empieza un minuto después de "ahora"
    for estado in ("Atendida", "Inasistencia", "Cancelada"):  # PN-06: los tres estados solo desde la hora de inicio
        assert cambiar(client, h_barbero, cita, estado).status_code == 400
    db.expire_all()
    assert db.get(models.Cita, cita.id).estado == models.ESTADO_PROGRAMADA


def test_cp_rf27_3_estado_terminal(client, db, reloj, h_barbero, barbero, cliente, corte):
    cita = crear_cita(db, cliente, barbero, corte, reloj.en(0), "07:00", estado=models.ESTADO_ATENDIDA)
    for estado in ("Atendida", "Inasistencia", "Cancelada"):
        assert cambiar(client, h_barbero, cita, estado).status_code == 400


def test_cp_rf27_4_marcar_inasistencia(client, db, reloj, h_barbero, barbero, cliente, corte):
    cita = crear_cita(db, cliente, barbero, corte, reloj.en(0), "07:00")
    r = cambiar(client, h_barbero, cita, "Inasistencia")
    assert r.status_code == 200 and r.json()["estado"] == "Inasistencia"


def test_cp_rf27_5_estado_arbitrario(client, db, reloj, h_barbero, barbero, cliente, corte):
    cita = crear_cita(db, cliente, barbero, corte, reloj.en(0), "07:00")
    assert cambiar(client, h_barbero, cita, "Borrador").status_code == 422
    assert cambiar(client, h_barbero, cita, "Programada").status_code == 422


def test_cp_rf27_6_el_barbero_cancela_y_se_avisa_al_cliente_y_al_barbero(
    client, db, reloj, h_barbero, barbero, cliente, corte, correos
):
    cita = crear_cita(db, cliente, barbero, corte, reloj.en(0), "07:00")
    r = cambiar(client, h_barbero, cita, "Cancelada")
    assert r.status_code == 200 and r.json()["estado"] == "Cancelada"
    assert sorted(c["para"] for c in correos) == sorted([cliente.email, barbero.usuario.email])


def test_cp_rf27_7_cita_inexistente(client, h_barbero):
    assert client.patch("/api/citas/999/estado", headers=h_barbero, json={"estado": "Atendida"}).status_code == 404


def test_cp_rf27_8_el_cliente_no_cambia_estados(client, db, reloj, h_cliente, barbero, cliente, corte):
    cita = crear_cita(db, cliente, barbero, corte, reloj.en(0), "07:00")
    assert cambiar(client, h_cliente, cita, "Atendida").status_code == 403
