// Pruebas de la capa de acceso al backend (api.js), sin dependencias externas: `npm test` usa el
// ejecutor nativo de Node (node --test) con un fetch y un sessionStorage simulados.
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  api,
  ApiError,
  guardarSesion,
  limpiarSesion,
  mensajeDeRespuesta,
  mensajeDeValidacion,
  obtenerToken,
  obtenerUsuarioGuardado,
  registrarAlExpirarSesion,
} from './api.js';

// --- Simulación del navegador -------------------------------------------------------------
const memoria = new Map();
globalThis.sessionStorage = {
  getItem: (k) => (memoria.has(k) ? memoria.get(k) : null),
  setItem: (k, v) => memoria.set(k, String(v)),
  removeItem: (k) => memoria.delete(k),
};

let llamadas = [];
function simularRespuesta(status, cuerpo) {
  globalThis.fetch = async (url, opciones) => {
    llamadas.push({ url, opciones });
    return {
      ok: status >= 200 && status < 300,
      status,
      text: async () => (cuerpo === undefined ? '' : typeof cuerpo === 'string' ? cuerpo : JSON.stringify(cuerpo)),
    };
  };
}
function reiniciar() {
  llamadas = [];
  limpiarSesion();
  registrarAlExpirarSesion(null);
}

// --- Mensajes de error --------------------------------------------------------------------
test('detail de texto se muestra tal cual (400, 403, 409)', () => {
  assert.equal(mensajeDeRespuesta(400, { detail: 'El correo ya está registrado.' }), 'El correo ya está registrado.');
  assert.equal(mensajeDeRespuesta(409, { detail: 'Ese horario ya no está disponible.' }), 'Ese horario ya no está disponible.');
});

test('422 con lista de errores se traduce a español', () => {
  const detail = [
    { type: 'string_too_short', loc: ['body', 'password'], msg: 'String should have at least 8 characters', ctx: { min_length: 8 } },
    { type: 'missing', loc: ['body', 'telefono'], msg: 'Field required' },
    { type: 'value_error', loc: ['body', 'email'], msg: 'value is not a valid email address: An email address must have an @-sign.' },
    { type: 'value_error', loc: ['body'], msg: 'Value error, Debes autorizar el tratamiento de tus datos personales.' },
    { type: 'greater_than', loc: ['body', 'duracion_minutos'], msg: 'Input should be greater than 0', ctx: { gt: 0 } },
  ];
  const texto = mensajeDeRespuesta(422, { detail });
  assert.match(texto, /La contraseña debe tener al menos 8 caracteres\./);
  assert.match(texto, /El teléfono es obligatorio\./);
  assert.match(texto, /El correo electrónico no es válido\./);
  assert.match(texto, /Debes autorizar el tratamiento de tus datos personales\./);
  assert.match(texto, /La duración debe ser mayor que 0\./);
  assert.doesNotMatch(texto, /Field required|Value error/);
});

test('mensajeDeValidacion: lista de servicios vacía', () => {
  const m = mensajeDeValidacion({ type: 'too_short', loc: ['body', 'servicios_ids'], msg: 'List should have at least 1 item', ctx: { min_length: 1 } });
  assert.equal(m, 'Debes elegir al menos un servicio.');
});

test('errores 5xx y sin detail usan mensajes genéricos sin información técnica', () => {
  assert.match(mensajeDeRespuesta(500, 'Internal Server Error'), /error en el servidor/);
  assert.equal(mensajeDeRespuesta(404, null), 'No se encontró el recurso solicitado.');
  assert.equal(mensajeDeRespuesta(403, {}), 'No tienes permiso para realizar esta acción.');
});

// --- Peticiones ---------------------------------------------------------------------------
test('una petición autenticada envía Authorization: Bearer <token>', async () => {
  reiniciar();
  guardarSesion('tok-123', { id: 1, rol: 'cliente' });
  simularRespuesta(200, []);
  await api.misCitas();
  assert.equal(llamadas[0].opciones.headers.Authorization, 'Bearer tok-123');
  assert.match(llamadas[0].url, /\/citas\/mias$/);
});

test('login, registro y recuperación no envían token', async () => {
  reiniciar();
  guardarSesion('tok-123', { id: 1, rol: 'cliente' });
  simularRespuesta(200, { access_token: 'x', token_type: 'bearer', usuario: {} });
  await api.login('a@b.co', 'secreto123');
  await api.recuperar('a@b.co');
  await api.restablecer('t', 'nueva-clave-1');
  for (const l of llamadas) assert.equal(l.opciones.headers.Authorization, undefined);
  assert.deepEqual(JSON.parse(llamadas[0].opciones.body), { email: 'a@b.co', password: 'secreto123' });
});

test('servicios_ids se envía como parámetro repetido y los vacíos se omiten', async () => {
  reiniciar();
  simularRespuesta(200, []);
  await api.disponibilidad({ barberoId: 2, fecha: '2030-01-07', franja: 'Mañana', serviciosIds: [1, 3] });
  const url = new URL(llamadas[0].url);
  assert.equal(url.pathname.endsWith('/disponibilidad'), true);
  assert.deepEqual(url.searchParams.getAll('servicios_ids'), ['1', '3']);
  assert.equal(url.searchParams.get('barbero_id'), '2');
  assert.equal(url.searchParams.get('franja'), 'Mañana');

  await api.adminCitas({ barberoId: '', fecha: '', estado: 'Cancelada' });
  const u2 = new URL(llamadas[1].url);
  assert.equal(u2.searchParams.has('barbero_id'), false);
  assert.equal(u2.searchParams.get('estado'), 'Cancelada');
});

