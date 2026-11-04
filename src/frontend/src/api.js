// Cliente HTTP centralizado de BarberShop Pro (backend v1.1).
//
// Todas las llamadas al backend pasan por este módulo: URL base, cabecera de autenticación
// (Authorization: Bearer <token>, ver `obtener_usuario_actual` en main.py), almacenamiento del token,
// interpretación de errores (`detail`, 401, 403 con `suspendido_hasta`, 422) y rutas de cada endpoint.
// Las reglas de negocio las valida el backend; aquí solo se transporta y se traduce su respuesta.

const BASE_URL = (import.meta.env?.VITE_API_URL || 'http://127.0.0.1:8000/api').replace(/\/+$/, '');

const CLAVE_TOKEN = 'bsp_token';
const CLAVE_USUARIO = 'bsp_usuario';

// ---------------------------------------------------------------------------
// Sesión (sessionStorage: la sesión no sobrevive al cierre de la pestaña y además el backend
// la expira a los 15 minutos de inactividad, PN-07)
// ---------------------------------------------------------------------------
function almacen() {
  try {
    return typeof sessionStorage === 'undefined' ? null : sessionStorage;
  } catch {
    return null;
  }
}

export function obtenerToken() {
  return almacen()?.getItem(CLAVE_TOKEN) || null;
}

export function obtenerUsuarioGuardado() {
  const bruto = almacen()?.getItem(CLAVE_USUARIO);
  if (!bruto) return null;
  try {
    return JSON.parse(bruto);
  } catch {
    return null;
  }
}

export function guardarSesion(token, usuario) {
  const a = almacen();
  if (!a) return;
  a.setItem(CLAVE_TOKEN, token);
  a.setItem(CLAVE_USUARIO, JSON.stringify(usuario));
}

export function limpiarSesion() {
  const a = almacen();
  if (!a) return;
  a.removeItem(CLAVE_TOKEN);
  a.removeItem(CLAVE_USUARIO);
}

// El AuthContext se registra aquí para enterarse cuando el backend responde 401 a una petición autenticada
// (sesión expirada por inactividad, cerrada o inválida).
let alExpirarSesion = null;
export function registrarAlExpirarSesion(fn) {
  alExpirarSesion = fn;
  return () => {
    if (alExpirarSesion === fn) alExpirarSesion = null;
  };
}

// ---------------------------------------------------------------------------
// Errores
// ---------------------------------------------------------------------------
export class ApiError extends Error {
  constructor(status, mensaje, datos = null) {
    super(mensaje);
    this.name = 'ApiError';
    this.status = status; // 0 = sin conexión con el servidor
    this.datos = datos; // cuerpo JSON completo (p. ej. `suspendido_hasta`, `codigos`)
  }

  /** Fecha ISO (YYYY-MM-DD) de reactivación cuando la cuenta está suspendida (403). */
  get suspendidoHasta() {
    return this.datos?.suspendido_hasta ?? null;
  }
}

const ETIQUETAS_CAMPO = {
  nombre: 'El nombre',
  telefono: 'El teléfono',
  email: 'El correo electrónico',
  password: 'La contraseña',
  nueva_password: 'La nueva contraseña',
  token: 'El enlace',
  foto_url: 'La URL de la foto',
  duracion_minutos: 'La duración',
  precio: 'El precio',
  fecha: 'La fecha',
  hora_inicio: 'La hora de inicio',
  hora_fin: 'La hora de fin',
  dia_semana: 'El día de la semana',
  notas: 'Las notas',
  servicios_ids: 'Los servicios',
  barbero_id: 'El barbero',
  estado: 'El estado',
  franja: 'La franja',
  acepta_tratamiento_datos: 'La autorización de tratamiento de datos',
};

function campoDe(loc) {
  if (!Array.isArray(loc)) return null;
  const nombres = loc.filter((p) => typeof p === 'string' && !['body', 'query', 'path'].includes(p));
  return nombres.length ? nombres[nombres.length - 1] : null;
}

