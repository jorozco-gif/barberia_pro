"""RF-05 a RF-10 (barberos y servicios), RF-28 (citas globales) y RNF-03 (acceso por rol)."""
from decimal import Decimal

import models
from helpers import CLAVE, agendar, crear_cita

NUEVO_BARBERO = {"nombre": "Luis Navaja", "email": "luis@test.com", "password": CLAVE}


# ---------- RF-05 Registro de barberos ----------
def test_cp_rf05_1_registro_valido(client, h_admin, h_cliente):
    r = client.post("/api/admin/barberos", json=NUEVO_BARBERO, headers=h_admin)
    assert r.status_code == 201
    assert r.json()["activo"] is True and r.json()["foto_url"] is None
    assert "luis@test.com" in [b["email"] for b in client.get("/api/admin/barberos", headers=h_admin).json()]
    assert "Luis Navaja" in [b["nombre"] for b in client.get("/api/barberos", headers=h_cliente).json()]
    # CA-05.1: el barbero puede iniciar sesión
    login = client.post("/api/auth/login", json={"email": "luis@test.com", "password": CLAVE})
    assert login.status_code == 200 and login.json()["usuario"]["rol"] == models.ROL_BARBERO


def test_cp_rf05_2_correo_duplicado(client, h_admin, barbero, cliente):
    for email in (barbero.usuario.email, cliente.email, barbero.usuario.email.upper()):
        r = client.post("/api/admin/barberos", json={**NUEVO_BARBERO, "email": email}, headers=h_admin)
        assert r.status_code == 400


def test_cp_rf05_3_sin_nombre(client, h_admin):
    for cuerpo in ({k: v for k, v in NUEVO_BARBERO.items() if k != "nombre"}, {**NUEVO_BARBERO, "nombre": ""}):
        r = client.post("/api/admin/barberos", json=cuerpo, headers=h_admin)
        assert r.status_code == 422
        assert any("nombre" in e["loc"] for e in r.json()["detail"])


def test_cp_rf05_4_con_foto(client, h_admin):
    r = client.post("/api/admin/barberos", json={**NUEVO_BARBERO, "foto_url": "https://x.test/f.jpg"}, headers=h_admin)
    assert r.status_code == 201 and r.json()["foto_url"] == "https://x.test/f.jpg"


# ---------- RF-06 Modificación de barberos ----------
def test_cp_rf06_1_modificar_nombre_y_foto(client, h_admin, h_cliente, barbero):
    r = client.patch(f"/api/admin/barberos/{barbero.id}", headers=h_admin,
                     json={"nombre": "Mateo Renovado", "foto_url": "https://x.test/nueva.jpg"})
    assert r.status_code == 200
    visto_por_cliente = [b for b in client.get("/api/barberos", headers=h_cliente).json() if b["id"] == barbero.id][0]
    assert visto_por_cliente["nombre"] == "Mateo Renovado"
    assert visto_por_cliente["foto_url"] == "https://x.test/nueva.jpg"


def test_cp_rf06_2_nombre_vacio_o_nulo_no_se_acepta(client, h_admin, barbero):
    for nombre in ("", None):
        r = client.patch(f"/api/admin/barberos/{barbero.id}", json={"nombre": nombre}, headers=h_admin)
        assert r.status_code == 422
    assert client.get("/api/admin/barberos", headers=h_admin).json()[0]["nombre"] == "Mateo Maestro"


def test_cp_rf06_3_barbero_inexistente(client, h_admin):
    assert client.patch("/api/admin/barberos/999", json={"nombre": "Nadie Aquí"}, headers=h_admin).status_code == 404


# ---------- RF-07 Eliminación de barberos ----------
def test_cp_rf07_1_baja_cancela_citas_futuras_conserva_historial_y_avisa(
    client, db, reloj, h_admin, h_cliente, barbero, cliente, otro_cliente, corte, correos
):
    futura1 = crear_cita(db, cliente, barbero, corte, reloj.en(2), "10:00")
    futura2 = crear_cita(db, otro_cliente, barbero, corte, reloj.en(3), "11:00")
    pasada = crear_cita(db, cliente, barbero, corte, reloj.en(-5), "10:00", estado=models.ESTADO_ATENDIDA)

    r = client.delete(f"/api/admin/barberos/{barbero.id}", headers=h_admin)
    assert r.status_code == 200 and r.json()["activo"] is False

    db.expire_all()
    assert db.get(models.Cita, futura1.id).estado == models.ESTADO_CANCELADA
    assert db.get(models.Cita, futura2.id).estado == models.ESTADO_CANCELADA
    assert db.get(models.Cita, pasada.id).estado == models.ESTADO_ATENDIDA  # historial intacto
    assert db.query(models.Barbero).filter_by(id=barbero.id).count() == 1  # baja lógica, no se borra la fila
    assert sorted(c["para"] for c in correos) == sorted([cliente.email, otro_cliente.email])
    # CP-RF13-2: ya no aparece en la lista para agendar
    assert barbero.id not in [b["id"] for b in client.get("/api/barberos", headers=h_cliente).json()]


