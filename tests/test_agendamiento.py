"""RF-13 a RF-21 (agendamiento), RNF-05, RNF-07 y RNF-08."""
import datetime
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import models
import services
from fastapi.testclient import TestClient
from helpers import (
    agendar, crear_barbero, crear_cita, crear_cliente, crear_servicio, hora, iniciar_sesion,
)
from main import app


def horarios(client, h, barbero, fecha, franja, servicios):
    r = client.get("/api/disponibilidad", headers=h, params={
        "barbero_id": barbero.id, "fecha": fecha.isoformat(), "franja": franja,
        "servicios_ids": [s.id for s in servicios],
    })
    assert r.status_code == 200, r.text
    return [s["hora_inicio"] for s in r.json()]


# ---------- RF-13 Lista de barberos ----------
def test_cp_rf13_1_lista_de_barberos_activos(client, db, h_cliente, barbero, otro_barbero):
    r = client.get("/api/barberos", headers=h_cliente)
    assert r.status_code == 200
    assert {b["nombre"] for b in r.json()} == {"Mateo Maestro", "Carlos Barba"}
    assert all(set(b) == {"id", "nombre", "foto_url"} for b in r.json())  # sin correo ni datos internos


def test_cp_rf13_2_no_aparecen_barberos_inactivos(client, db, h_cliente, barbero, otro_barbero):
    otro_barbero.activo = False
    db.commit()
    assert [b["id"] for b in client.get("/api/barberos", headers=h_cliente).json()] == [barbero.id]


# ---------- RF-14 / RF-15 Servicios y resumen ----------
def test_cp_rf14_1_lista_de_servicios_activos(client, db, h_cliente, corte, barba):
    inactivo = crear_servicio(db, "Descontinuado", 30, "5000")
    inactivo.activo = False
    db.commit()
    nombres = {s["nombre"] for s in client.get("/api/servicios", headers=h_cliente).json()}
    assert nombres == {"Corte", "Barba"}


def test_cp_rf14_2_sin_servicios_no_se_puede_continuar(client, h_cliente, barbero, reloj):
    assert client.get("/api/citas/resumen", headers=h_cliente).status_code == 422
    r = client.post("/api/citas", headers=h_cliente, json={
        "barbero_id": barbero.id, "servicios_ids": [], "fecha": reloj.en(1).isoformat(), "hora_inicio": "10:00"})
    assert r.status_code == 422


def test_cp_rf15_1_total_y_duracion(client, h_cliente, corte, barba):
    r = client.get("/api/citas/resumen", headers=h_cliente, params={"servicios_ids": [corte.id, barba.id]})
    assert r.status_code == 200
    assert Decimal(r.json()["total"]) == 30000 and r.json()["duracion_total_minutos"] == 45
    assert len(r.json()["servicios"]) == 2


def test_cp_rf15_2_servicio_inexistente_o_repetido(client, h_cliente, corte):
    assert client.get("/api/citas/resumen", headers=h_cliente, params={"servicios_ids": [999]}).status_code == 404
    repetido = client.get("/api/citas/resumen", headers=h_cliente, params={"servicios_ids": [corte.id, corte.id]})
    assert repetido.status_code in (400, 422)


# ---------- RF-16 Fecha ----------
def test_cp_rf16_1_fecha_futura(client, reloj, h_cliente, barbero, corte):
    assert horarios(client, h_cliente, barbero, reloj.en(1), "Mañana", [corte])


def test_cp_rf16_2_fecha_pasada(client, reloj, h_cliente, barbero, corte):
    r = client.get("/api/disponibilidad", headers=h_cliente, params={
        "barbero_id": barbero.id, "fecha": reloj.en(-1).isoformat(), "franja": "Mañana", "servicios_ids": [corte.id]})
    assert r.status_code == 400
    assert agendar(client, h_cliente, barbero, corte, reloj.en(-1), "10:00").status_code == 400


def test_cp_rf16_3_hoy_un_minuto_antes_de_la_hora_actual(client, reloj, h_cliente, barbero, corte):
    reloj.ahora = reloj.ahora.replace(hour=9, minute=29)
    h = iniciar_sesion(client, "cliente@test.com")
    assert agendar(client, h, barbero, corte, reloj.en(0), "09:28").status_code == 400
    assert agendar(client, h, barbero, corte, reloj.en(0), "09:29").status_code == 400  # igual a "ahora": ya empezó