/** Convierte un elemento de `detail` de un 422 (Pydantic) en una frase en español. */
export function mensajeDeValidacion(err) {
  const campo = campoDe(err?.loc);
  const etiqueta = ETIQUETAS_CAMPO[campo] || 'El valor indicado';
  const ctx = err?.ctx || {};
  const msg = typeof err?.msg === 'string' ? err.msg : '';

  switch (err?.type) {
    case 'missing':
      return `${etiqueta} es obligatorio.`;
    case 'string_too_short':
      return ctx.min_length <= 1
        ? `${etiqueta} es obligatorio.`
        : `${etiqueta} debe tener al menos ${ctx.min_length} caracteres.`;
    case 'string_too_long':
      return `${etiqueta} no puede superar ${ctx.max_length} caracteres.`;
    case 'too_short':
      return campo === 'servicios_ids'
        ? 'Debes elegir al menos un servicio.'
        : `${etiqueta} debe incluir al menos ${ctx.min_length} elemento(s).`;
    case 'greater_than':
      return `${etiqueta} debe ser mayor que ${ctx.gt}.`;
    case 'greater_than_equal':
      return `${etiqueta} no puede ser menor que ${ctx.ge}.`;
    case 'less_than':
      return `${etiqueta} debe ser menor que ${ctx.lt}.`;
    case 'less_than_equal':
      return `${etiqueta} no puede ser mayor que ${ctx.le}.`;
    case 'int_parsing':
    case 'int_type':
    case 'int_from_float':
    case 'float_parsing':
    case 'float_type':
    case 'decimal_parsing':
    case 'decimal_type':
      return `${etiqueta} debe ser un número válido.`;
    case 'date_parsing':
    case 'date_type':
    case 'date_from_datetime_parsing':
      return `${etiqueta} no tiene un formato de fecha válido.`;
    case 'time_parsing':
    case 'time_type':
      return `${etiqueta} no tiene un formato de hora válido.`;
    case 'literal_error':
    case 'enum':
      return `${etiqueta} tiene un valor no permitido.`;
    case 'value_error':
    case 'assertion_error': {
      // Los validadores del backend escriben el mensaje en español: "Value error, <mensaje>".
      if (campo === 'email' && /email/i.test(msg)) return 'El correo electrónico no es válido.';
      const limpio = msg.replace(/^(Value error|Assertion failed),?\s*/i, '').trim();
      return limpio || `${etiqueta} no es válido.`;
    }
    default:
      return `${etiqueta} no es válido.`;
  }
}

/** Texto legible para un `detail` que es una lista de errores de validación. */
export function mensajeDeValidacionLista(detail) {
  const mensajes = [];
  detail.forEach((e) => {
    const m = mensajeDeValidacion(e);
    if (!mensajes.includes(m)) mensajes.push(m);
  });
  return mensajes.length ? mensajes.join(' ') : 'Revisa los datos ingresados.';
}

const MENSAJES_POR_ESTADO = {
  400: 'La operación no está permitida.',
  401: 'Debes iniciar sesión para continuar.',
  403: 'No tienes permiso para realizar esta acción.',
  404: 'No se encontró el recurso solicitado.',
  409: 'La operación entra en conflicto con el estado actual. Actualiza e inténtalo de nuevo.',
  422: 'Revisa los datos ingresados.',
};

/** Mensaje para mostrar al usuario a partir del estado HTTP y del cuerpo de la respuesta. */
export function mensajeDeRespuesta(status, datos) {
  if (status >= 500) return 'Ocurrió un error en el servidor. Inténtalo de nuevo más tarde.';
  const detail = datos?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail)) return mensajeDeValidacionLista(detail);
  return MENSAJES_POR_ESTADO[status] || 'No se pudo completar la operación.';
}

// ---------------------------------------------------------------------------
// Petición base
// ---------------------------------------------------------------------------
function construirQuery(params) {
  const q = new URLSearchParams();
  Object.entries(params || {}).forEach(([clave, valor]) => {
    if (valor === undefined || valor === null || valor === '') return;
    if (Array.isArray(valor)) valor.forEach((v) => q.append(clave, v)); // FastAPI espera ?servicios_ids=1&servicios_ids=2
    else q.append(clave, valor);
  });
  const texto = q.toString();
  return texto ? `?${texto}` : '';
}

