# 🧪 Plan de Pruebas de Software

**Proyecto:** BarberShop Pro — Sistema de Gestión y Agendamiento de Barbería
**Materia:** Ingeniería de Software II (Código 17934) — Cotecnova
**Versión:** 1.1 (propuesta de modificación sobre la v1.0 del Seguimiento 1)
**Basado en:** `especificacion-requisitos.md` v1.1
**Responsable de Pruebas:** Sebastian Orozco
**Responsable de Calidad:** Juan David Osorio
**Líder Técnico:** Elizabeth Ramirez
**Documentación:** Juan David Monroy

---

## 1. Propósito y Alcance de las Pruebas

Este documento establece la estrategia y el diseño formal de casos de prueba para verificar los requisitos funcionales (RF-01 a RF-30) y no funcionales (RNF-01 a RNF-10) de la especificación v1.1. Cada requisito tiene como mínimo dos casos: uno que el sistema debe permitir y otro que debe rechazar. Los módulos cubiertos son:

1. Cuentas y acceso: registro, inicio y cierre de sesión, recuperación de contraseña.
2. Validación de entradas en el registro de barberos y en el catálogo de servicios (precios, duraciones).
3. Disponibilidad del barbero y consulta de horarios libres por fecha y franja del día.
4. Cálculo automático de horarios de cita (`hora_fin = hora_inicio + duración total de los servicios`) y límite de citas activas por cliente.
5. Detección y prevención estricta de choques de horario (**RF-20**) para un mismo barbero.
6. Integridad referencial e independencia entre agendas de diferentes barberos.
7. Cancelación y reprogramación con reglas de anticipación.
8. Control de estados operativos y bloqueo de modificaciones sobre citas en estado terminal.
9. Suspensión del cliente por inasistencias.
10. Notificaciones por correo electrónico.
11. Requisitos no funcionales (seguridad, usabilidad, localización, rendimiento y arquitectura).

**Fuera del alcance de este plan:** RF-31 y RF-32 (dashboard y calificaciones, por confirmar) y las notificaciones por SMS/WhatsApp (excluidas hasta la versión 2.0).

---

## 2. Técnicas de Diseño de Pruebas Aplicadas

Siguiendo las metodologías vistas en clase, se aplicaron dos técnicas de caja negra formales.

### A. Partición de Equivalencia (Equivalence Partitioning)
Se dividió el dominio de entrada en clases válidas e inválidas para probar comportamientos representativos sin redundancia:

| Variable / Campo | Clase Válida | Clases Inválidas |
|---|---|---|
| **Duración del servicio** | Entero entre 1 y 240 minutos (> 0) | ≤ 0 minutos (ej. 0, -15), > 240 min, o no numérico |
| **Precio del servicio** | Decimal mayor o igual a 0 | Decimal negativo (ej. -5.000) o vacío |
| **Estado de la cita** | `'Programada'`, `'Atendida'`, `'Cancelada'`, `'Inasistencia'` | Cualquier cadena arbitraria (ej. `'Borrador'`, `'Esperando'`) |
| **Horario del barbero** | Turno en franja sin citas activas | Turno que interseca con una cita activa existente |
| **Intervalo del horario del barbero** | Hora de inicio múltiplo de 30 min (PN-02) | Hora de inicio fuera del intervalo (ej. 08:10) o fin anterior al inicio |
| **Fecha y hora de la cita** | Hoy con hora futura, o fecha futura | Fecha y hora anteriores a la actual |
| **Franja del día** | Mañana, Tarde o Noche | Sin franja elegida |
| **Citas activas del cliente** | 0 o 1 (puede agendar otra) | 2 (límite alcanzado, PN-09) |
| **Anticipación para cancelar o reprogramar** | 12 horas o más (PN-04, PN-05) | Menos de 12 horas |
| **Reprogramaciones de una cita** | 0 (primera vez) | 1 o más (PN-05) |
| **Inasistencias dentro de 3 meses** | 0 o 1 (sin suspensión) | 2 o más (suspensión de 1 mes, PN-10) |
| **Vigencia del enlace de recuperación** | Hasta 1 hora (PN-01) | Más de 1 hora |
| **Inactividad de la sesión** | Menos de 15 minutos (PN-07) | 15 minutos o más |

### B. Análisis de Valores Límite (Boundary Value Analysis - BVA)
Se probaron las fronteras críticas del algoritmo de solapamiento de tiempo para evitar falsos positivos o falsos negativos:

