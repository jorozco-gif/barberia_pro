import datetime
from fastapi import status


def test_cp01_crear_servicio_valido(client):
    """CP-01: Registro exitoso de un servicio con valores válidos (HTTP 201)."""
    payload = {
        "nombre": "Afeitado Clásico",
        "descripcion": "Afeitado con toalla caliente",
        "duracion_minutos": 30,
        "precio": 12.50,
        "activo": True
    }
    response = client.post("/api/servicios", json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["id"] is not None
    assert data["nombre"] == "Afeitado Clásico"
    assert float(data["precio"]) == 12.50


def test_cp02_crear_servicio_precio_negativo_falla(client):
    """CP-02: Rechazo por validación Pydantic de precio negativo (HTTP 422)."""
    payload = {
        "nombre": "Servicio Inválido",
        "duracion_minutos": 30,
        "precio": -10.00
    }
    response = client.post("/api/servicios", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_cp03_crear_servicio_duracion_cero_falla(client):
    """CP-03: Rechazo por validación Pydantic de duración igual o menor a cero (HTTP 422)."""
    payload = {
        "nombre": "Servicio Sin Tiempo",
        "duracion_minutos": 0,
        "precio": 15.00
    }
    response = client.post("/api/servicios", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_cp04_agendar_cita_horario_libre(client, setup_datos_base):
    """CP-04: Agendamiento de cita en horario libre con cálculo automático de hora_fin (HTTP 201)."""
    barbero = setup_datos_base["barbero1"]
    servicio = setup_datos_base["servicio"]  # duración: 30 min

    payload = {
        "barbero_id": barbero.id,
        "servicio_id": servicio.id,
        "cliente_nombre": "Juan Pérez",
        "cliente_telefono": "3001234567",
        "cliente_email": "juan@example.com",
        "fecha": "2026-11-10",
        "hora_inicio": "10:00"
    }

    response = client.post("/api/citas", json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["codigo_reserva"].startswith("BSP-")
    assert data["hora_inicio"] == "10:00:00"
    assert data["hora_fin"] == "10:30:00"  # 10:00 + 30 minutos
    assert data["estado"] == "Pendiente"


def test_cp05_agendar_citas_consecutivas_permitidas(client, setup_datos_base):
    """
    CP-05: Valor límite de frontera.
    Cita 1: 10:00 a 10:30.
    Cita 2: 10:30 a 11:00.
    Deben permitirse sin colisión ya que no se solapan (HTTP 201).
    """
    barbero = setup_datos_base["barbero1"]
    servicio = setup_datos_base["servicio"]

    # Cita 1
    c1 = client.post("/api/citas", json={
        "barbero_id": barbero.id,
        "servicio_id": servicio.id,
        "cliente_nombre": "Cliente Uno",
        "cliente_telefono": "3001111111",
        "fecha": "2026-11-10",
        "hora_inicio": "10:00"
    })
    assert c1.status_code == status.HTTP_201_CREATED

    # Cita 2 (arranca exactamente cuando termina la anterior)
    c2 = client.post("/api/citas", json={
        "barbero_id": barbero.id,
        "servicio_id": servicio.id,
        "cliente_nombre": "Cliente Dos",
        "cliente_telefono": "3002222222",
        "fecha": "2026-11-10",
        "hora_inicio": "10:30"
    })
    assert c2.status_code == status.HTTP_201_CREATED
    assert c2.json()["hora_inicio"] == "10:30:00"
    assert c2.json()["hora_fin"] == "11:00:00"


def test_cp06_agendar_cita_solapada_un_minuto_falla(client, setup_datos_base):
    """
    CP-06: Valor límite frontera de conflicto.
    Cita 1: 10:00 a 10:30.
    Cita 2: 10:29 a 10:59 (solapa por 1 minuto).
    Debe responder HTTP 409 Conflict.
    """
    barbero = setup_datos_base["barbero1"]
    servicio = setup_datos_base["servicio"]

    # Cita 1
    client.post("/api/citas", json={
        "barbero_id": barbero.id,
        "servicio_id": servicio.id,
        "cliente_nombre": "Cliente Base",
        "cliente_telefono": "3003333333",
        "fecha": "2026-11-10",
        "hora_inicio": "10:00"
    })

    # Cita 2 en conflicto por 1 minuto
    c2 = client.post("/api/citas", json={
        "barbero_id": barbero.id,
        "servicio_id": servicio.id,
        "cliente_nombre": "Cliente Solapado",
        "cliente_telefono": "3004444444",
        "fecha": "2026-11-10",
        "hora_inicio": "10:29"
    })
    assert c2.status_code == status.HTTP_409_CONFLICT
    assert "Conflicto de horario" in c2.json()["detail"]


def test_cp07_agendar_cita_totalmente_dentro_falla(client, setup_datos_base):
    """CP-07: Intento de reserva completamente dentro de una cita activa (HTTP 409 Conflict)."""
    barbero = setup_datos_base["barbero1"]
    servicio = setup_datos_base["servicio"]

    # Cita 1: 10:00 a 10:30
    client.post("/api/citas", json={
        "barbero_id": barbero.id,
        "servicio_id": servicio.id,
        "cliente_nombre": "Cliente A",
        "cliente_telefono": "3005555555",
        "fecha": "2026-11-10",
        "hora_inicio": "10:00"
    })

    # Cita 2: 10:10 a 10:40 (choca en su totalidad inicial)
    c2 = client.post("/api/citas", json={
        "barbero_id": barbero.id,
        "servicio_id": servicio.id,
        "cliente_nombre": "Cliente B",
        "cliente_telefono": "3006666666",
        "fecha": "2026-11-10",
        "hora_inicio": "10:10"
    })
    assert c2.status_code == status.HTTP_409_CONFLICT


def test_cp08_mismo_horario_diferente_barbero_permitido(client, setup_datos_base):
    """CP-08: Dos barberos distintos pueden tener citas al mismo tiempo sin interferencia (HTTP 201)."""
    barbero1 = setup_datos_base["barbero1"]
    barbero2 = setup_datos_base["barbero2"]
    servicio = setup_datos_base["servicio"]

    # Barbero 1 a las 11:00
    c1 = client.post("/api/citas", json={
        "barbero_id": barbero1.id,
        "servicio_id": servicio.id,
        "cliente_nombre": "Cliente X",
        "cliente_telefono": "3007777777",
        "fecha": "2026-11-10",
        "hora_inicio": "11:00"
    })
    assert c1.status_code == status.HTTP_201_CREATED

    # Barbero 2 a las 11:00 (mismo horario, otro profesional)
    c2 = client.post("/api/citas", json={
        "barbero_id": barbero2.id,
        "servicio_id": servicio.id,
        "cliente_nombre": "Cliente Y",
        "cliente_telefono": "3008888888",
        "fecha": "2026-11-10",
        "hora_inicio": "11:00"
    })
    assert c2.status_code == status.HTTP_201_CREATED


def test_cp09_transicion_estado_finalizada_bloqueada(client, setup_datos_base):
    """CP-09: Una cita en estado 'Finalizada' no puede ser reabierta ni modificada (HTTP 400)."""
    barbero = setup_datos_base["barbero1"]
    servicio = setup_datos_base["servicio"]

    cita = client.post("/api/citas", json={
        "barbero_id": barbero.id,
        "servicio_id": servicio.id,
        "cliente_nombre": "Cliente Finalizado",
        "cliente_telefono": "3009999999",
        "fecha": "2026-11-10",
        "hora_inicio": "14:00"
    }).json()

    cita_id = cita["id"]

    # Marcar como 'Finalizada'
    p1 = client.patch(f"/api/citas/{cita_id}/estado", json={"estado": "Finalizada"})
    assert p1.status_code == status.HTTP_200_OK
    assert p1.json()["estado"] == "Finalizada"

    # Intentar revertir a 'Pendiente' -> Debe fallar
    p2 = client.patch(f"/api/citas/{cita_id}/estado", json={"estado": "Pendiente"})
    assert p2.status_code == status.HTTP_400_BAD_REQUEST
    assert "no puede modificar su estado" in p2.json()["detail"]