def test_cp_rf16_4_hoy_un_minuto_despues_de_la_hora_actual(client, reloj, h_cliente, barbero, corte):
    reloj.ahora = reloj.ahora.replace(hour=9, minute=29)
    h = iniciar_sesion(client, "cliente@test.com")
    assert agendar(client, h, barbero, corte, reloj.en(0), "09:30").status_code == 201


def test_cp_rf16_5_hoy_no_se_ofrecen_horarios_que_ya_pasaron(client, reloj, h_cliente, barbero, corte):
    reloj.ahora = reloj.ahora.replace(hour=9, minute=10)
    h = iniciar_sesion(client, "cliente@test.com")
    assert horarios(client, h, barbero, reloj.en(0), "Mañana", [corte])[0] == "09:30"


# ---------- RF-17 Franjas ----------
def test_cp_rf17_1_franja_tarde(client, reloj, h_cliente, barbero, corte):
    inicios = horarios(client, h_cliente, barbero, reloj.en(1), "Tarde", [corte])
    assert inicios[0] == "12:00" and inicios[-1] == "17:30"
    assert len(inicios) == 12


def test_cp_rf17_2_sin_franja_o_franja_invalida(client, reloj, h_cliente, barbero, corte):
    base = {"barbero_id": barbero.id, "fecha": reloj.en(1).isoformat(), "servicios_ids": [corte.id]}
    assert client.get("/api/disponibilidad", headers=h_cliente, params=base).status_code == 422
    assert client.get("/api/disponibilidad", headers=h_cliente, params={**base, "franja": "Madrugada"}).status_code == 422


def test_cp_rf17_3_limite_entre_manana_y_tarde(client, db, reloj, h_cliente, corte):
    barbero = crear_barbero(db, "once@test.com", "Once Treinta", horario=False)
    db.add(models.Disponibilidad(barbero_id=barbero.id, dia_semana=reloj.en(1).weekday(),
                                 hora_inicio=hora("11:30"), hora_fin=hora("12:30")))
    db.commit()
    assert horarios(client, h_cliente, barbero, reloj.en(1), "Mañana", [corte]) == ["11:30"]
    assert horarios(client, h_cliente, barbero, reloj.en(1), "Tarde", [corte]) == ["12:00"]


def test_cp_rf17_4_franja_noche(client, reloj, h_cliente, barbero, corte):
    inicios = horarios(client, h_cliente, barbero, reloj.en(1), "Noche", [corte])
    assert inicios == ["18:00", "18:30", "19:00", "19:30"]  # el barbero atiende hasta las 20:00


# ---------- RF-18 Horarios libres ----------
def barbero_14_a_17(db, reloj):
    b = crear_barbero(db, "tarde@test.com", "Tarde Tres", horario=False)
    db.add(models.Disponibilidad(barbero_id=b.id, dia_semana=reloj.en(1).weekday(),
                                 hora_inicio=hora("14:00"), hora_fin=hora("17:00")))
    db.commit()
    return b


def test_cp_rf18_1_solo_horarios_que_alcanzan_para_la_duracion(client, db, reloj, h_cliente):
    b = barbero_14_a_17(db, reloj)
    servicio = crear_servicio(db, "Combo", 45, "30000")
    r = client.get("/api/disponibilidad", headers=h_cliente, params={
        "barbero_id": b.id, "fecha": reloj.en(1).isoformat(), "franja": "Tarde", "servicios_ids": [servicio.id]})
    assert [s["hora_inicio"] for s in r.json()] == ["14:00", "14:30", "15:00", "15:30", "16:00"]
    assert r.json()[-1]["hora_fin"] == "16:45"  # 16:30 no alcanza: terminaría a las 17:15
    assert all(s["disponible"] is True for s in r.json())


def test_cp_rf18_2_no_se_muestran_horarios_reservados_ni_huecos_insuficientes(client, db, reloj, h_cliente, cliente):
    b = barbero_14_a_17(db, reloj)
    servicio = crear_servicio(db, "Combo", 45, "30000")
    corto = crear_servicio(db, "Corto", 30, "10000")
    crear_cita(db, cliente, b, corto, reloj.en(1), "15:00")  # 15:00 a 15:30
    assert horarios(client, h_cliente, b, reloj.en(1), "Tarde", [servicio]) == ["14:00", "15:30", "16:00"]