```text
Caso Cita Existente: [10:00 ---------------- 10:30)

Caso Límite Válido (Contiguo posterior): [10:30 -------- 11:00) -> APROBADO (HTTP 201)
Caso Límite Válido (Contiguo anterior):  [09:30 -------- 10:00) -> APROBADO (HTTP 201)
Caso Límite Inválido (Solape 1 min):     [10:29 -------- 10:59) -> CONFLICTO (HTTP 409)
Caso Límite Inválido (Solape 1 min):     [09:31 -------- 10:01) -> CONFLICTO (HTTP 409)
Caso Interior Inválido:                    [10:10 --- 10:25)     -> CONFLICTO (HTTP 409)
```

También se probaron las fronteras de las políticas del negocio, con un valor justo dentro y otro justo fuera del límite:

| Límite | Justo dentro (aceptado) | Justo fuera (rechazado) |
|---|---|---|
| Anticipación para cancelar o reprogramar (PN-04, PN-05) | 12 h 01 min | 11 h 59 min |
| Citas activas por cliente (PN-09) | 1 cita activa (agenda la segunda) | 2 citas activas (rechaza la tercera) |
| Vigencia del enlace de recuperación (PN-01) | 59 min | 61 min |
| Inactividad de la sesión (PN-07) | 14 min | 16 min |
| Periodo de inasistencias (PN-10) | 2 meses y 29 días | 3 meses y 1 día |
| Duración del servicio | 1 min y 240 min | 0 min y 241 min |
| Franja del día (PN-03) | 11:30 pertenece a Mañana | 12:00 ya pertenece a Tarde |

### Convención de códigos HTTP

| Código | Uso |
|---|---|
| `200 OK` / `201 Created` | Operación o creación exitosa. |
| `400 Bad Request` | Regla de negocio incumplida: correo duplicado, fecha pasada, enlace vencido, cancelar o reprogramar fuera de plazo, estado terminal. |
| `401 Unauthorized` | Credenciales inválidas o sesión inexistente o expirada. |
| `403 Forbidden` | Rol sin permiso, recurso de otro usuario o cuenta suspendida. |
| `404 Not Found` | El recurso referenciado no existe o está inactivo. |
| `409 Conflict` | Conflicto con el estado actual de la agenda: choque de horario o límite de citas. |
| `422 Unprocessable Entity` | Error de validación de esquema (Pydantic). |
| `—` | El caso se verifica en la interfaz, en el correo o por inspección, sin código HTTP. |

---

## 3. Matriz Detallada de Casos de Prueba (CP)

### 3.1 Cuentas y acceso

| ID | Requisito | Técnica | Condición / Entrada | Resultado Esperado | Código HTTP |
|---|---|---|---|---|---|
| **CP-RF01-1** | RF-01 | Partición Válida | Registrar un cliente con nombre, teléfono, un correo que no está en el sistema y una contraseña válida. | Cuenta creada; el cliente puede iniciar sesión con esos datos. | `201 Created` |
| **CP-RF01-2** | RF-01 | Partición Inválida | Registrar un cliente con un correo que ya está registrado. | Rechazado con aviso de correo ya registrado; no se crea una cuenta nueva. | `400 Bad Request` |
| **CP-RF01-3** | RF-01 | Partición Inválida | Registrar un cliente con un correo sin formato válido (ej. `juan@`). | Rechazado por validación de formato. | `422 Unprocessable` |
| **CP-RF02-1** | RF-02 | Partición Válida | Iniciar sesión con el correo registrado y la contraseña correcta. | El sistema lo deja ingresar y muestra la interfaz de su rol. | `200 OK` |
| **CP-RF02-2** | RF-02 | Partición Inválida | Iniciar sesión con un correo no registrado. | Aviso de que el correo debe estar registrado; no ingresa. | `401 Unauthorized` |
| **CP-RF02-3** | RF-02 | Partición Inválida | Iniciar sesión con un correo registrado y una contraseña incorrecta. | Rechazado; no ingresa. | `401 Unauthorized` |
| **CP-RF03-1** | RF-03 | Partición Válida | Un usuario con sesión iniciada presiona "Cerrar sesión". | La sesión termina y el sistema lo lleva a la pantalla de inicio de sesión. | `200 OK` |
| **CP-RF03-2** | RF-03 | Partición Inválida | Con la sesión ya cerrada, intentar acceder a un recurso privado (botón "atrás" o URL directa). | No se muestra información privada; se pide iniciar sesión. | `401 Unauthorized` |
| **CP-RF04-1** | RF-04 | Valor Límite | Abrir el enlace de recuperación a los 59 minutos de emitido y definir una nueva contraseña. | Contraseña cambiada; el usuario inicia sesión con la nueva. | `200 OK` |
| **CP-RF04-2** | RF-04 | Valor Límite | Abrir el enlace de recuperación a los 61 minutos de emitido. | Aviso de que el enlace caducó; no se permite cambiar la contraseña. | `400 Bad Request` |