def test_cp_rf07_2_barbero_eliminado_no_puede_iniciar_sesion_y_su_sesion_se_cierra(client, h_admin, h_barbero, barbero):
    assert client.get("/api/barbero/agenda", headers=h_barbero).status_code == 200
    assert client.delete(f"/api/admin/barberos/{barbero.id}", headers=h_admin).status_code == 200
    assert client.get("/api/barbero/agenda", headers=h_barbero).status_code == 401
    r = client.post("/api/auth/login", json={"email": barbero.usuario.email, "password": CLAVE})
    assert r.status_code == 401


def test_cp_rf07_3_citas_atendidas_y_canceladas_no_generan_correo(client, db, reloj, h_admin, barbero, cliente, corte, correos):
    crear_cita(db, cliente, barbero, corte, reloj.en(2), "10:00", estado=models.ESTADO_CANCELADA)
    client.delete(f"/api/admin/barberos/{barbero.id}", headers=h_admin)
    assert correos == []


def test_cp_rf07_4_eliminar_dos_veces_o_inexistente(client, h_admin, barbero):
    assert client.delete(f"/api/admin/barberos/{barbero.id}", headers=h_admin).status_code == 200
    assert client.delete(f"/api/admin/barberos/{barbero.id}", headers=h_admin).status_code == 404
    assert client.delete("/api/admin/barberos/999", headers=h_admin).status_code == 404


# ---------- RF-08 Registro de servicios ----------
def crear(client, h_admin, **cambios):
    cuerpo = {"nombre": "Afeitado", "duracion_minutos": 30, "precio": "15000"}
    cuerpo.update(cambios)
    return client.post("/api/admin/servicios", json=cuerpo, headers=h_admin)


def test_cp_rf08_1_registro_valido(client, h_admin, h_cliente):
    r = crear(client, h_admin)
    assert r.status_code == 201 and r.json()["activo"] is True
    assert "Afeitado" in [s["nombre"] for s in client.get("/api/servicios", headers=h_cliente).json()]


def test_cp_rf08_2_precio_negativo(client, h_admin):
    assert crear(client, h_admin, precio="-1").status_code == 422


def test_cp_rf08_3_precio_vacio(client, h_admin):
    assert client.post("/api/admin/servicios", json={"nombre": "Afeitado", "duracion_minutos": 30},
                       headers=h_admin).status_code == 422


def test_cp_rf08_4_duracion_cero(client, h_admin):
    assert crear(client, h_admin, duracion_minutos=0).status_code == 422


def test_cp_rf08_5_duracion_minima(client, h_admin):
    assert crear(client, h_admin, nombre="Minimo", duracion_minutos=1).status_code == 201


def test_cp_rf08_6_duracion_maxima(client, h_admin):
    assert crear(client, h_admin, nombre="Maximo", duracion_minutos=240).status_code == 201


def test_cp_rf08_7_duracion_que_supera_el_maximo(client, h_admin):
    assert crear(client, h_admin, nombre="Excede", duracion_minutos=241).status_code == 422


def test_cp_rf08_8_precio_cero(client, h_admin):
    r = crear(client, h_admin, nombre="Cortesia", precio="0")
    assert r.status_code == 201 and Decimal(r.json()["precio"]) == 0


def test_cp_rf08_9_valores_no_numericos(client, h_admin):
    assert crear(client, h_admin, nombre="Duracion texto", duracion_minutos="abc").status_code == 422
    assert crear(client, h_admin, nombre="Precio texto", precio="abc").status_code == 422


# ---------- RF-09 Modificación de servicios ----------
def test_cp_rf09_1_cambio_de_precio_no_altera_citas_existentes(
    client, h_admin, h_cliente, h_otro_cliente, barbero, corte, reloj
):
    cita = agendar(client, h_cliente, barbero, corte, reloj.en(1), "10:00").json()
    assert Decimal(cita["total"]) == 20000

    r = client.patch(f"/api/admin/servicios/{corte.id}", json={"precio": "25000"}, headers=h_admin)
    assert r.status_code == 200 and Decimal(r.json()["precio"]) == 25000

    vieja = client.get(f"/api/citas/{cita['id']}", headers=h_cliente).json()
    assert Decimal(vieja["total"]) == 20000
    assert Decimal(vieja["servicios"][0]["precio_aplicado"]) == 20000
    nueva = agendar(client, h_otro_cliente, barbero, corte, reloj.en(1), "11:00").json()
    assert Decimal(nueva["total"]) == 25000