def test_cp_rf18_3_no_se_muestran_horas_bloqueadas(client, db, reloj, h_cliente):
    b = barbero_14_a_17(db, reloj)
    servicio = crear_servicio(db, "Combo", 45, "30000")
    db.add(models.Bloqueo(barbero_id=b.id, fecha=reloj.en(1), hora_inicio=hora("15:00"), hora_fin=hora("16:00")))
    db.commit()
    assert horarios(client, h_cliente, b, reloj.en(1), "Tarde", [servicio]) == ["14:00", "16:00"]


def test_cp_rf18_4_barbero_inexistente_o_inactivo(client, db, reloj, h_cliente, barbero, corte):
    base = {"fecha": reloj.en(1).isoformat(), "franja": "Tarde", "servicios_ids": [corte.id]}
    assert client.get("/api/disponibilidad", headers=h_cliente, params={**base, "barbero_id": 999}).status_code == 404
    barbero.activo = False
    db.commit()
    assert client.get("/api/disponibilidad", headers=h_cliente, params={**base, "barbero_id": barbero.id}).status_code == 404


def test_cp_rf18_5_dia_sin_atencion(client, reloj, h_cliente, barbero, corte):
    domingo = reloj.en(6)
    assert domingo.weekday() == 6
    assert horarios(client, h_cliente, barbero, domingo, "Mañana", [corte]) == []


# ---------- RF-19 Agendamiento ----------
def test_cp_rf19_1_cita_creada_programada_con_codigo(client, db, reloj, h_cliente, barbero, corte, barba):
    r = agendar(client, h_cliente, barbero, [corte, barba], reloj.en(1), "10:00", notas="Degradado")
    assert r.status_code == 201
    cita = r.json()
    assert cita["estado"] == "Programada" and cita["reprogramada"] is False
    assert re.fullmatch(r"BSP-[0-9A-F]{6}", cita["codigo_reserva"])
    assert cita["notas"] == "Degradado" and cita["cliente"]["email"] == "cliente@test.com"
    assert Decimal(cita["total"]) == 30000
    assert (cita["hora_inicio"], cita["hora_fin"]) == ("10:00:00", "10:45:00")
    assert len(cita["servicios"]) == 2


def test_cp_rf19_2_limite_de_dos_citas_activas(client, reloj, h_cliente, barbero, corte, correos):
    assert agendar(client, h_cliente, barbero, corte, reloj.en(1), "10:00").status_code == 201
    assert agendar(client, h_cliente, barbero, corte, reloj.en(1), "11:00").status_code == 201
    enviados = len(correos)
    r = agendar(client, h_cliente, barbero, corte, reloj.en(1), "12:00")
    assert r.status_code == 409 and "límite" in r.json()["detail"].lower()
    assert len(correos) == enviados  # CP-RF21-2: la cita rechazada no genera correo


def test_cp_rf19_3_al_cancelar_una_se_puede_agendar_otra(client, reloj, h_cliente, barbero, corte):
    primera = agendar(client, h_cliente, barbero, corte, reloj.en(1), "10:00").json()
    agendar(client, h_cliente, barbero, corte, reloj.en(1), "11:00")
    assert agendar(client, h_cliente, barbero, corte, reloj.en(1), "12:00").status_code == 409
    assert client.post(f"/api/citas/{primera['id']}/cancelar", headers=h_cliente).status_code == 200
    assert agendar(client, h_cliente, barbero, corte, reloj.en(1), "12:00").status_code == 201


def test_cp_rf19_4_solo_cuentan_las_citas_programadas(client, db, reloj, h_cliente, barbero, cliente, corte):
    for i, estado in enumerate((models.ESTADO_ATENDIDA, models.ESTADO_ATENDIDA, models.ESTADO_CANCELADA,
                                models.ESTADO_INASISTENCIA)):
        crear_cita(db, cliente, barbero, corte, reloj.en(-10 - i), "10:00", estado=estado)
    crear_cita(db, cliente, barbero, corte, reloj.en(2), "10:00")
    assert agendar(client, h_cliente, barbero, corte, reloj.en(1), "10:00").status_code == 201


def test_cp_rf19_5_hora_fin_con_servicio_de_30_minutos(client, reloj, h_cliente, barbero, corte):
    r = agendar(client, h_cliente, barbero, corte, reloj.en(1), "09:00")
    assert r.status_code == 201 and r.json()["hora_fin"] == "09:30:00"