### 3.2 Gestión de barberos (administrador)

| ID | Requisito | Técnica | Condición / Entrada | Resultado Esperado | Código HTTP |
|---|---|---|---|---|---|
| **CP-RF05-1** | RF-05 | Partición Válida | Registrar un barbero con correo, contraseña y nombre, sin foto. | Barbero guardado con `activo = true`, aparece en la lista y puede iniciar sesión. | `201 Created` |
| **CP-RF05-2** | RF-05 | Partición Inválida | Registrar un barbero dejando el nombre vacío. | Error de validación; el nombre es obligatorio. | `422 Unprocessable` |
| **CP-RF05-3** | RF-05 | Partición Inválida | Registrar un barbero con un correo ya existente. | Rechazado con mensaje de error explicativo. | `400 Bad Request` |
| **CP-RF06-1** | RF-06 | Partición Válida | Cambiar el nombre y la foto de un barbero y guardar. | Cambios guardados; el cliente ve el perfil actualizado al elegir barbero. | `200 OK` |
| **CP-RF06-2** | RF-06 | Partición Inválida | Borrar el nombre de un barbero y guardar. | Error de validación; el perfil conserva los datos anteriores. | `422 Unprocessable` |
| **CP-RF07-1** | RF-07 | Partición Válida | Eliminar el perfil de un barbero que tiene citas futuras y pasadas. | Perfil inactivo; citas futuras en `Cancelada`; clientes notificados; historial conservado. | `200 OK` |
| **CP-RF07-2** | RF-07 | Partición Inválida | Un barbero con perfil eliminado intenta iniciar sesión. | No puede ingresar. | `401 Unauthorized` |

### 3.3 Catálogo y gestión de servicios (administrador)

| ID | Requisito | Técnica | Condición / Entrada | Resultado Esperado | Código HTTP |
|---|---|---|---|---|---|
| **CP-RF08-1** | RF-08 | Partición Válida | Crear servicio con nombre "Corte", duración 30 min, precio $15.000. | Servicio persistido en BD y disponible en el catálogo. | `201 Created` |
| **CP-RF08-2** | RF-08 | Partición Inválida | Crear servicio con precio negativo (-$5.000). | Error de validación Pydantic. | `422 Unprocessable` |
| **CP-RF08-3** | RF-08 | Partición Inválida | Crear servicio con el precio vacío. | Error de validación; no se guarda. | `422 Unprocessable` |
| **CP-RF08-4** | RF-08 | Valor Límite | Crear servicio con duración 0 minutos. | Error de validación Pydantic (`gt=0`). | `422 Unprocessable` |
| **CP-RF08-5** | RF-08 | Valor Límite | Crear servicio con duración 1 minuto. | Servicio persistido. | `201 Created` |
| **CP-RF08-6** | RF-08 | Valor Límite | Crear servicio con duración 240 minutos. | Servicio persistido. | `201 Created` |
| **CP-RF08-7** | RF-08 | Valor Límite | Crear servicio con duración 241 minutos. | Error de validación; supera el máximo. | `422 Unprocessable` |
| **CP-RF08-8** | RF-08 | Valor Límite | Crear servicio con precio $0. | Servicio persistido (el precio puede ser 0). | `201 Created` |
| **CP-RF08-9** | RF-08 | Partición Inválida | Crear servicio con duración no numérica (ej. `"abc"`). | Error de validación Pydantic. | `422 Unprocessable` |
| **CP-RF09-1** | RF-09 | Partición Válida | Cambiar el precio de un servicio que tiene citas ya agendadas. | Las citas nuevas usan el precio nuevo; las ya agendadas conservan el anterior. | `200 OK` |
| **CP-RF09-2** | RF-09 | Partición Inválida | Dejar el nombre del servicio vacío y guardar. | Error de validación; el servicio conserva sus datos anteriores. | `422 Unprocessable` |
| **CP-RF10-1** | RF-10 | Partición Válida | Eliminar un servicio que tiene citas pasadas y citas ya agendadas. | Servicio inactivo; las citas existentes no cambian. | `200 OK` |
| **CP-RF10-2** | RF-10 | Partición Inválida | Un cliente intenta agendar con un servicio eliminado. | El servicio no aparece en la lista y el sistema rechaza elegirlo. | `404 Not Found` |

