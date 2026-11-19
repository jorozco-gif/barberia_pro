"""v1.2: RF-33 (gestión de estilos por el administrador) y RF-34 (elección del estilo al reservar, PN-14)."""
import pytest
from sqlalchemy.exc import IntegrityError

import models
from helpers import agendar, crear_estilo, iniciar_sesion

FADE = {"nombre": "Fade bajo", "descripcion": "Degradado que empieza cerca de la oreja."}


def crear(client, h_admin, **cambios):
    return client.post("/api/admin/estilos", json={**FADE, **cambios}, headers=h_admin)


# ---------- RF-33 Gestión de estilos ----------
def test_cp_rf33_1_registro_valido(client, h_admin, h_cliente):
    r = crear(client, h_admin, nombre="  Pompadour ", descripcion=" Volumen hacia atrás. ",
              foto_url="https://x.test/pompadour.jpg")
    assert r.status_code == 201, r.text
    estilo = r.json()
    assert (estilo["nombre"], estilo["descripcion"], estilo["foto_url"], estilo["activo"]) == (
        "Pompadour", "Volumen hacia atrás.", "https://x.test/pompadour.jpg", True)
    catalogo = client.get("/api/estilos", headers=h_cliente)
    assert catalogo.status_code == 200
    assert [e["nombre"] for e in catalogo.json()] == ["Pompadour"]
    assert catalogo.json()[0]["descripcion"] == "Volumen hacia atrás."  # el cliente la ve en el modal


def test_cp_rf33_2_la_foto_es_opcional(client, h_admin):
    for foto in (None, "", "   "):
        r = crear(client, h_admin, foto_url=foto)
        assert r.status_code == 201 and r.json()["foto_url"] is None, foto
    assert crear(client, h_admin, nombre="Sin foto").json()["foto_url"] is None


def test_cp_rf33_3_nombre_y_descripcion_obligatorios(client, h_admin):
    for cambio in ({"nombre": ""}, {"nombre": "   "}, {"nombre": None}, {"nombre": "x" * 101},
                   {"descripcion": ""}, {"descripcion": "   "}, {"descripcion": None}, {"descripcion": "x" * 1001},
                   {"foto_url": "x" * 256}):
        assert crear(client, h_admin, **cambio).status_code == 422, cambio
    for campo in ("nombre", "descripcion"):
        incompleto = {k: v for k, v in FADE.items() if k != campo}
        assert client.post("/api/admin/estilos", json=incompleto, headers=h_admin).status_code == 422, campo


def test_cp_rf33_4_modificar_estilo(client, db, h_admin, h_cliente):
    estilo = crear_estilo(db, foto_url="https://x.test/fade.jpg")
    url = f"/api/admin/estilos/{estilo.id}"
    r = client.patch(url, json={"nombre": "Fade medio", "descripcion": "Degradado a media altura."}, headers=h_admin)
    assert r.status_code == 200
    assert (r.json()["nombre"], r.json()["descripcion"], r.json()["foto_url"]) == (
        "Fade medio", "Degradado a media altura.", "https://x.test/fade.jpg")  # lo no enviado se conserva
    assert client.patch(url, json={"foto_url": None}, headers=h_admin).json()["foto_url"] is None
    assert client.get("/api/estilos", headers=h_cliente).json()[0]["nombre"] == "Fade medio"


def test_cp_rf33_5_modificar_con_datos_no_validos(client, db, h_admin):
    estilo = crear_estilo(db)
    for cambio in ({"nombre": ""}, {"nombre": None}, {"descripcion": " "}, {"descripcion": None}):
        assert client.patch(f"/api/admin/estilos/{estilo.id}", json=cambio, headers=h_admin).status_code == 422, cambio
    db.refresh(estilo)
    assert (estilo.nombre, estilo.descripcion) == ("Fade bajo", "Degradado bajo cerca de la oreja.")


def test_cp_rf33_6_eliminar_estilo_es_logico_y_conserva_las_citas(client, db, reloj, h_admin, h_cliente, barbero, corte):
    estilo = crear_estilo(db)
    cita = agendar(client, h_cliente, barbero, corte, reloj.en(1), "10:00", estilo_id=estilo.id).json()

    r = client.delete(f"/api/admin/estilos/{estilo.id}", headers=h_admin)
    assert r.status_code == 200 and r.json()["activo"] is False
    assert client.get("/api/estilos", headers=h_cliente).json() == []
    db.expire_all()
    assert db.get(models.Estilo, estilo.id) is not None  # sigue en la base de datos
    vista = client.get(f"/api/citas/{cita['id']}", headers=h_cliente).json()
    assert vista["estilo_id"] == estilo.id and vista["estilo"]["nombre"] == "Fade bajo"


def test_cp_rf33_7_estilo_inexistente_o_eliminado(client, db, h_admin):
    eliminado = crear_estilo(db, activo=False)
    for estilo_id in (999, eliminado.id):
        assert client.patch(f"/api/admin/estilos/{estilo_id}", json={"nombre": "Nuevo"}, headers=h_admin).status_code == 404
        assert client.delete(f"/api/admin/estilos/{estilo_id}", headers=h_admin).status_code == 404