def test_cp_rf19_6_hora_fin_con_45_minutos(client, db, reloj, h_cliente, barbero):
    combo = crear_servicio(db, "Combo", 45, "30000")
    r = agendar(client, h_cliente, barbero, combo, reloj.en(1), "10:00")
    assert r.status_code == 201 and r.json()["hora_fin"] == "10:45:00"


def test_cp_rf19_7_el_precio_y_la_duracion_quedan_guardados_con_la_cita(client, db, reloj, h_cliente, barbero, corte):
    cita = agendar(client, h_cliente, barbero, corte, reloj.en(1), "10:00").json()
    corte.precio, corte.duracion_minutos = Decimal("99000"), 90
    db.commit()
    guardada = db.get(models.Cita, cita["id"])
    assert guardada.total == Decimal("20000") and guardada.servicios[0].duracion_minutos == 30


def test_cp_rf19_8_validaciones_del_cuerpo(client, reloj, h_cliente, barbero, corte):
    base = {"barbero_id": barbero.id, "servicios_ids": [corte.id], "fecha": reloj.en(1).isoformat(),
            "hora_inicio": "10:00"}
    for cambio in ({"servicios_ids": [corte.id, corte.id]}, {"hora_inicio": None}, {"fecha": "no-es-fecha"},
                   {"barbero_id": 0}, {"notas": "x" * 501}):
        assert client.post("/api/citas", headers=h_cliente, json={**base, **cambio}).status_code == 422, cambio
    sin_barbero = {k: v for k, v in base.items() if k != "barbero_id"}
    assert client.post("/api/citas", headers=h_cliente, json=sin_barbero).status_code == 422


def test_cp_rf19_9_solo_el_cliente_agenda(client, reloj, h_barbero, h_admin, barbero, corte):
    assert agendar(client, h_barbero, barbero, corte, reloj.en(1), "10:00").status_code == 403
    assert agendar(client, h_admin, barbero, corte, reloj.en(1), "10:00").status_code == 403


# ---------- RF-20 Choques de horario ----------
def reservar_10_a_10_30(client, db, reloj, barbero, corte, email="primero@test.com"):
    crear_cliente(db, email, "Primero")
    return agendar(client, iniciar_sesion(client, email), barbero, corte, reloj.en(1), "10:00")


def test_cp_rf20_1_el_horario_reservado_desaparece_para_otros(client, db, reloj, h_cliente, barbero, corte):
    assert "10:00" in horarios(client, h_cliente, barbero, reloj.en(1), "Mañana", [corte])
    reservar_10_a_10_30(client, db, reloj, barbero, corte)
    assert "10:00" not in horarios(client, h_cliente, barbero, reloj.en(1), "Mañana", [corte])


def test_cp_rf20_2_segundo_intento_sobre_el_mismo_horario(client, db, reloj, h_cliente, barbero, corte):
    assert reservar_10_a_10_30(client, db, reloj, barbero, corte).status_code == 201
    r = agendar(client, h_cliente, barbero, corte, reloj.en(1), "10:00")
    assert r.status_code == 409 and "ya no está disponible" in r.json()["detail"]
    assert db.query(models.Cita).count() == 1


def test_cp_rf20_3_cita_contigua_posterior(client, db, reloj, h_cliente, barbero, corte):
    reservar_10_a_10_30(client, db, reloj, barbero, corte)
    assert agendar(client, h_cliente, barbero, corte, reloj.en(1), "10:30").status_code == 201


def test_cp_rf20_4_solape_de_un_minuto_al_final(client, db, reloj, h_cliente, barbero, corte):
    reservar_10_a_10_30(client, db, reloj, barbero, corte)
    assert agendar(client, h_cliente, barbero, corte, reloj.en(1), "10:29").status_code == 409


def test_cp_rf20_5_cita_contenida_dentro_de_otra(client, db, reloj, h_cliente, barbero, corte):
    reservar_10_a_10_30(client, db, reloj, barbero, corte)
    veinte = crear_servicio(db, "Veinte", 20, "8000")
    assert agendar(client, h_cliente, barbero, veinte, reloj.en(1), "10:05").status_code == 409


def test_cp_rf20_6_agendas_independientes_por_barbero(client, db, reloj, h_cliente, barbero, otro_barbero, corte):
    reservar_10_a_10_30(client, db, reloj, barbero, corte)
    assert agendar(client, h_cliente, otro_barbero, corte, reloj.en(1), "10:00").status_code == 201