### 3.4 Disponibilidad (barbero)

| ID | Requisito | Técnica | Condición / Entrada | Resultado Esperado | Código HTTP |
|---|---|---|---|---|---|
| **CP-RF11-1** | RF-11 | Partición Válida | El barbero define los lunes de 08:00 a 12:00 en intervalos de 30 minutos. | Horario guardado; los clientes ven esos espacios los lunes. | `201 Created` |
| **CP-RF11-2** | RF-11 | Partición Inválida | Definir un horario con hora de fin anterior a la de inicio. | Error de validación; no se guarda. | `422 Unprocessable` |
| **CP-RF11-3** | RF-11 | Partición Inválida | Definir un horario que empieza a las 08:10 (fuera del intervalo de 30 min). | Rechazado; no se guarda. | `422 Unprocessable` |
| **CP-RF12-1** | RF-12 | Partición Válida | El barbero bloquea un día futuro. | Bloqueo guardado; ese día no ofrece horarios a los clientes. | `201 Created` |
| **CP-RF12-2** | RF-12 | Partición Inválida | El barbero intenta bloquear una fecha que ya pasó. | Rechazado; la fecha no es válida. | `400 Bad Request` |

### 3.5 Agendamiento (cliente)

| ID | Requisito | Técnica | Condición / Entrada | Resultado Esperado | Código HTTP |
|---|---|---|---|---|---|
| **CP-RF13-1** | RF-13 | Partición Válida | El cliente entra a agendar y abre la lista de barberos. | Ve los barberos activos con nombre y foto y puede elegir uno. | `200 OK` |
| **CP-RF13-2** | RF-13 | Partición Inválida | El cliente abre la lista después de que un barbero fue eliminado. | El barbero eliminado no aparece. | `200 OK` |
| **CP-RF14-1** | RF-14 | Partición Válida | El cliente elige dos servicios de la lista. | Ambos quedan marcados y puede continuar. | `200 OK` |
| **CP-RF14-2** | RF-14 | Partición Inválida | El cliente intenta continuar sin elegir ningún servicio. | Aviso de que debe elegir al menos uno; no avanza. | `422 Unprocessable` |
| **CP-RF15-1** | RF-15 | Partición Válida | Elegir un servicio de $20.000 y 30 min y otro de $10.000 y 15 min. | Total $30.000 y duración total 45 minutos. | `200 OK` |
| **CP-RF15-2** | RF-15 | Partición Inválida | El cliente quita todos los servicios elegidos e intenta continuar. | Total $0; no permite continuar. | `422 Unprocessable` |
| **CP-RF16-1** | RF-16 | Partición Válida | El cliente elige una fecha futura. | El sistema la acepta y muestra las franjas del día. | `200 OK` |
| **CP-RF16-2** | RF-16 | Partición Inválida | El cliente intenta agendar en una fecha que ya pasó. | Rechazado por fecha en el pasado. | `400 Bad Request` |
| **CP-RF16-3** | RF-16 | Valor Límite | Agendar hoy con hora de inicio 1 minuto antes de la hora actual. | Rechazado por hora en el pasado. | `400 Bad Request` |
| **CP-RF16-4** | RF-16 | Valor Límite | Agendar hoy con hora de inicio 1 minuto después de la hora actual, en un horario libre. | Cita aceptada. | `201 Created` |
| **CP-RF17-1** | RF-17 | Partición Válida | El cliente elige la franja "Tarde". | Toma el rango 12:00 a 18:00 y muestra los horarios de ese rango. | `200 OK` |
| **CP-RF17-2** | RF-17 | Partición Inválida | El cliente intenta continuar sin elegir franja. | Aviso de que debe elegir una; no avanza. | `422 Unprocessable` |
| **CP-RF17-3** | RF-17 | Valor Límite | Con la franja "Mañana", el barbero tiene libres 11:30 y 12:00. | Se muestra 11:30; 12:00 no aparece porque pertenece a "Tarde". | `200 OK` |
| **CP-RF18-1** | RF-18 | Partición Válida | Barbero con horarios libres de 14:00 a 17:00, franja "Tarde" y servicios de 45 min. | Solo se muestran los horarios libres de esa franja que alcanzan para 45 min. | `200 OK` |
| **CP-RF18-2** | RF-18 | Partición Inválida | Mismo caso, con un horario ya reservado y un último espacio que no alcanza para 45 min. | No se muestran ni el horario reservado ni el espacio insuficiente. | `200 OK` |
| **CP-RF18-3** | RF-18 | Partición Inválida | Mismo caso, con una hora bloqueada por el barbero (RF-12). | La hora bloqueada no se muestra. | `200 OK` |
| **CP-RF19-1** | RF-19 | Partición Válida | Un cliente con 1 cita activa elige un horario libre y confirma. | Cita creada en estado `Programada` con código de reserva único (`BSP-...`). | `201 Created` |
| **CP-RF19-2** | RF-19 | Valor Límite | Un cliente con 2 citas activas intenta agendar una tercera. | Rechazada; aviso de que alcanzó el límite de citas. | `409 Conflict` |
| **CP-RF19-3** | RF-19 | Valor Límite | Un cliente con 2 citas activas cancela una y agenda otra. | La nueva cita se crea. | `201 Created` |
| **CP-RF19-4** | RF-19 | Partición Válida | Un cliente con 1 cita activa y 3 citas en estado `Atendida` agenda otra. | La nueva cita se crea; solo cuentan las citas `Programada`. | `201 Created` |
| **CP-RF19-5** | RF-19 | Partición Válida | Agendar con el Barbero 1 un servicio de 30 min a las 09:00, en horario libre. | Cita agendada, código `BSP-...` generado, hora de fin 09:30. | `201 Created` |
| **CP-RF19-6** | RF-19 | Partición Válida | Agendar servicios con duración total de 45 min a las 10:00, en horario libre. | Hora de fin calculada exactamente a las 10:45. | `201 Created` |
| **CP-RF20-1** | RF-20 | Partición Válida | El cliente A reserva un horario libre; el cliente B consulta el mismo barbero y fecha. | El horario reservado ya no aparece disponible para B. | `200 OK` |
| **CP-RF20-2** | RF-20 | Partición Inválida | A y B tienen el mismo horario en pantalla; A confirma y luego B intenta confirmar. | Se acepta la de A (`201`); la de B se rechaza e informa que el horario ya no está disponible. | `409 Conflict` |
| **CP-RF20-3** | RF-20 | Valor Límite Frontera | Agendar con inicio exactamente a la hora de fin de la anterior (10:30 tras una cita de 10:00 a 10:30). | Permitido. Citas contiguas no colisionan. | `201 Created` |
| **CP-RF20-4** | RF-20 | Valor Límite Frontera | Agendar con solape de 1 minuto (10:29 cuando hay cita hasta 10:30). | Rechazado por choque de horario. | `409 Conflict` |
| **CP-RF20-5** | RF-20 | Partición Inválida | Agendar una cita totalmente contenida dentro de otra existente (10:05 a 10:25). | Rechazado por choque de horario. | `409 Conflict` |
| **CP-RF20-6** | RF-20 | Independencia de Datos | Agendar a las 10:00 con el Barbero 2 cuando el Barbero 1 ya está ocupado a las 10:00. | Permitido. Cada profesional tiene agenda independiente. | `201 Created` |
| **CP-RF20-7** | RF-20 | Valor Límite Frontera | Agendar de 09:30 a 10:00 cuando hay una cita de 10:00 a 10:30. | Permitido. Contigua por el lado anterior. | `201 Created` |
| **CP-RF20-8** | RF-20 | Valor Límite Frontera | Agendar de 09:31 a 10:01 cuando hay una cita de 10:00 a 10:30. | Rechazado por solape de 1 minuto. | `409 Conflict` |

