import os
import json
import datetime
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import engine, Base, get_db
import models
import schemas
import services


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Crear tablas automáticamente al arrancar la aplicación si no existen
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="BarberShop Pro API",
    description="API REST para la gestión integral de citas, barberos y servicios.",
    version="1.0.0",
    lifespan=lifespan
)

# Configuración de CORS para permitir peticiones desde React/Vite
cors_origins_env = os.getenv("CORS_ORIGINS", '["*"]')
try:
    origins = json.loads(cors_origins_env)
except Exception:
    origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Salud"])
def health_check():
    return {
        "status": "online",
        "app": "BarberShop Pro API",
        "version": "1.0.0",
        "docs_url": "/docs"
    }


# ==========================================
# Endpoints de Barberos
# ==========================================
@app.get("/api/barberos", response_model=List[schemas.BarberoResponse], tags=["Barberos"])
def listar_barberos(solo_activos: bool = True, db: Session = Depends(get_db)):
    query = db.query(models.Barbero)
    if solo_activos:
        query = query.filter(models.Barbero.activo == True)
    return query.all()


@app.post("/api/barberos", response_model=schemas.BarberoResponse, status_code=status.HTTP_201_CREATED, tags=["Barberos"])
def crear_barbero(barbero_in: schemas.BarberoCreate, db: Session = Depends(get_db)):
    existente = db.query(models.Barbero).filter(models.Barbero.email == barbero_in.email).first()
    if existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un barbero registrado con el correo '{barbero_in.email}'."
        )
    
    nuevo_barbero = models.Barbero(**barbero_in.model_dump())
    db.add(nuevo_barbero)
    db.commit()
    db.refresh(nuevo_barbero)
    return nuevo_barbero


# ==========================================
# Endpoints de Servicios
# ==========================================
@app.get("/api/servicios", response_model=List[schemas.ServicioResponse], tags=["Servicios"])
def listar_servicios(solo_activos: bool = True, db: Session = Depends(get_db)):
    query = db.query(models.Servicio)
    if solo_activos:
        query = query.filter(models.Servicio.activo == True)
    return query.all()


@app.post("/api/servicios", response_model=schemas.ServicioResponse, status_code=status.HTTP_201_CREATED, tags=["Servicios"])
def crear_servicio(servicio_in: schemas.ServicioCreate, db: Session = Depends(get_db)):
    nuevo_servicio = models.Servicio(**servicio_in.model_dump())
    db.add(nuevo_servicio)
    db.commit()
    db.refresh(nuevo_servicio)
    return nuevo_servicio


# ==========================================
# Endpoints de Citas y Agendamiento (Lógica Crítica RF-03 y RF-04)
# ==========================================
@app.post("/api/citas", response_model=schemas.CitaResponse, status_code=status.HTTP_201_CREATED, tags=["Citas"])
def agendar_cita(cita_in: schemas.CitaCreate, db: Session = Depends(get_db)):
    # 1. Validar existencia del barbero
    barbero = db.query(models.Barbero).filter(models.Barbero.id == cita_in.barbero_id, models.Barbero.activo == True).first()
    if not barbero:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El barbero con ID {cita_in.barbero_id} no existe o no está activo."
        )

    # 2. Validar existencia del servicio
    servicio = db.query(models.Servicio).filter(models.Servicio.id == cita_in.servicio_id, models.Servicio.activo == True).first()
    if not servicio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El servicio con ID {cita_in.servicio_id} no existe o no está activo."
        )

    # 3. Calcular hora de fin
    hora_fin = services.calcular_hora_fin(cita_in.hora_inicio, servicio.duracion_minutos)

    # 4. Control de calidad estricto: Verificar choques de horario (RF-04)
    disponible = services.verificar_disponibilidad_barbero(
        db=db,
        barbero_id=barbero.id,
        fecha=cita_in.fecha,
        hora_inicio=cita_in.hora_inicio,
        hora_fin=hora_fin
    )

    if not disponible:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflicto de horario: El barbero ya tiene una cita reservada que se cruza con este horario."
        )

    # 5. Generar código de reserva y persistir
    codigo = services.generar_codigo_reserva()

    nueva_cita = models.Cita(
        codigo_reserva=codigo,
        barbero_id=cita_in.barbero_id,
        servicio_id=cita_in.servicio_id,
        cliente_nombre=cita_in.cliente_nombre,
        cliente_telefono=cita_in.cliente_telefono,
        cliente_email=cita_in.cliente_email,
        fecha=cita_in.fecha,
        hora_inicio=cita_in.hora_inicio,
        hora_fin=hora_fin,
        estado="Pendiente",
        notas=cita_in.notas
    )

    db.add(nueva_cita)
    db.commit()
    db.refresh(nueva_cita)
    return nueva_cita


@app.get("/api/citas", response_model=List[schemas.CitaResponse], tags=["Citas"])
def listar_citas(
    fecha: Optional[datetime.date] = None,
    barbero_id: Optional[int] = None,
    estado: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(models.Cita)
    if fecha:
        query = query.filter(models.Cita.fecha == fecha)
    if barbero_id:
        query = query.filter(models.Cita.barbero_id == barbero_id)
    if estado:
        query = query.filter(models.Cita.estado == estado)
    
    return query.order_by(models.Cita.hora_inicio.asc()).all()


@app.get("/api/citas/codigo/{codigo_reserva}", response_model=schemas.CitaResponse, tags=["Citas"])
def buscar_cita_por_codigo(codigo_reserva: str, db: Session = Depends(get_db)):
    cita = db.query(models.Cita).filter(models.Cita.codigo_reserva == codigo_reserva.strip().upper()).first()
    if not cita:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró ninguna cita con el código '{codigo_reserva}'."
        )
    return cita


@app.patch("/api/citas/{cita_id}/estado", response_model=schemas.CitaResponse, tags=["Citas"])
def actualizar_estado_cita(cita_id: int, estado_in: schemas.CitaEstadoUpdate, db: Session = Depends(get_db)):
    cita = db.query(models.Cita).filter(models.Cita.id == cita_id).first()
    if not cita:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cita con ID {cita_id} no encontrada."
        )

    # Regla de calidad: Un estado finalizado no puede cambiarse
    if cita.estado == "Finalizada":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Una cita marcada como 'Finalizada' no puede modificar su estado."
        )

    cita.estado = estado_in.estado
    db.commit()
    db.refresh(cita)
    return cita


# ==========================================
# Consulta de Disponibilidad de Turnos
# ==========================================
@app.get("/api/disponibilidad", response_model=List[schemas.SlotHorario], tags=["Disponibilidad"])
def consultar_disponibilidad(
    barbero_id: int = Query(..., description="ID del barbero a consultar"),
    fecha: datetime.date = Query(..., description="Fecha de interés"),
    servicio_id: int = Query(..., description="Servicio deseado para calcular duración"),
    db: Session = Depends(get_db)
):
    servicio = db.query(models.Servicio).filter(models.Servicio.id == servicio_id, models.Servicio.activo == True).first()
    if not servicio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Servicio no encontrado.")

    slots = services.generar_slots_del_dia(
        db=db,
        barbero_id=barbero_id,
        fecha=fecha,
        duracion_minutos=servicio.duracion_minutos
    )
    return slots