test('POST /citas envía los nombres de campo del esquema CitaCreate', async () => {
  reiniciar();
  simularRespuesta(201, { id: 1 });
  await api.crearCita({ barbero_id: 1, servicios_ids: [1, 2], fecha: '2030-01-07', hora_inicio: '10:00', notas: null });
  assert.equal(llamadas[0].opciones.method, 'POST');
  assert.deepEqual(Object.keys(JSON.parse(llamadas[0].opciones.body)).sort(), ['barbero_id', 'fecha', 'hora_inicio', 'notas', 'servicios_ids']);
});

test('401 en ruta protegida limpia la sesión y avisa al AuthContext', async () => {
  reiniciar();
  guardarSesion('tok-viejo', { id: 1, rol: 'cliente' });
  let aviso = null;
  registrarAlExpirarSesion((m) => {
    aviso = m;
  });
  simularRespuesta(401, { detail: 'Tu sesión expiró. Inicia sesión de nuevo.' });
  await assert.rejects(api.misCitas(), (e) => e instanceof ApiError && e.status === 401);
  assert.equal(aviso, 'Tu sesión expiró. Inicia sesión de nuevo.');
  assert.equal(obtenerToken(), null);
  assert.equal(obtenerUsuarioGuardado(), null);
});

test('401 simultáneos o tardíos de una sesión anterior solo avisan una vez y no cierran la sesión nueva', async () => {
  reiniciar();
  guardarSesion('tok-viejo', { id: 1, rol: 'cliente' });
  const avisos = [];
  registrarAlExpirarSesion((m) => avisos.push(m));
  // Dos peticiones salen con el mismo token; la primera respuesta invalida la sesión local.
  let resolver = null;
  globalThis.fetch = async () =>
    new Promise((resolve) => {
      resolver = resolve;
    });
  const respuesta401 = (detail) => ({ ok: false, status: 401, text: async () => JSON.stringify({ detail }) });
  const p1 = api.servicios();
  const resolver1 = resolver;
  const p2 = api.barberos();
  const resolver2 = resolver;
  resolver1(respuesta401('Tu sesión expiró. Inicia sesión de nuevo.'));
  await assert.rejects(p1);
  resolver2(respuesta401('Sesión no válida. Inicia sesión.'));
  await assert.rejects(p2);
  assert.deepEqual(avisos, ['Tu sesión expiró. Inicia sesión de nuevo.']);

  // Una respuesta tardía del token viejo no debe cerrar una sesión iniciada después.
  guardarSesion('tok-viejo', { id: 1, rol: 'cliente' });
  const p3 = api.misCitas();
  const resolver3 = resolver;
  guardarSesion('tok-nuevo', { id: 1, rol: 'cliente' });
  resolver3(respuesta401('Sesión no válida. Inicia sesión.'));
  await assert.rejects(p3);
  assert.equal(avisos.length, 1);
  assert.equal(obtenerToken(), 'tok-nuevo');
});

test('401 en el login (credenciales incorrectas) no se trata como sesión expirada', async () => {
  reiniciar();
  let avisado = false;
  registrarAlExpirarSesion(() => {
    avisado = true;
  });
  simularRespuesta(401, { detail: 'La contraseña es incorrecta.' });
  await assert.rejects(api.login('a@b.co', 'mala'), (e) => e.status === 401 && e.message === 'La contraseña es incorrecta.');
  assert.equal(avisado, false);
});

test('403 por cuenta suspendida expone suspendido_hasta', async () => {
  reiniciar();
  simularRespuesta(403, { detail: 'Tu cuenta está suspendida hasta el 04/12/2026.', suspendido_hasta: '2026-12-04' });
  await assert.rejects(api.login('a@b.co', 'x'), (e) => e.status === 403 && e.suspendidoHasta === '2026-12-04' && /04\/12\/2026/.test(e.message));
});

test('logout con sesión ya inválida no dispara el aviso de expiración', async () => {
  reiniciar();
  guardarSesion('tok', { id: 1, rol: 'cliente' });
  let avisado = false;
  registrarAlExpirarSesion(() => {
    avisado = true;
  });
  simularRespuesta(401, { detail: 'Sesión no válida. Inicia sesión.' });
  await assert.rejects(api.logout());
  assert.equal(avisado, false);
});

test('sin conexión se lanza un ApiError con status 0 y mensaje claro', async () => {
  reiniciar();
  globalThis.fetch = async () => {
    throw new TypeError('Failed to fetch');
  };
  await assert.rejects(api.servicios(), (e) => e instanceof ApiError && e.status === 0 && /No se pudo conectar/.test(e.message));
});

test('respuesta no JSON en un error del servidor no rompe el manejo', async () => {
  reiniciar();
  simularRespuesta(500, 'Internal Server Error');
  await assert.rejects(api.servicios(), (e) => e.status === 500 && /error en el servidor/.test(e.message));
});