### 3.6 Gestión de citas (cliente)

| ID | Requisito | Técnica | Condición / Entrada | Resultado Esperado | Código HTTP |
|---|---|---|---|---|---|
| **CP-RF21-1** | RF-21 | Partición Válida | El cliente agenda una cita correctamente. | Recibe un correo con barbero, servicios, fecha, hora, total y código de reserva. | `—` |
| **CP-RF21-2** | RF-21 | Partición Inválida | Una cita es rechazada por límite de citas (CP-RF19-2). | No se envía ningún correo de confirmación. | `409 Conflict` |
| **CP-RF22-1** | RF-22 | Partición Válida | Un cliente con citas agendadas y pasadas abre "Mis citas". | Ve sus citas agendadas y su historial. | `200 OK` |
| **CP-RF22-2** | RF-22 | Partición Inválida | Un cliente solicita por su identificador la cita de otro cliente. | El sistema no muestra la cita ajena. | `403 Forbidden` |
| **CP-RF23-1** | RF-23 | Valor Límite | Cancelar una cita con 12 h 01 min de anticipación. | Estado `Cancelada`; el horario del barbero se libera. | `200 OK` |
| **CP-RF23-2** | RF-23 | Valor Límite | Cancelar una cita con 11 h 59 min de anticipación. | Denegado; el límite de cancelación expiró. | `400 Bad Request` |
| **CP-RF23-3** | RF-23 | Máquina de Estados | Cancelar una cita que ya está en estado `Cancelada` o `Atendida`. | Rechazado por estado terminal. | `400 Bad Request` |
| **CP-RF24-1** | RF-24 | Partición Válida | Reprogramar por primera vez una cita (más de 12 h) a un horario libre del mismo barbero. | La cita pasa al nuevo horario y el anterior queda libre. | `200 OK` |
| **CP-RF24-2** | RF-24 | Partición Inválida | Reprogramar por segunda vez la misma cita. | Rechazado; ya se usó la reprogramación. | `400 Bad Request` |
| **CP-RF24-3** | RF-24 | Valor Límite | Reprogramar una cita con 11 h 59 min de anticipación. | Rechazado por falta de anticipación. | `400 Bad Request` |
| **CP-RF24-4** | RF-24 | Partición Inválida | Reprogramar a un horario que se solapa con otra cita del barbero. | Rechazado por choque de horario. | `409 Conflict` |
| **CP-RF25-1** | RF-25 | Partición Válida | Cancelar o reprogramar una cita con la anticipación requerida. | Se envía un correo al cliente y otro al barbero. | `200 OK` |
| **CP-RF25-2** | RF-25 | Partición Inválida | Intentar cancelar con menos de 12 h y que el sistema lo rechace. | No se envía ningún correo. | `400 Bad Request` |

