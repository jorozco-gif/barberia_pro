import os
import json
import datetime
from typing import List, Literal, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from database import engine, Base, get_db
import schemas
import services
from models import Usuario, ROL_ADMIN, ROL_BARBERO, ROL_CLIENTE

# RNF-09: este archivo solo define las rutas, valida la sesión y el rol, y traduce los errores a HTTP.
# Las reglas de negocio y el acceso a la base de datos están en services.py.


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Crear tablas automáticamente al arrancar la aplicación si no existen
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="BarberShop Pro API",
    description="API REST para la gestión integral de citas, barberos y servicios.",
    version="1.1.0",
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


@app.exception_handler(services.ErrorDeNegocio)
async def manejar_error_de_negocio(request: Request, error: services.ErrorDeNegocio):
    cabeceras = {"WWW-Authenticate": "Bearer"} if error.status_code == status.HTTP_401_UNAUTHORIZED else None
    return JSONResponse(
        status_code=error.status_code,
        content={"detail": error.detalle, **error.datos},
        headers=cabeceras,
    )


# ==========================================
# Sesión y permisos por rol (RNF-02, RNF-03)
# ==========================================
_esquema_bearer = HTTPBearer(auto_error=False)


def obtener_token(credenciales: Optional[HTTPAuthorizationCredentials] = Depends(_esquema_bearer)) -> str:
    if credenciales is None or not credenciales.credentials:
        raise services.NoAutorizado("Debes iniciar sesión.")
    return credenciales.credentials


def usuario_actual(token: str = Depends(obtener_token), db: Session = Depends(get_db)) -> Usuario:
    return services.autenticar_sesion(db, token)


