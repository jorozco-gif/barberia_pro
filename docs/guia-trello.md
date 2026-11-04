# 📋 Guía Paso a Paso para Configurar el Tablero de Trello

Esta guía detalla la configuración exacta del tablero de Trello requerida por el docente Felipe Gutiérrez Isaza en la rúbrica del proyecto.

---

## 1. Crear el Tablero e Invitar al Docente
1. Entrar a [Trello](https://trello.com/) y crear un tablero con el nombre:  
   `BarberShop Pro - Cotecnova 2026-2`
2. En la opción **Compartir / Miembros**, invitar al correo del profesor Felipe.
3. Asegurarse de que el enlace sea accesible y copiar la URL en el `README.md`.

---

## 2. Configurar las Listas Obligatorias
El docente exige como mínimo estas 4 listas (de izquierda a derecha):
1. **Por hacer** (Backlog de tareas pendientes)
2. **En curso** (Tareas en desarrollo activo)
3. **En revisión** (Pull Requests abiertos o código pendiente de pruebas/calidad)
4. **Hecho** (Tareas completadas, mergeadas y con pruebas pasando)

---

## 3. Configurar las 4 Etiquetas (Labels) por Etapa
En el menú lateral de Trello $\rightarrow$ Etiquetas, crear o renombrar exactamente:
* 🟢 **Planeación** (Verde)
* 🟡 **Seguimiento 1** (Amarillo)
* 🟠 **Seguimiento 2** (Naranja)
* 🔴 **Entrega final** (Rojo)

---

## 4. Tarjetas Iniciales Sugeridas por Rol (Para Seguimiento 1)

Cada tarjeta debe tener:
* **Miembro asignado** (uno solo o principal responsable).
* **Fecha de vencimiento:** Lunes 2 de noviembre (11:59 p. m.).
* **Etiqueta:** `Seguimiento 1` (o `Planeación`).
* **Descripción breve** del resultado esperado.
* **Trazabilidad (Vital):** Cuando la terminen, agregar en la descripción o comentario el enlace al **commit de GitHub** o al archivo que la resolvió.

### 👤 Elizabeth Ramirez (Líder Técnico)
* **Tarjeta 1:** *Inicialización de arquitectura del repositorio y estructura de carpetas*
  * Etiqueta: `Planeación`
  * Descripción: Configurar la estructura `docs/`, `src/`, `tests/` y `.gitignore`.
* **Tarjeta 2:** *Diseño del modelo de datos de la base de datos (SQLAlchemy)*
  * Etiqueta: `Seguimiento 1`
  * Descripción: Crear modelos de `Barbero`, `Servicio` y `Cita`.
* **Tarjeta 3:** *Lógica de control de solapamiento de horarios (RF-04)*
  * Etiqueta: `Seguimiento 1`
  * Descripción: Algoritmo que valida que un barbero no tenga citas que se crucen el mismo día.

### 👤 Juan David Monroy (Documentación)
* **Tarjeta 1:** *Redacción de `README.md` institucional con roles y comandos*
  * Etiqueta: `Planeación`
  * Descripción: Incluir integrantes, roles, comandos de inicio y enlace a Trello.
* **Tarjeta 2:** *Elaboración de `docs/especificacion.md` con historias de usuario y Gherkin*
  * Etiqueta: `Seguimiento 1`
  * Descripción: Documentar RF-01 al RF-06 con criterios de aceptación Dado/Cuando/Entonces.

### 👤 Juan David Osorio (Calidad)
* **Tarjeta 1:** *Auditoría de buenas prácticas y seguridad del repositorio*
  * Etiqueta: `Planeación`
  * Descripción: Validar que no se suban archivos `.env`, contraseñas ni credenciales reales.
* **Tarjeta 2:** *Definición de esquemas de validación de entrada con Pydantic v2*
  * Etiqueta: `Seguimiento 1`
  * Descripción: Validar que precios sean $\ge 0$, duraciones $> 0$ y formatos de fecha/hora válidos.
* **Tarjeta 3:** *Creación de plantilla de informe de calidad (`docs/informe-calidad.md`)*
  * Etiqueta: `Seguimiento 1`
  * Descripción: Estructurar formato para registro de defectos encontrados y métricas de código.

### 👤 Sebastian Orozco (Pruebas)
* **Tarjeta 1:** *Diseño de casos de prueba con técnicas formales (`docs/plan-de-pruebas.md`)*
  * Etiqueta: `Seguimiento 1`
  * Descripción: Diseñar casos de partición de equivalencia y valores límite para solapamiento de turnos.
* **Tarjeta 2:** *Configuración del entorno de pruebas con `pytest` y SQLite en memoria*
  * Etiqueta: `Seguimiento 1`
  * Descripción: Crear fixtures de prueba y base de datos aislada para testing.
* **Tarjeta 3:** *Automatización de pruebas unitarias de solapamiento de horarios*
  * Etiqueta: `Seguimiento 1`
  * Descripción: Escribir tests que verifiquen citas consecutivas, solapadas y en horarios distintos.