def test_cp_rf20_7_cita_contigua_anterior(client, db, reloj, h_cliente, barbero, corte):
    reservar_10_a_10_30(client, db, reloj, barbero, corte)
    assert agendar(client, h_cliente, barbero, corte, reloj.en(1), "09:30").status_code == 201


def test_cp_rf20_8_solape_de_un_minuto_al_inicio(client, db, reloj, h_cliente, barbero, corte):
    reservar_10_a_10_30(client, db, reloj, barbero, corte)
    assert agendar(client, h_cliente, barbero, corte, reloj.en(1), "09:31").status_code == 409


def test_cp_rf20_9_mitad_de_intervalo_con_choque_es_409_y_sin_choque_es_400(client, db, reloj, h_cliente, barbero, corte):
    """PN-02 se evalúa después del choque: 10:15 sobre una cita de 10:00 a 10:30 es 409 (CA-20.3);
    10:15 en un horario libre se rechaza por no coincidir con el intervalo de 30 minutos."""
    reservar_10_a_10_30(client, db, reloj, barbero, corte)
    assert agendar(client, h_cliente, barbero, corte, reloj.en(1), "10:15").status_code == 409
    fuera_de_intervalo = agendar(client, h_cliente, barbero, corte, reloj.en(1), "14:15")
    assert fuera_de_intervalo.status_code == 400 and "30 minutos" in fuera_de_intervalo.json()["detail"]


def test_cp_rf20_10_fuera_de_la_disponibilidad_o_bloqueado(client, db, reloj, h_cliente, barbero, corte):
    assert agendar(client, h_cliente, barbero, corte, reloj.en(1), "07:30").status_code == 409  # antes de abrir
    assert agendar(client, h_cliente, barbero, corte, reloj.en(1), "19:30").status_code == 201  # termina 20:00
    assert agendar(client, h_cliente, barbero, corte, reloj.en(1), "20:00").status_code == 409  # después de cerrar
    assert agendar(client, h_cliente, barbero, corte, reloj.en(6), "10:00").status_code == 409  # domingo
    db.add(models.Bloqueo(barbero_id=barbero.id, fecha=reloj.en(2), hora_inicio=hora("10:00"), hora_fin=hora("11:00")))
    db.commit()
    assert agendar(client, h_cliente, barbero, corte, reloj.en(2), "10:30").status_code == 409
    assert agendar(client, h_cliente, barbero, corte, reloj.en(2), "09:30").status_code == 201  # termina a las 10:00


def test_cp_rf20_11_las_citas_canceladas_liberan_el_horario(client, db, reloj, h_cliente, barbero, cliente, corte):
    crear_cita(db, crear_cliente(db, "x@test.com", "Equis"), barbero, corte, reloj.en(1), "10:00",
               estado=models.ESTADO_CANCELADA)
    assert agendar(client, h_cliente, barbero, corte, reloj.en(1), "10:00").status_code == 201


def test_cp_rf20_12_el_contador_de_choques_funciona_con_varios_clientes_en_secuencia(client, db, reloj, barbero, corte):
    resultados = []
    for i in range(4):
        email = f"c{i}@test.com"
        crear_cliente(db, email, f"Cliente {i}")
        resultados.append(agendar(client, iniciar_sesion(client, email), barbero, corte, reloj.en(1), "10:00").status_code)
    assert resultados == [201, 409, 409, 409]
    assert db.query(models.Cita).count() == 1


def test_cp_rf20_13_solicitudes_simultaneas_sobre_el_mismo_horario(client, db, reloj, barbero, corte):
    """CA-20.2 con peticiones realmente concurrentes: solo una puede quedarse con el horario."""
    cabeceras = []
    for i in range(6):
        email = f"simultaneo{i}@test.com"
        crear_cliente(db, email, f"Simultáneo {i}")
        cabeceras.append(iniciar_sesion(client, email))
    salida = threading.Barrier(len(cabeceras))

    def reservar(h):
        salida.wait()
        return agendar(TestClient(app), h, barbero, corte, reloj.en(1), "10:00").status_code

    with ThreadPoolExecutor(max_workers=len(cabeceras)) as pool:
        codigos = sorted(pool.map(reservar, cabeceras))
    assert codigos == [201, 409, 409, 409, 409, 409]
    assert db.query(models.Cita).count() == 1


