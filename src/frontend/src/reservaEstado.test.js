// Pruebas del estado de la reserva en curso (v1.2): orden del asistente, estilo elegido (RF-34, PN-14),
// descarte del turno cuando cambia otra elección y sincronización con el catálogo.
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  ACCIONES,
  PASOS,
  PASO_BARBERO,
  PASO_CONFIRMACION,
  PASO_FECHA_HORA,
  PASO_SERVICIOS,
  crearEstadoInicial,
  cuerpoDeCita,
  faltaEstilo,
  pasoCompleto,
  pasoMaximo,
  reservaReducer,
  sincronizarConCatalogo,
} from './reservaEstado.js';

const HOY = '2026-11-18';
const BARBERO = { id: 1, nombre: 'Carlos', foto_url: null };
const OTRO_BARBERO = { id: 2, nombre: 'Andrés', foto_url: null };
const TURNO = { hora_inicio: '10:00:00', hora_fin: '10:30:00' };
const ESTILOS = [{ id: 7, nombre: 'Fade bajo' }, { id: 8, nombre: 'Pompadour' }];

function aplicar(estado, ...acciones) {
  return acciones.reduce(reservaReducer, estado);
}

function reservaCompleta() {
  return aplicar(
    crearEstadoInicial(HOY),
    { type: ACCIONES.ELEGIR_BARBERO, barbero: BARBERO },
    { type: ACCIONES.ALTERNAR_SERVICIO, id: 3 },
    { type: ACCIONES.ELEGIR_ESTILO, id: 7 },
    { type: ACCIONES.ELEGIR_TURNO, turno: TURNO },
  );
}

test('el asistente sigue el orden Barbero, Servicios, Fecha y Hora, Confirmación', () => {
  assert.deepEqual(
    PASOS.map((p) => p.etiqueta),
    ['Barbero', 'Servicios', 'Fecha y Hora', 'Confirmación'],
  );
  assert.deepEqual([PASO_BARBERO, PASO_SERVICIOS, PASO_FECHA_HORA, PASO_CONFIRMACION], [1, 2, 3, 4]);
});

test('el estado inicial empieza en el barbero, sin estilo y con la fecha de mañana', () => {
  const estado = crearEstadoInicial(HOY);
  assert.equal(estado.paso, PASO_BARBERO);
  assert.equal(estado.barbero, null);
  assert.deepEqual(estado.serviciosIds, []);
  assert.equal(estado.estiloId, null);
  assert.equal(estado.fecha, '2026-11-19');
  assert.equal(estado.turno, null);
  assert.equal('notas' in estado, false); // v1.2: las notas se reemplazan por el estilo
});

test('los servicios se alternan en el orden de elección y descartan el turno', () => {
  let estado = aplicar(crearEstadoInicial(HOY), { type: ACCIONES.ALTERNAR_SERVICIO, id: 5 });
  estado = aplicar(estado, { type: ACCIONES.ALTERNAR_SERVICIO, id: 2 }, { type: ACCIONES.ELEGIR_TURNO, turno: TURNO });
  assert.deepEqual(estado.serviciosIds, [5, 2]);
  estado = aplicar(estado, { type: ACCIONES.ALTERNAR_SERVICIO, id: 5 });
  assert.deepEqual(estado.serviciosIds, [2]);
  assert.equal(estado.turno, null); // cambió la duración total
});

test('el estilo elegido se guarda por su id y se puede cambiar', () => {
  let estado = aplicar(crearEstadoInicial(HOY), { type: ACCIONES.ELEGIR_ESTILO, id: 7 });
  assert.equal(estado.estiloId, 7);
  estado = aplicar(estado, { type: ACCIONES.ELEGIR_ESTILO, id: 8 });
  assert.equal(estado.estiloId, 8);
  estado = aplicar(estado, { type: ACCIONES.ELEGIR_ESTILO, id: undefined });
  assert.equal(estado.estiloId, null);
});

test('cambiar de barbero o de fecha descarta el turno; repetir la misma elección lo conserva', () => {
  const base = reservaCompleta();
  assert.deepEqual(aplicar(base, { type: ACCIONES.ELEGIR_BARBERO, barbero: BARBERO }).turno, TURNO);
  assert.equal(aplicar(base, { type: ACCIONES.ELEGIR_BARBERO, barbero: OTRO_BARBERO }).turno, null);
  assert.equal(aplicar(base, { type: ACCIONES.ELEGIR_FECHA, fecha: base.fecha }), base);
  assert.equal(aplicar(base, { type: ACCIONES.ELEGIR_FECHA, fecha: '2026-11-25' }).turno, null);
  // El estilo y los servicios no dependen del barbero ni de la fecha
  const otro = aplicar(base, { type: ACCIONES.ELEGIR_BARBERO, barbero: OTRO_BARBERO });
  assert.equal(otro.estiloId, 7);
  assert.deepEqual(otro.serviciosIds, [3]);
});