def test_cp_rf09_2_nombre_vacio(client, h_admin, corte):
    assert client.patch(f"/api/admin/servicios/{corte.id}", json={"nombre": ""}, headers=h_admin).status_code == 422
    assert client.patch(f"/api/admin/servicios/{corte.id}", json={"nombre": None}, headers=h_admin).status_code == 422
    assert client.patch(f"/api/admin/servicios/{corte.id}", json={"precio": "-5"}, headers=h_admin).status_code == 422


def test_cp_rf09_3_servicio_inexistente(client, h_admin):
    assert client.patch("/api/admin/servicios/999", json={"nombre": "Nada Aquí"}, headers=h_admin).status_code == 404


# ---------- RF-10 Eliminación de servicios ----------
def test_cp_rf10_1_baja_logica_conserva_citas(client, db, reloj, h_admin, h_cliente, barbero, cliente, corte):
    cita = crear_cita(db, cliente, barbero, corte, reloj.en(2), "10:00")
    assert client.delete(f"/api/admin/servicios/{corte.id}", headers=h_admin).status_code == 200
    assert corte.id not in [s["id"] for s in client.get("/api/servicios", headers=h_cliente).json()]
    detalle = client.get(f"/api/citas/{cita.id}", headers=h_cliente).json()
    assert detalle["estado"] == models.ESTADO_PROGRAMADA
    assert detalle["servicios"][0]["servicio"]["nombre"] == "Corte"


def test_cp_rf10_2_servicio_eliminado_no_se_puede_agendar(client, h_admin, h_cliente, barbero, corte, reloj):
    client.delete(f"/api/admin/servicios/{corte.id}", headers=h_admin)
    assert agendar(client, h_cliente, barbero, corte, reloj.en(1), "10:00").status_code == 404
    assert client.delete(f"/api/admin/servicios/{corte.id}", headers=h_admin).status_code == 404


# ---------- RF-28 Consulta global de citas ----------
def test_cp_rf28_1_filtros(client, db, reloj, h_admin, barbero, otro_barbero, cliente, corte):
    a = crear_cita(db, cliente, barbero, corte, reloj.en(1), "10:00")
    b = crear_cita(db, cliente, barbero, corte, reloj.en(2), "10:00", estado=models.ESTADO_CANCELADA)
    c = crear_cita(db, cliente, otro_barbero, corte, reloj.en(1), "10:00")

    todas = client.get("/api/admin/citas", headers=h_admin).json()
    assert {x["id"] for x in todas} == {a.id, b.id, c.id}
    solo_barbero = client.get("/api/admin/citas", params={"barbero_id": barbero.id}, headers=h_admin).json()
    assert {x["id"] for x in solo_barbero} == {a.id, b.id}
    cancelada = client.get("/api/admin/citas", params={"barbero_id": barbero.id, "estado": "Cancelada"},
                           headers=h_admin).json()
    assert [x["id"] for x in cancelada] == [b.id]
    por_fecha = client.get("/api/admin/citas", params={"fecha": reloj.en(1).isoformat()}, headers=h_admin).json()
    assert {x["id"] for x in por_fecha} == {a.id, c.id}


def test_cp_rf28_2_sin_resultados(client, h_admin):
    r = client.get("/api/admin/citas", params={"estado": "Atendida"}, headers=h_admin)
    assert r.status_code == 200 and r.json() == []


def test_cp_rf28_3_solo_el_administrador(client, h_cliente, h_barbero):
    assert client.get("/api/admin/citas", headers=h_cliente).status_code == 403
    assert client.get("/api/admin/citas", headers=h_barbero).status_code == 403
    assert client.get("/api/admin/citas").status_code == 401


# ---------- RNF-03 Control de acceso por rol ----------
def test_cp_rnf03_1_el_administrador_accede_a_su_panel(client, h_admin):
    assert client.get("/api/admin/barberos", headers=h_admin).status_code == 200
    assert crear(client, h_admin).status_code == 201


def test_cp_rnf03_2_cliente_y_barbero_no_acceden_al_panel_de_administracion(client, h_cliente, h_barbero):
    for h in (h_cliente, h_barbero):
        assert client.get("/api/admin/barberos", headers=h).status_code == 403
        assert client.post("/api/admin/barberos", json=NUEVO_BARBERO, headers=h).status_code == 403
        assert client.post("/api/admin/servicios", json={"nombre": "X Y", "duracion_minutos": 10, "precio": "1"},
                           headers=h).status_code == 403
        assert client.delete("/api/admin/servicios/1", headers=h).status_code == 403


def test_cp_rnf03_3_cada_rol_solo_usa_sus_endpoints(client, h_admin, h_cliente, h_barbero):
    assert client.get("/api/barbero/agenda", headers=h_cliente).status_code == 403
    assert client.get("/api/barbero/agenda", headers=h_admin).status_code == 403
    assert client.get("/api/citas/mias", headers=h_barbero).status_code == 403
    assert client.get("/api/citas/mias", headers=h_admin).status_code == 403
    assert client.post("/api/citas", json={}, headers=h_barbero).status_code == 403
