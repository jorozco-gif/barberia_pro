# 📋 Informe de Calidad, Defectos y Mantenimiento

**Proyecto:** BarberShop Pro — Sistema de Gestión y Agendamiento de Barbería  
**Materia:** Ingeniería de Software II (Código 17934) — Cotecnova  
**Responsable de Calidad:** Juan David Osorio  
**Responsable de Pruebas:** Sebastian Orozco  
**Líder Técnico:** Elizabeth Ramirez  
**Documentación:** Juan David Monroy  
**Versión:** 1.0 (Seguimiento 1)

---

## 1. Resumen Ejecutivo de Calidad

Este documento consolida el estado de la calidad del software para el **Seguimiento 1**, reportando las métricas de verificación, el registro formal de defectos detectados y resueltos, y las políticas de mantenimiento preventivo aplicadas al código fuente.

---

## 2. Métricas de Calidad del Producto (Seguimiento 1)

| Métrica | Meta / Umbral | Valor Obtenido | Estado |
|---|---|---|---|
| **Casos de prueba diseñados** | $\ge 8$ casos formales | 9 casos (CP-01 a CP-09) | ✅ Superado |
| **Tasa de éxito de pruebas automatizadas** | 100% | 100% (9 de 9 pasando) | ✅ Cumplido |
| **Tiempo promedio de ejecución de la suite** | $< 3.0$ segundos | $\approx 0.8$ segundos | ✅ Óptimo |
| **Vulnerabilidad de datos sensibles en Git** | 0 contraseñas / `.env` en repo | 0 credenciales expuestas | ✅ Seguro |
| **Tratamiento semántico de errores** | 0 errores genéricos `HTTP 500` | Uso de `400`, `404`, `409`, `422` | ✅ Cumplido |

---

## 3. Registro y Gestión de Defectos (Bugs)

*(Nota para la sustentación: Estos son los defectos reales que detectamos y corregimos durante la construcción del núcleo de agendamiento).*

### 🐛 Defecto DEF-001: Falso positivo de solapamiento en citas consecutivas
* **Severidad:** Alta
* **Módulo afectado:** `src/backend/services.py` (Función `hay_solapamiento`)
* **Descripción del problema:**
  Cuando un cliente reservaba una cita de `10:00` a `10:30` y otro cliente solicitaba la cita inmediatamente contigua de `10:30` a `11:00`, la condición inicial utilizaba `<=` en lugar de `<`. Como resultado, el sistema interpretaba que las 10:30 era un minuto compartido y bloqueaba erróneamente la segunda cita con `HTTP 409 Conflict`.
* **Pasos para reproducir:**
  1. Registrar una cita de 10:00 a 10:30 con el Barbero 1.
  2. Intentar agendar una segunda cita con el mismo barbero a las 10:30.
  3. Resultado antes del fix: `409 Conflict` (Defecto).
* **Causa raíz:**
  Comparación inclusiva de límites temporales en intervalos semiabiertos $[A, B)$.
* **Solución aplicada:**
  Se ajustó la fórmula formal a:
  $$\max(\text{Inicio}_A, \text{Inicio}_B) < \min(\text{Fin}_A, \text{Fin}_B)$$
  Garantizando que si $\text{Fin}_A == \text{Inicio}_B$, la condición evalúe a `False` (sin colisión).
* **Caso de prueba que lo valida:** `CP-05` (`test_agendar_citas_consecutivas_permitidas`).

---

### 🐛 Defecto DEF-002: Inyección de datos numéricos anómalos en el catálogo
* **Severidad:** Media
* **Módulo afectado:** `src/backend/schemas.py` (`ServicioCreate`)
* **Descripción del problema:**
  Se permitía enviar servicios con duración de $0$ minutos o precios negativos (ej. $-15.00$ COP). Esto provocaba que en el cálculo de disponibilidad el bucle temporal entrara en ciclos infinitos o citas con hora de inicio igual a la hora de fin.
* **Solución aplicada:**
  Se integraron validadores estrictos en Pydantic:
  * `duracion_minutos = Field(..., gt=0, le=240)`
  * `precio = Field(..., ge=0)`
  Ahora cualquier intento de valor anómalo es rechazado inmediatamente con `HTTP 422 Unprocessable Entity` antes de tocar la base de datos.
* **Casos de prueba que lo validan:** `CP-02` y `CP-03`.

---

### 🐛 Defecto DEF-003: Modificación indebida de citas cerradas/finalizadas
* **Severidad:** Media
* **Módulo afectado:** `src/backend/main.py` (`actualizar_estado_cita`)
* **Descripción del problema:**
  Una vez que un barbero marcaba una cita como `Finalizada`, la API permitía regresar el estado a `Pendiente` mediante peticiones directas `PATCH`. Esto violaba la regla de auditoría del negocio.
* **Solución aplicada:**
  Se agregó una guarda en el endpoint que verifica si `cita.estado == "Finalizada"`. Si es así, interrumpe el flujo con `HTTP 400 Bad Request` indicando que es un estado terminal no modificable.
* **Caso de prueba que lo valida:** `CP-09` (`test_transicion_estado_finalizada_bloqueada`).

---

## 4. Plan de Mantenimiento Preventivo y Evolutivo

1. **Mantenimiento Preventivo:**
   * Ejecución obligatoria de la suite `pytest tests/ -v` antes de fusionar cualquier Pull Request a la rama `main`.
   * Verificación continua de no inclusión de archivos `.env` o bases de datos locales (`.gitignore`).
2. **Mantenimiento Evolutivo (Preparación para Seguimiento 2):**
   * Ampliación de la cobertura de pruebas al endpoint de cancelación (`RF-05`) con la regla de 2 horas de anticipación.
   * Implementación del módulo de métricas de rendimiento por barbero (`RF-08`).