### 3.7 Atención (barbero)

| ID | Requisito | Técnica | Condición / Entrada | Resultado Esperado | Código HTTP |
|---|---|---|---|---|---|
| **CP-RF26-1** | RF-26 | Partición Válida | El barbero consulta su agenda de una fecha y de una semana. | Recibe la lista cronológica de sus citas con cliente y servicios. | `200 OK` |
| **CP-RF26-2** | RF-26 | Partición Inválida | El Barbero A solicita la agenda del Barbero B. | El sistema niega el acceso. | `403 Forbidden` |
| **CP-RF27-1** | RF-27 | Máquina de Estados | Con la hora de inicio ya llegada, marcar una cita `Programada` como `Atendida`. | El estado cambia a `Atendida`. | `200 OK` |
| **CP-RF27-2** | RF-27 | Máquina de Estados | Marcar como `Atendida` una cita que aún no ha empezado. | Rechazado; no se permite el cambio. | `400 Bad Request` |
| **CP-RF27-3** | RF-27 | Máquina de Estados | Intentar cambiar el estado de una cita ya marcada como `Atendida`. | Rechazado por regla de negocio de estado terminal. | `400 Bad Request` |
| **CP-RF27-4** | RF-27 | Máquina de Estados | Con la hora de inicio ya llegada, marcar una cita como `Inasistencia`. | El estado cambia a `Inasistencia`. | `200 OK` |
| **CP-RF27-5** | RF-27 | Partición Inválida | Cambiar el estado de una cita a una cadena arbitraria (ej. `'Borrador'`). | Error de validación. | `422 Unprocessable` |

### 3.8 Consulta general (administrador)

