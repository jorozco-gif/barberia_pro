# 💈 BarberShop Pro — Sistema de Gestión y Agendamiento de Citas

Proyecto final para el curso de **Ingeniería de Software II** (Código 17934) — **Cotecnova**  
Docente: **Felipe Gutiérrez Isaza**  
Periodo: **2026-2**

---

## 👥 Equipo y Asignación de Roles

| Integrante | Rol en el Proyecto | Responsabilidad Principal |
|---|---|---|
| **Elizabeth Ramirez** | **Líder Técnico** | Coordina el alcance, la arquitectura, el modelo de datos y la integración continua del repositorio. |
| **Sebastian Orozco** | **Responsable de Pruebas** | Diseña los casos de prueba formales, técnicas de partición/valores límite y coordina la automatización con `pytest`. |
| **Juan David Osorio** | **Responsable de Calidad** | Revisa estándares de código, registra defectos/riesgos, propone acciones de mantenimiento y métricas de calidad. |
| **Juan David Monroy** | **Responsable de Documentación** | Mantiene la especificación de requisitos, criterios de aceptación, actas, manuales y evidencias de entregas. |

---

## 📌 Gestión del Proyecto en Trello

El seguimiento ágil del proyecto, la asignación de tarjetas y la trazabilidad de tareas hacia los commits del repositorio se gestionan a través de:
* **Enlace al Tablero de Trello:** [Tablero Oficial - BarberShop Pro](https://trello.com/b/ENLACE_DEL_TABLERO_AQUI) *(Pendiente por actualizar enlace una vez invitado el docente)*

---

## 🏛️ Estructura del Repositorio

El repositorio respeta estrictamente los lineamientos solicitados para el curso:

```text
gestor-barberia/
├── README.md                 # Integrantes, roles, guía de ejecución y enlace a Trello
├── .gitignore                # Exclusión de archivos sensibles, temporales y dependencias
├── docs/                     # Documentación de ingeniería de software
│   ├── especificacion.md     # Requisitos funcionales y criterios de aceptación (Gherkin)
│   ├── plan-de-pruebas.md    # Casos de prueba diseñados (partición de equivalencia, límites)
│   └── informe-calidad.md    # Registro de defectos, métricas y acciones de mantenimiento
├── src/                      # Código fuente de la aplicación
│   ├── backend/              # API REST con FastAPI, SQLAlchemy 2.0 y Pydantic v2
│   └── frontend/             # Interfaz de usuario con React, Vite y Tailwind CSS
└── tests/                    # Pruebas automatizadas (unitarias e integración con pytest)
```

---

## 🚀 Stack Tecnológico

| Capa | Tecnologías Seleccionadas |
|---|---|
| **Backend** | Python 3.11+ / 3.13, FastAPI, Pydantic v2, Uvicorn, SQLAlchemy 2.0 |
| **Frontend** | React 18, Vite, Tailwind CSS, Lucide Icons |
| **Base de Datos** | MySQL 8 / MariaDB (Producción/Dev) y SQLite (Entorno de pruebas automatizadas) |
| **Testing / Calidad**| `pytest`, `pytest-asyncio`, `httpx` (TestClient de FastAPI) |

---

## ⚡ Guía de Instalación y Ejecución Local

### Prerrequisitos
* Python 3.11 o superior instalado (`python --version`)
* Node.js v18 o superior instalado (`node --version`)
* Git instalado (`git --version`)

---

### 1. Configuración del Backend (FastAPI)

1. Abrir una terminal y navegar al directorio del backend:
   ```bash
   cd src/backend
   ```

2. Crear y activar el entorno virtual de Python:
   * **Windows (PowerShell):**
     ```powershell
     python -m venv venv
     .\venv\Scripts\Activate.ps1
     ```
   * **Linux / macOS:**
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. Instalar las dependencias necesarias:
   ```bash
   pip install -r requirements.txt
   ```

4. Configurar las variables de entorno:
   * Copiar el archivo de plantilla `.env.example` a `.env`:
     ```bash
     cp .env.example .env
     ```
   *(Ajustar las credenciales en caso de usar un servidor MySQL local, o usar la cadena de SQLite para pruebas rápidas).*

5. Iniciar el servidor de desarrollo:
   ```bash
   uvicorn main:app --host 127.0.0.1 --port 8000 --reload
   ```
   * **API Base:** `http://127.0.0.1:8000`
   * **Documentación interactiva Swagger / OpenAPI:** `http://127.0.0.1:8000/docs`

6. **Actualizar una base de datos de la v1.1 a la v1.2** (solo si ya tenías datos):
   * Al arrancar, la API (y también `python seed.py`) aplica automáticamente los cambios pendientes del esquema sin borrar datos. Para hacerlo a mano:
     ```bash
     python migrar.py
     ```
   * Si prefieres SQL, aplica **una sola vez** el script de tu motor, después de sacar una copia de seguridad:
     ```bash
     mysql -u <usuario> -p <base_de_datos> < migraciones/v1_2_mysql.sql   # MySQL / MariaDB
     sqlite3 barberia.db < migraciones/v1_2_sqlite.sql                     # SQLite
     ```
   * Cambios: tabla `estilos`, columna `servicios.descripcion` y columna `citas.estilo_id` (clave foránea hacia `estilos`). La columna `citas.notas` se conserva para el historial.

---

### 2. Ejecución de Pruebas Automatizadas

Para validar los casos de prueba unitarios y de lógica de negocio (como detección de choques de horario y cálculo de disponibilidad):

```bash
# Estando en la raíz del proyecto o en src/backend con el entorno virtual activo:
pytest tests/ -v
```

Las pruebas unitarias del frontend (cliente de la API y estado del asistente de reserva) se ejecutan con:

```bash
cd src/frontend && npm test
```

---

### 3. Configuración del Frontend (React + Vite)

1. En una nueva terminal, navegar al directorio del frontend:
   ```bash
   cd src/frontend
   ```

2. Instalar las dependencias de Node:
   ```bash
   npm install
   ```

3. Iniciar el servidor local de desarrollo:
   ```bash
   npm run dev
   ```
   * **Aplicación Web:** `http://localhost:5173`

---

## 🆕 Novedades de la versión 1.2

* **Nuevo orden del agendamiento:** Barbero → Servicios → Fecha y Hora → Confirmación. La reserva en curso se guarda en un contexto global (`BookingContext`), incluido el estilo elegido.
* **Servicios con descripción:** campo opcional que el administrador llena al crear o editar; el cliente la abre en una ventana flotante.
* **Catálogo de estilos:** nuevo módulo del administrador (listar, crear, editar y eliminar) con nombre, descripción y foto opcional. El cliente elige un estilo junto a los servicios y puede ver su descripción en una ventana flotante.
* **Turnos del día completo:** al elegir la fecha se muestran todos los turnos libres, sin botones de Mañana, Tarde o Noche.
* **Confirmación sin notas:** la personalización la da el estilo elegido.
* **Edición completa de barberos:** el administrador modifica nombre, correo, contraseña y foto.
* **Nuevos endpoints:** `GET /api/estilos`, `POST /api/admin/estilos`, `PATCH /api/admin/estilos/{id}`, `DELETE /api/admin/estilos/{id}`. `POST /api/citas` recibe `estilo_id`; `PATCH /api/admin/barberos/{id}` acepta `email` y `password`; la `franja` de las consultas de disponibilidad pasa a ser opcional.

Detalle en [`docs/especificacion.md`](docs/especificacion.md) (RF-06, RF-08, RF-09, RF-13 a RF-19, RF-24, RF-33, RF-34 y PN-14) y en [`docs/plan-de-pruebas.md`](docs/plan-de-pruebas.md).

---

## 🏷️ Historial de Entregas y Tags

* **Seguimiento 1:** `git tag entrega-s1`
* **Seguimiento 2:** `git tag entrega-s2`
* **Entrega Final:** `git tag entrega-final`