async function solicitar(metodo, ruta, { cuerpo, params, autenticado = true, silenciarExpiracion = false } = {}) {
  const headers = {};
  if (cuerpo !== undefined) headers['Content-Type'] = 'application/json';
  const token = autenticado ? obtenerToken() : null;
  if (token) headers.Authorization = `Bearer ${token}`;

  let respuesta;
  try {
    respuesta = await fetch(`${BASE_URL}${ruta}${construirQuery(params)}`, {
      method: metodo,
      headers,
      body: cuerpo !== undefined ? JSON.stringify(cuerpo) : undefined,
    });
  } catch {
    throw new ApiError(0, 'No se pudo conectar con el servidor. Verifica tu conexión e inténtalo de nuevo.');
  }

  let datos;
  try {
    const texto = await respuesta.text();
    datos = texto ? JSON.parse(texto) : null;
  } catch {
    datos = null;
  }

  if (!respuesta.ok) {
    const error = new ApiError(respuesta.status, mensajeDeRespuesta(respuesta.status, datos), datos);
    // 401 en una ruta protegida: sesión expirada (15 min de inactividad), cerrada o inválida.
    // Solo se procesa si el token usado sigue siendo el vigente: así, varias peticiones simultáneas que
    // fallan a la vez muestran un único aviso (el primero), y una respuesta tardía de una sesión anterior
    // no cierra la sesión recién iniciada.
    if (respuesta.status === 401 && autenticado && !silenciarExpiracion && token && token === obtenerToken()) {
      limpiarSesion();
      if (alExpirarSesion) alExpirarSesion(error.message);
    }
    throw error;
  }
  return datos;
}

const get = (ruta, params, opciones) => solicitar('GET', ruta, { params, ...opciones });
const post = (ruta, cuerpo, opciones) => solicitar('POST', ruta, { cuerpo: cuerpo ?? undefined, ...opciones });
const patch = (ruta, cuerpo) => solicitar('PATCH', ruta, { cuerpo });
const del = (ruta) => solicitar('DELETE', ruta);

// ---------------------------------------------------------------------------
// Endpoints del backend v1.1 (main.py)
// ---------------------------------------------------------------------------
export const api = {
  // Autenticación (RF-01 a RF-04)
  registro: (datos) => post('/auth/registro', datos, { autenticado: false }),
  login: (email, password) => post('/auth/login', { email, password }, { autenticado: false }),
  logout: () => post('/auth/logout', undefined, { silenciarExpiracion: true }),
  recuperar: (email) => post('/auth/recuperar', { email }, { autenticado: false }),
  validarEnlaceRecuperacion: (token) => get('/auth/restablecer/validar', { token }, { autenticado: false }),
  restablecer: (token, nueva_password) => post('/auth/restablecer', { token, nueva_password }, { autenticado: false }),

  // Catálogo (cliente o administrador)
  barberos: () => get('/barberos'),
  servicios: () => get('/servicios'),

  // Agendamiento (cliente)
  resumenCita: (serviciosIds) => get('/citas/resumen', { servicios_ids: serviciosIds }),
  disponibilidad: ({ barberoId, fecha, franja, serviciosIds }) =>
    get('/disponibilidad', { barbero_id: barberoId, fecha, franja, servicios_ids: serviciosIds }),
  crearCita: (datos) => post('/citas', datos),

  // Gestión de citas (cliente)
  misCitas: () => get('/citas/mias'),
  cancelarCita: (id) => post(`/citas/${id}/cancelar`),
  disponibilidadReprogramacion: (id, { fecha, franja }) => get(`/citas/${id}/disponibilidad`, { fecha, franja }),
  reprogramarCita: (id, { fecha, hora_inicio }) => post(`/citas/${id}/reprogramar`, { fecha, hora_inicio }),

  // Barbero
  agenda: ({ fecha, vista }) => get('/barbero/agenda', { fecha, vista }),
  cambiarEstadoCita: (id, estado) => patch(`/citas/${id}/estado`, { estado }),
  listarDisponibilidad: () => get('/barbero/disponibilidad'),
  agregarDisponibilidad: (datos) => post('/barbero/disponibilidad', datos),
  eliminarDisponibilidad: (id) => del(`/barbero/disponibilidad/${id}`),
  listarBloqueos: () => get('/barbero/bloqueos'),
  agregarBloqueo: (datos) => post('/barbero/bloqueos', datos),
  eliminarBloqueo: (id) => del(`/barbero/bloqueos/${id}`),

  // Administrador
  adminBarberos: () => get('/admin/barberos'),
  adminCrearBarbero: (datos) => post('/admin/barberos', datos),
  adminActualizarBarbero: (id, datos) => patch(`/admin/barberos/${id}`, datos),
  adminEliminarBarbero: (id) => del(`/admin/barberos/${id}`),
  adminCrearServicio: (datos) => post('/admin/servicios', datos),
  adminActualizarServicio: (id, datos) => patch(`/admin/servicios/${id}`, datos),
  adminEliminarServicio: (id) => del(`/admin/servicios/${id}`),
  adminCitas: ({ barberoId, fecha, estado }) => get('/admin/citas', { barbero_id: barberoId, fecha, estado }),
};