| ID | Requisito | Técnica | Condición / Entrada | Resultado Esperado | Código HTTP |
|---|---|---|---|---|---|
| **CP-RF28-1** | RF-28 | Partición Válida | El administrador filtra por un barbero y el estado `Cancelada`. | Se muestran solo las citas de ese barbero que están canceladas. | `200 OK` |
| **CP-RF28-2** | RF-28 | Partición Inválida | Filtrar por una fecha en la que el barbero no tiene citas. | Mensaje de que no hay citas, sin errores. | `200 OK` |
| **CP-RF28-3** | RF-28 | Partición Inválida | Un cliente intenta consultar todas las citas. | El sistema niega el acceso. | `403 Forbidden` |

### 3.9 Control de inasistencias

| ID | Requisito | Técnica | Condición / Entrada | Resultado Esperado | Código HTTP |
|---|---|---|---|---|---|
| **CP-RF29-1** | RF-29 | Valor Límite | Un cliente con 1 inasistencia de hace 2 meses y 29 días recibe una segunda. | La cuenta se suspende durante 1 mes. | `200 OK` |
| **CP-RF29-2** | RF-29 | Valor Límite | Un cliente con 1 inasistencia de hace 3 meses y 1 día recibe otra. | No se suspende; solo cuenta 1 inasistencia. | `200 OK` |
| **CP-RF29-3** | RF-29 | Partición Válida | Un cliente sin inasistencias recibe la primera. | No se suspende. | `200 OK` |
| **CP-RF29-4** | RF-29 | Partición Válida | Un cliente cuya suspensión terminó recibe una nueva inasistencia. | No se suspende; el contador se había reiniciado en cero. | `200 OK` |
| **CP-RF30-1** | RF-30 | Partición Inválida | Un cliente suspendido intenta iniciar sesión. | No ingresa; ve que su cuenta está suspendida y la fecha de reactivación. | `403 Forbidden` |
| **CP-RF30-2** | RF-30 | Partición Válida | Un cliente cuya suspensión ya terminó inicia sesión. | Ingresa sin ningún aviso de suspensión. | `200 OK` |
| **CP-RF30-3** | RF-30 | Partición Inválida | Un cliente suspendido intenta agendar una cita. | Rechazado. | `403 Forbidden` |

### 3.10 Requisitos no funcionales

| ID | Requisito | Técnica | Condición / Entrada | Resultado Esperado | Código HTTP |
|---|---|---|---|---|---|
| **CP-RNF01-1** | RNF-01 | Prueba de Seguridad | Registrar un cliente y revisar cómo quedó guardada su contraseña en la BD. | Está almacenada como hash, no en texto legible. | `—` |
| **CP-RNF01-2** | RNF-01 | Prueba de Seguridad | Solicitar la recuperación de contraseña. | El correo contiene solo un enlace, nunca la contraseña actual. | `—` |
| **CP-RNF02-1** | RNF-02 | Valor Límite | Un usuario permanece 16 minutos inactivo e intenta una acción. | La sesión expiró; se pide iniciar sesión. | `401 Unauthorized` |
| **CP-RNF02-2** | RNF-02 | Valor Límite | Un usuario permanece 14 minutos inactivo y luego realiza una acción. | La sesión sigue activa y la acción se completa. | `200 OK` |
| **CP-RNF03-1** | RNF-03 | Partición Válida | El administrador abre la gestión de barberos y de servicios. | Acceso permitido. | `200 OK` |
| **CP-RNF03-2** | RNF-03 | Partición Inválida | Un cliente intenta abrir la dirección de gestión de barberos. | Acceso denegado. | `403 Forbidden` |
| **CP-RNF04-1** | RNF-04 | Prueba de Usabilidad | Abrir la app en un celular y recorrer el flujo de agendar una cita. | Todas las pantallas se ven completas y se usan sin desplazamiento horizontal. | `—` |
| **CP-RNF04-2** | RNF-04 | Prueba de Usabilidad | Reducir la ventana del navegador de computador a 320 px de ancho. | No hay elementos cortados, superpuestos ni botones inaccesibles. | `—` |
| **CP-RNF05-1** | RNF-05 | Partición Válida | Agendar una cita a las 3:00 p. m. | La app y el correo de confirmación muestran 3:00 p. m. hora de Colombia (UTC-5). | `—` |
| **CP-RNF05-2** | RNF-05 | Partición Inválida | Consultar la cita desde un dispositivo configurado en otra zona horaria. | La hora mostrada sigue siendo la de Colombia, sin conversión. | `—` |
| **CP-RNF06-1** | RNF-06 | Partición Válida | Un cliente se registra y acepta el aviso de privacidad y la autorización de datos. | El sistema muestra el aviso y crea la cuenta. | `201 Created` |
| **CP-RNF06-2** | RNF-06 | Partición Inválida | Un cliente completa el registro sin aceptar la autorización de datos. | No se permite registrarse hasta aceptarla. | `422 Unprocessable` |
| **CP-RNF07-1** | RNF-07 | Partición Válida | Crear una cita con un barbero y un cliente existentes. | La cita se persiste con claves foráneas válidas. | `201 Created` |
| **CP-RNF07-2** | RNF-07 | Partición Inválida | Crear una cita con un `barbero_id` que no existe. | Rechazada por integridad referencial; no se guarda. | `404 Not Found` |
| **CP-RNF08-1** | RNF-08 | Prueba de Rendimiento | Consultar la disponibilidad de un barbero con 500 citas cargadas. | Responde en menos de 300 ms. | `200 OK` |
| **CP-RNF08-2** | RNF-08 | Prueba de Rendimiento | Lanzar 20 consultas de disponibilidad simultáneas. | Cada una responde en menos de 300 ms. | `200 OK` |
| **CP-RNF09-1** | RNF-09 | Inspección de Código | Revisar la estructura del backend. | Existen capas separadas: modelos, esquemas Pydantic, rutas y repositorios/servicios. | `—` |
| **CP-RNF09-2** | RNF-09 | Inspección de Código | Revisar las rutas (controladores). | Ninguna ruta contiene consultas SQL ni accede directamente a la BD. | `—` |
| **CP-RNF10-1** | RNF-10 | Inspección de Código | Revisar el repositorio de control de versiones. | No contiene `.env` ni credenciales; existe `.env.example`. | `—` |
| **CP-RNF10-2** | RNF-10 | Prueba de Seguridad | Iniciar sesión con el correo `' OR '1'='1`. | Rechazado sin acceso; la BD no se altera. | `401` o `422` |