# ---------- RF-21 Confirmación por correo y RNF-05 ----------
def test_cp_rf21_1_correo_de_confirmacion(client, reloj, h_cliente, cliente, barbero, corte, barba, correos):
    cita = agendar(client, h_cliente, barbero, [corte, barba], reloj.en(1), "15:00").json()
    assert len(correos) == 1 and correos[0]["para"] == cliente.email
    cuerpo = correos[0]["cuerpo"]
    for dato in ("Mateo Maestro", "Corte", "Barba", "08/01/2030", "$30.000", cita["codigo_reserva"]):
        assert dato in cuerpo
    assert "3:00 p. m." in cuerpo  # CP-RNF05-1: hora de Colombia en formato de 12 horas


def test_cp_rf21_3_un_fallo_del_correo_no_deshace_la_cita(client, db, monkeypatch, reloj, h_cliente, barbero, corte):
    def falla(*args, **kwargs):
        raise RuntimeError("SMTP caído")
    monkeypatch.setattr(services.notificaciones, "confirmacion_cita", falla)
    assert agendar(client, h_cliente, barbero, corte, reloj.en(1), "10:00").status_code == 201
    assert db.query(models.Cita).count() == 1


# ---------- RNF-07 Integridad referencial ----------
def test_cp_rnf07_1_cita_con_claves_validas(client, db, reloj, h_cliente, cliente, barbero, corte):
    cita = agendar(client, h_cliente, barbero, corte, reloj.en(1), "10:00").json()
    guardada = db.get(models.Cita, cita["id"])
    assert guardada.cliente_id == cliente.id and guardada.barbero_id == barbero.id


def test_cp_rnf07_2_barbero_inexistente(client, db, reloj, h_cliente, corte):
    r = client.post("/api/citas", headers=h_cliente, json={
        "barbero_id": 999, "servicios_ids": [corte.id], "fecha": reloj.en(1).isoformat(), "hora_inicio": "10:00"})
    assert r.status_code == 404
    assert db.query(models.Cita).count() == 0


# ---------- RNF-08 Rendimiento ----------
def cargar_500_citas(db, barbero, cliente, reloj):
    citas = []
    for dia in range(1, 51):  # 50 días x 10 citas
        for n in range(10):
            inicio = datetime.time(8 + n // 2, 30 * (n % 2))
            fin = (datetime.datetime.combine(reloj.en(dia), inicio) + datetime.timedelta(minutes=30)).time()
            citas.append(models.Cita(
                codigo_reserva=f"BSP-{len(citas):06X}", cliente_id=cliente.id, barbero_id=barbero.id,
                fecha=reloj.en(dia), hora_inicio=inicio, hora_fin=fin,
                estado=models.ESTADO_PROGRAMADA, total=Decimal("20000"),
            ))
    db.add_all(citas)
    db.commit()
    assert db.query(models.Cita).count() == 500


def test_cp_rnf08_1_disponibilidad_con_500_citas_en_menos_de_300_ms(client, db, reloj, h_cliente, barbero, cliente, corte):
    cargar_500_citas(db, barbero, cliente, reloj)
    params = {"barbero_id": barbero.id, "fecha": reloj.en(1).isoformat(), "franja": "Tarde", "servicios_ids": [corte.id]}
    client.get("/api/disponibilidad", headers=h_cliente, params=params)  # calentamiento
    inicio = time.perf_counter()
    r = client.get("/api/disponibilidad", headers=h_cliente, params=params)
    duracion = time.perf_counter() - inicio
    assert r.status_code == 200
    assert duracion < 0.3, f"tardó {duracion * 1000:.0f} ms"


def test_cp_rnf08_2_veinte_consultas_simultaneas(db, reloj, barbero, cliente, corte):
    cargar_500_citas(db, barbero, cliente, reloj)
    cabeceras = []
    cliente_http = TestClient(app)
    for i in range(20):
        email = f"carga{i}@test.com"
        crear_cliente(db, email, f"Carga {i}")
        cabeceras.append(iniciar_sesion(cliente_http, email))
    params = {"barbero_id": barbero.id, "fecha": reloj.en(1).isoformat(), "franja": "Tarde", "servicios_ids": [corte.id]}

    def consultar(h):
        inicio = time.perf_counter()
        r = TestClient(app).get("/api/disponibilidad", headers=h, params=params)
        return r.status_code, time.perf_counter() - inicio

    with ThreadPoolExecutor(max_workers=20) as pool:
        resultados = list(pool.map(consultar, cabeceras))
    assert all(codigo == 200 for codigo, _ in resultados)
    assert max(t for _, t in resultados) < 0.3, [round(t * 1000) for _, t in resultados]