def test_cp_rf33_8_el_catalogo_lo_ven_el_cliente_y_el_administrador(client, db, h_admin, h_cliente, h_barbero):
    crear_estilo(db, "Buzz cut", "Corte uniforme a máquina.")
    crear_estilo(db, "Retirado", "Ya no se ofrece.", activo=False)
    for h in (h_cliente, h_admin):
        assert [e["nombre"] for e in client.get("/api/estilos", headers=h).json()] == ["Buzz cut"]
    assert client.get("/api/estilos", headers=h_barbero).status_code == 403
    assert client.get("/api/estilos").status_code == 401


# ---------- RF-34 Elección del estilo al reservar ----------
def test_cp_rf34_1_cita_con_estilo(client, db, reloj, h_admin, h_cliente, barbero, corte):
    estilo = crear_estilo(db, "Pompadour", "Volumen hacia atrás.", foto_url="https://x.test/p.jpg")
    r = agendar(client, h_cliente, barbero, corte, reloj.en(1), "10:00", estilo_id=estilo.id)
    assert r.status_code == 201, r.text
    cita = r.json()
    assert cita["estilo_id"] == estilo.id
    assert cita["estilo"] == {"id": estilo.id, "nombre": "Pompadour", "foto_url": "https://x.test/p.jpg"}
    assert db.get(models.Cita, cita["id"]).estilo_id == estilo.id
    # El estilo se ve en todas las vistas de la cita
    assert client.get("/api/citas/mias", headers=h_cliente).json()[0]["estilo"]["nombre"] == "Pompadour"
    h_barbero = iniciar_sesion(client, barbero.email)
    agenda = client.get("/api/barbero/agenda", params={"fecha": reloj.en(1).isoformat()}, headers=h_barbero).json()
    assert agenda[0]["estilo"]["nombre"] == "Pompadour"
    assert client.get("/api/admin/citas", headers=h_admin).json()[0]["estilo"]["nombre"] == "Pompadour"


def test_cp_rf34_2_con_catalogo_el_estilo_es_obligatorio(client, db, reloj, h_cliente, barbero, corte, correos):
    crear_estilo(db)
    r = agendar(client, h_cliente, barbero, corte, reloj.en(1), "10:00")
    assert r.status_code == 400 and "estilo" in r.json()["detail"].lower()
    assert db.query(models.Cita).count() == 0 and correos == []


def test_cp_rf34_3_estilo_inexistente_o_eliminado(client, db, reloj, h_cliente, barbero, corte):
    crear_estilo(db, "Vigente", "Sí se ofrece.")
    eliminado = crear_estilo(db, "Retirado", "Ya no se ofrece.", activo=False)
    for estilo_id in (999, eliminado.id):
        r = agendar(client, h_cliente, barbero, corte, reloj.en(1), "10:00", estilo_id=estilo_id)
        assert r.status_code == 404 and "estilo" in r.json()["detail"].lower(), estilo_id
    assert db.query(models.Cita).count() == 0


def test_cp_rf34_4_sin_catalogo_se_agenda_sin_estilo(client, db, reloj, h_cliente, barbero, corte):
    """PN-14: si el administrador no ha creado estilos (o los eliminó todos), la reserva no se bloquea."""
    crear_estilo(db, "Retirado", "Ya no se ofrece.", activo=False)
    r = agendar(client, h_cliente, barbero, corte, reloj.en(1), "10:00")
    assert r.status_code == 201 and r.json()["estilo_id"] is None and r.json()["estilo"] is None


def test_cp_rf34_5_el_correo_de_confirmacion_incluye_el_estilo(client, db, reloj, h_cliente, barbero, corte, correos):
    estilo = crear_estilo(db, "Crop texturizado", "Textura arriba y flequillo corto.")
    agendar(client, h_cliente, barbero, corte, reloj.en(1), "10:00", estilo_id=estilo.id)
    assert len(correos) == 1
    assert "Estilo" in correos[0]["cuerpo"] and "Crop texturizado" in correos[0]["cuerpo"]
    assert "Crop texturizado" in correos[0]["html"]


def test_cp_rf34_6_la_reprogramacion_conserva_el_estilo(client, db, reloj, h_cliente, barbero, corte):
    estilo = crear_estilo(db)
    cita = agendar(client, h_cliente, barbero, corte, reloj.en(1), "10:00", estilo_id=estilo.id).json()
    r = client.post(f"/api/citas/{cita['id']}/reprogramar", headers=h_cliente,
                    json={"fecha": reloj.en(2).isoformat(), "hora_inicio": "11:00"})
    assert r.status_code == 200 and r.json()["estilo"]["nombre"] == "Fade bajo"


def test_cp_rf34_7_el_estilo_no_se_puede_borrar_de_la_base_si_tiene_citas(client, db, reloj, h_cliente, barbero, corte):
    """RNF-07: la clave foránea citas.estilo_id es RESTRICT; por eso la eliminación del administrador es lógica."""
    estilo = crear_estilo(db)
    agendar(client, h_cliente, barbero, corte, reloj.en(1), "10:00", estilo_id=estilo.id)
    db.expire_all()
    db.delete(db.get(models.Estilo, estilo.id))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