---

## 4. Automatización con Pytest

* **Framework:** `pytest` con `httpx.AsyncClient` y `TestClient` de FastAPI.
* **Aislamiento:** Base de datos SQLite en memoria (`sqlite:///:memory:`) para que las pruebas corran en milisegundos y sean reproducibles en cualquier máquina sin tocar datos reales.
* **Usuarios de prueba:** fixtures que crean un cliente, un barbero y un administrador con su sesión iniciada, para probar los casos por rol.
* **Control del tiempo:** los casos de anticipación (12 h), vigencia del enlace (1 h), inactividad (15 min) y periodo de inasistencias (3 meses) necesitan fijar la hora actual. Se recomienda una librería de reloj controlado (por ejemplo `freezegun`).
* **Correo:** el envío real se sustituye por un doble de prueba (mock) y se verifica a quién y con qué contenido se enviaría.
* **Comando de ejecución:**
  ```bash
  pytest tests/ -v
  ```

Los casos con código `—` (interfaz, correo e inspección) se verifican manualmente o con herramientas fuera de `pytest`.

---

## 5. Supuestos y Observaciones

- **Franja del día:** se asume que un horario pertenece a la franja según su hora de inicio (CP-RF17-3).
- **Solapamiento a nivel de servicio:** los casos CP-RF20-3 a CP-RF20-8 usan horas como 10:29 o 09:31, que no coinciden con el intervalo de 30 minutos (PN-02). Se ejecutan sobre la lógica de solapamiento (servicio o API), no desde la interfaz, que solo ofrece horarios en intervalos de 30 minutos.
- **Duración máxima de 240 minutos:** viene de la partición del plan v1.0 pero no aparece en RF-08 de la especificación. Hay que confirmarla y agregarla al requisito, o retirar CP-RF08-6 y CP-RF08-7.
- **Límite exacto de 12 horas:** no se prueba con exactamente 12 horas de anticipación, porque la especificación no dice si en ese instante se permite. Hay que definirlo.
- **Códigos HTTP:** los códigos `401`, `403` y `404` son una propuesta nueva. Los demás (`201`, `400`, `409`, `422`) mantienen el uso de la v1.0.
- **RNF-08 y RNF-09:** no tienen un caso negativo estricto; se verifican con una prueba de rendimiento y una inspección de código.

---