def requiere_rol(*roles: str):
    def verificar(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
        if usuario.rol not in roles:
            raise services.Prohibido("No tienes permiso para realizar esta acción.")
        return usuario
    return verificar


solo_cliente = requiere_rol(ROL_CLIENTE)
solo_barbero = requiere_rol(ROL_BARBERO)
solo_admin = requiere_rol(ROL_ADMIN)
cliente_o_admin = requiere_rol(ROL_CLIENTE, ROL_ADMIN)


@app.get("/", tags=["Salud"])
def health_check():
    return {
        "status": "online",
        "app": "BarberShop Pro API",
        "version": "1.1.0",
        "docs_url": "/docs"
    }


# ==========================================
# Cuentas y acceso (RF-01 a RF-04)
# ==========================================
@app.post("/api/auth/registro", response_model=schemas.UsuarioResponse,
          status_code=status.HTTP_201_CREATED, tags=["Cuentas"])
def registrar_cliente(datos: schemas.RegistroCliente, db: Session = Depends(get_db)):
    return services.registrar_cliente(db, datos)


@app.post("/api/auth/login", response_model=schemas.TokenResponse, tags=["Cuentas"])
def iniciar_sesion(datos: schemas.LoginRequest, db: Session = Depends(get_db)):
    token, usuario = services.iniciar_sesion(db, datos)
    return schemas.TokenResponse(access_token=token, usuario=schemas.UsuarioResponse.model_validate(usuario))


@app.post("/api/auth/logout", response_model=schemas.MensajeResponse, tags=["Cuentas"])
def cerrar_sesion(
    token: str = Depends(obtener_token),
    _usuario: Usuario = Depends(usuario_actual),
    db: Session = Depends(get_db),
):
    services.cerrar_sesion(db, token)
    return {"detail": "Sesión cerrada."}


@app.post("/api/auth/recuperar", response_model=schemas.MensajeResponse, tags=["Cuentas"])
def solicitar_recuperacion(datos: schemas.SolicitudRecuperacion, db: Session = Depends(get_db)):
    services.solicitar_recuperacion(db, datos.email)
    return {"detail": "Si el correo está registrado, te enviamos un enlace para recuperar tu contraseña."}


@app.get("/api/auth/restablecer/validar", response_model=schemas.MensajeResponse, tags=["Cuentas"])
def validar_enlace_de_recuperacion(token: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    services.validar_token_recuperacion(db, token)
    return {"detail": "El enlace es válido."}


@app.post("/api/auth/restablecer", response_model=schemas.MensajeResponse, tags=["Cuentas"])
def restablecer_password(datos: schemas.RestablecerPassword, db: Session = Depends(get_db)):
    services.restablecer_password(db, datos.token, datos.nueva_password)
    return {"detail": "Contraseña actualizada. Ya puedes iniciar sesión."}


# ==========================================
# Catálogo: barberos y servicios visibles (RF-13, RF-14)
# ==========================================
@app.get("/api/barberos", response_model=List[schemas.BarberoPublico], tags=["Catálogo"])
def listar_barberos(_usuario: Usuario = Depends(cliente_o_admin), db: Session = Depends(get_db)):
    return services.listar_barberos(db)


@app.get("/api/servicios", response_model=List[schemas.ServicioResponse], tags=["Catálogo"])
def listar_servicios(_usuario: Usuario = Depends(cliente_o_admin), db: Session = Depends(get_db)):
    return services.listar_servicios(db)


# ==========================================
# Administrador: barberos, servicios y citas (RF-05 a RF-10, RF-28)
# ==========================================
@app.get("/api/admin/barberos", response_model=List[schemas.BarberoResponse], tags=["Administrador"])
def admin_listar_barberos(_admin: Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    return services.listar_barberos(db, solo_activos=False)


@app.post("/api/admin/barberos", response_model=schemas.BarberoResponse,
          status_code=status.HTTP_201_CREATED, tags=["Administrador"])
def admin_crear_barbero(
    datos: schemas.BarberoCreate, _admin: Usuario = Depends(solo_admin), db: Session = Depends(get_db)
):
    return services.crear_barbero(db, datos)


@app.patch("/api/admin/barberos/{barbero_id}", response_model=schemas.BarberoResponse, tags=["Administrador"])
def admin_actualizar_barbero(
    barbero_id: int, datos: schemas.BarberoUpdate,
    _admin: Usuario = Depends(solo_admin), db: Session = Depends(get_db),
):
    return services.actualizar_barbero(db, barbero_id, datos)


@app.delete("/api/admin/barberos/{barbero_id}", response_model=schemas.BarberoResponse, tags=["Administrador"])
def admin_eliminar_barbero(
    barbero_id: int, _admin: Usuario = Depends(solo_admin), db: Session = Depends(get_db)
):
    return services.eliminar_barbero(db, barbero_id)


@app.post("/api/admin/servicios", response_model=schemas.ServicioResponse,
          status_code=status.HTTP_201_CREATED, tags=["Administrador"])
def admin_crear_servicio(
    datos: schemas.ServicioCreate, _admin: Usuario = Depends(solo_admin), db: Session = Depends(get_db)
):
    return services.crear_servicio(db, datos)


@app.patch("/api/admin/servicios/{servicio_id}", response_model=schemas.ServicioResponse, tags=["Administrador"])
def admin_actualizar_servicio(
    servicio_id: int, datos: schemas.ServicioUpdate,
    _admin: Usuario = Depends(solo_admin), db: Session = Depends(get_db),
):
    return services.actualizar_servicio(db, servicio_id, datos)


@app.delete("/api/admin/servicios/{servicio_id}", response_model=schemas.ServicioResponse, tags=["Administrador"])
def admin_eliminar_servicio(
    servicio_id: int, _admin: Usuario = Depends(solo_admin), db: Session = Depends(get_db)
):
    return services.eliminar_servicio(db, servicio_id)


@app.get("/api/admin/citas", response_model=List[schemas.CitaResponse], tags=["Administrador"])
def admin_listar_citas(
    barbero_id: Optional[int] = None,
    fecha: Optional[datetime.date] = None,
    estado: Optional[str] = None,
    _admin: Usuario = Depends(solo_admin),
    db: Session = Depends(get_db),
):
    return services.listar_citas(db, barbero_id, fecha, estado)


# ==========================================
# Barbero: disponibilidad, bloqueos, agenda y estados (RF-11, RF-12, RF-26, RF-27)
# ==========================================
@app.get("/api/barbero/disponibilidad", response_model=List[schemas.DisponibilidadResponse], tags=["Barbero"])
def listar_disponibilidad(barbero: Usuario = Depends(solo_barbero), db: Session = Depends(get_db)):
    return services.listar_disponibilidad(db, barbero)


@app.post("/api/barbero/disponibilidad", response_model=schemas.DisponibilidadResponse,
          status_code=status.HTTP_201_CREATED, tags=["Barbero"])
def agregar_disponibilidad(
    datos: schemas.DisponibilidadCreate, barbero: Usuario = Depends(solo_barbero), db: Session = Depends(get_db)
):
    return services.agregar_disponibilidad(db, barbero, datos)


@app.delete("/api/barbero/disponibilidad/{disponibilidad_id}", response_model=schemas.MensajeResponse, tags=["Barbero"])
def eliminar_disponibilidad(
    disponibilidad_id: int, barbero: Usuario = Depends(solo_barbero), db: Session = Depends(get_db)
):
    services.eliminar_disponibilidad(db, barbero, disponibilidad_id)
    return {"detail": "Horario eliminado."}


@app.get("/api/barbero/bloqueos", response_model=List[schemas.BloqueoResponse], tags=["Barbero"])
def listar_bloqueos(barbero: Usuario = Depends(solo_barbero), db: Session = Depends(get_db)):
    return services.listar_bloqueos(db, barbero)


@app.post("/api/barbero/bloqueos", response_model=schemas.BloqueoResponse,
          status_code=status.HTTP_201_CREATED, tags=["Barbero"])
def agregar_bloqueo(
    datos: schemas.BloqueoCreate, barbero: Usuario = Depends(solo_barbero), db: Session = Depends(get_db)
):
    return services.agregar_bloqueo(db, barbero, datos)


@app.delete("/api/barbero/bloqueos/{bloqueo_id}", response_model=schemas.MensajeResponse, tags=["Barbero"])
def eliminar_bloqueo(bloqueo_id: int, barbero: Usuario = Depends(solo_barbero), db: Session = Depends(get_db)):
    services.eliminar_bloqueo(db, barbero, bloqueo_id)
    return {"detail": "Bloqueo eliminado."}


@app.get("/api/barbero/agenda", response_model=List[schemas.CitaResponse], tags=["Barbero"])
def agenda_del_barbero(
    fecha: Optional[datetime.date] = Query(None, description="Por defecto, hoy"),
    vista: Literal["dia", "semana"] = "dia",
    barbero: Usuario = Depends(solo_barbero),
    db: Session = Depends(get_db),
):
    return services.agenda_barbero(db, barbero, fecha, vista)


@app.patch("/api/citas/{cita_id}/estado", response_model=schemas.CitaResponse, tags=["Barbero"])
def actualizar_estado_cita(
    cita_id: int, datos: schemas.CitaEstadoUpdate,
    barbero: Usuario = Depends(solo_barbero), db: Session = Depends(get_db),
):
    return services.actualizar_estado_cita(db, barbero, cita_id, datos.estado)


# ==========================================
# Cliente: agendamiento (RF-15 a RF-21)
# ==========================================
@app.get("/api/citas/resumen", response_model=schemas.ResumenCitaResponse, tags=["Citas"])
def resumen_de_servicios(
    servicios_ids: List[int] = Query(..., min_length=1),
    _cliente: Usuario = Depends(solo_cliente),
    db: Session = Depends(get_db),
):
    return services.calcular_resumen(db, servicios_ids)


@app.get("/api/disponibilidad", response_model=List[schemas.SlotHorario], tags=["Citas"])
def consultar_disponibilidad(
    barbero_id: int = Query(..., gt=0),
    fecha: datetime.date = Query(...),
    franja: schemas.Franja = Query(...),
    servicios_ids: List[int] = Query(..., min_length=1),
    _cliente: Usuario = Depends(solo_cliente),
    db: Session = Depends(get_db),
):
    return services.consultar_disponibilidad(db, barbero_id, fecha, franja, servicios_ids)


@app.post("/api/citas", response_model=schemas.CitaResponse, status_code=status.HTTP_201_CREATED, tags=["Citas"])
def agendar_cita(datos: schemas.CitaCreate, cliente: Usuario = Depends(solo_cliente), db: Session = Depends(get_db)):
    return services.agendar_cita(db, cliente, datos)


# ==========================================
# Cliente: gestión de sus citas (RF-22 a RF-25)
# ==========================================
@app.get("/api/citas/mias", response_model=List[schemas.CitaResponse], tags=["Citas"])
def mis_citas(cliente: Usuario = Depends(solo_cliente), db: Session = Depends(get_db)):
    return services.listar_mis_citas(db, cliente)


@app.get("/api/citas/{cita_id}", response_model=schemas.CitaResponse, tags=["Citas"])
def obtener_cita(cita_id: int, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    return services.obtener_cita_visible(db, usuario, cita_id)


@app.post("/api/citas/{cita_id}/cancelar", response_model=schemas.CitaResponse, tags=["Citas"])
def cancelar_cita(cita_id: int, cliente: Usuario = Depends(solo_cliente), db: Session = Depends(get_db)):
    return services.cancelar_cita(db, cliente, cita_id)


@app.get("/api/citas/{cita_id}/disponibilidad", response_model=List[schemas.SlotHorario], tags=["Citas"])
def disponibilidad_para_reprogramar(
    cita_id: int,
    fecha: datetime.date = Query(...),
    franja: schemas.Franja = Query(...),
    cliente: Usuario = Depends(solo_cliente),
    db: Session = Depends(get_db),
):
    return services.horarios_para_reprogramar(db, cliente, cita_id, fecha, franja)


@app.post("/api/citas/{cita_id}/reprogramar", response_model=schemas.CitaResponse, tags=["Citas"])
def reprogramar_cita(
    cita_id: int, datos: schemas.CitaReprogramar,
    cliente: Usuario = Depends(solo_cliente), db: Session = Depends(get_db),
):
    return services.reprogramar_cita(db, cliente, cita_id, datos)