test('al volver a consultar los turnos del día se conserva el elegido solo si sigue libre', () => {
  const base = reservaCompleta();
  const libres = [TURNO, { hora_inicio: '10:30:00', hora_fin: '11:00:00' }];
  assert.equal(aplicar(base, { type: ACCIONES.SINCRONIZAR_TURNOS, libres }), base);
  const sinElTurno = aplicar(base, { type: ACCIONES.SINCRONIZAR_TURNOS, libres: libres.slice(1) });
  assert.equal(sinElTurno.turno, null);
  assert.equal(aplicar(base, { type: ACCIONES.DESCARTAR_TURNO }).turno, null);
});

test('PN-14: el estilo es obligatorio solo si hay estilos activos', () => {
  const sinEstilo = aplicar(reservaCompleta(), { type: ACCIONES.ELEGIR_ESTILO, id: null });
  assert.equal(faltaEstilo(sinEstilo, ESTILOS), true);
  assert.equal(faltaEstilo(sinEstilo, []), false);
  assert.equal(pasoCompleto(sinEstilo, PASO_SERVICIOS, { estilos: ESTILOS }), false);
  assert.equal(pasoCompleto(sinEstilo, PASO_SERVICIOS, { estilos: [] }), true);
  assert.equal(pasoCompleto(reservaCompleta(), PASO_SERVICIOS, { estilos: ESTILOS }), true);
});

test('pasoMaximo devuelve el primer paso pendiente', () => {
  const opciones = { estilos: ESTILOS };
  const inicial = crearEstadoInicial(HOY);
  assert.equal(pasoMaximo(inicial, opciones), PASO_BARBERO);
  const conBarbero = aplicar(inicial, { type: ACCIONES.ELEGIR_BARBERO, barbero: BARBERO });
  assert.equal(pasoMaximo(conBarbero, opciones), PASO_SERVICIOS);
  const conServicio = aplicar(conBarbero, { type: ACCIONES.ALTERNAR_SERVICIO, id: 3 });
  assert.equal(pasoMaximo(conServicio, opciones), PASO_SERVICIOS); // falta el estilo
  const conEstilo = aplicar(conServicio, { type: ACCIONES.ELEGIR_ESTILO, id: 7 });
  assert.equal(pasoMaximo(conEstilo, opciones), PASO_FECHA_HORA);
  assert.equal(pasoMaximo(reservaCompleta(), opciones), PASO_CONFIRMACION);
});

test('IR_A_PASO se limita a los pasos existentes', () => {
  const estado = crearEstadoInicial(HOY);
  assert.equal(aplicar(estado, { type: ACCIONES.IR_A_PASO, paso: 3 }).paso, 3);
  assert.equal(aplicar(estado, { type: ACCIONES.IR_A_PASO, paso: 9 }).paso, PASO_CONFIRMACION);
  assert.equal(aplicar(estado, { type: ACCIONES.IR_A_PASO, paso: 0 }).paso, PASO_BARBERO);
});

test('el catálogo vigente descarta barbero, servicios y estilo retirados', () => {
  const base = aplicar(
    reservaCompleta(),
    { type: ACCIONES.ALTERNAR_SERVICIO, id: 4 },
    { type: ACCIONES.ELEGIR_TURNO, turno: TURNO },
  );
  const catalogo = { barberos: [BARBERO], servicios: [{ id: 3 }, { id: 4 }], estilos: ESTILOS };
  assert.equal(sincronizarConCatalogo(base, catalogo), base); // nada cambió

  const sinServicio = sincronizarConCatalogo(base, { ...catalogo, servicios: [{ id: 4 }] });
  assert.deepEqual(sinServicio.serviciosIds, [4]);
  assert.equal(sinServicio.turno, null);

  const sinEstilo = sincronizarConCatalogo(base, { ...catalogo, estilos: [ESTILOS[1]] });
  assert.equal(sinEstilo.estiloId, null);
  assert.deepEqual(sinEstilo.turno, TURNO);

  const sinBarbero = sincronizarConCatalogo(base, { ...catalogo, barberos: [OTRO_BARBERO] });
  assert.equal(sinBarbero.barbero, null);
  assert.equal(sinBarbero.turno, null);

  const renombrado = sincronizarConCatalogo(base, { ...catalogo, barberos: [{ ...BARBERO, nombre: 'Carlos R.' }] });
  assert.equal(renombrado.barbero.nombre, 'Carlos R.');
  assert.deepEqual(renombrado.turno, TURNO);
});

test('cuerpoDeCita arma el CitaCreate v1.2 con estilo_id y sin notas', () => {
  const estado = reservaCompleta();
  assert.deepEqual(cuerpoDeCita(estado), {
    barbero_id: 1,
    servicios_ids: [3],
    estilo_id: 7,
    fecha: '2026-11-19',
    hora_inicio: '10:00:00',
  });
  const sinEstilo = cuerpoDeCita(aplicar(estado, { type: ACCIONES.ELEGIR_ESTILO, id: null }));
  assert.equal(sinEstilo.estilo_id, null);
});

test('REINICIAR deja la reserva como al principio', () => {
  const estado = aplicar(reservaCompleta(), { type: ACCIONES.IR_A_PASO, paso: 4 }, { type: ACCIONES.REINICIAR, hoy: HOY });
  assert.deepEqual(estado, crearEstadoInicial(HOY));
});

test('una acción desconocida no cambia el estado', () => {
  const estado = reservaCompleta();
  assert.equal(reservaReducer(estado, { type: 'OTRA' }), estado);
});
