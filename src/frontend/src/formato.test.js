import test from 'node:test';
import assert from 'node:assert/strict';
import { hoyColombia, sumarDias, formatearFecha, formatearFechaLarga, formatearHora, formatearPrecio, opcionesDeHora, claseEstado } from './formato.js';
import { ROLES, pestanasDeRol, pestanaInicial, puedeVerPestana } from './roles.js';

test('hoyColombia usa UTC-5 y no la fecha UTC', () => {
  // 2026-11-05 02:30 UTC = 2026-11-04 21:30 en Colombia
  assert.equal(hoyColombia(new Date('2026-11-05T02:30:00Z')), '2026-11-04');
  assert.equal(hoyColombia(new Date('2026-11-05T05:00:00Z')), '2026-11-05');
});

test('sumarDias cruza meses y años', () => {
  assert.equal(sumarDias('2026-12-31', 1), '2027-01-01');
  assert.equal(sumarDias('2026-03-01', -1), '2026-02-28');
  assert.equal(sumarDias('2026-11-04', 7), '2026-11-11');
});

test('formatos de fecha, hora y precio', () => {
  assert.equal(formatearFecha('2026-11-04'), '04/11/2026');
  assert.equal(formatearHora('10:30:00'), '10:30');
  assert.equal(formatearPrecio('30000.00'), '$30.000');
  assert.equal(formatearPrecio('20000.50'), '$20.000,5');
});

test('opcionesDeHora genera intervalos de 30 minutos de 00:00 a 23:30', () => {
  const o = opcionesDeHora();
  assert.equal(o.length, 48);
  assert.equal(o[0], '00:00');
  assert.equal(o[1], '00:30');
  assert.equal(o[47], '23:30');
});

test('claseEstado cubre los cuatro estados del backend', () => {
  for (const e of ['Programada', 'Atendida', 'Cancelada', 'Inasistencia']) assert.notEqual(claseEstado(e), claseEstado('otro'));
});

test('roles: pestañas visibles según el rol del backend', () => {
  assert.deepEqual(pestanasDeRol(ROLES.CLIENTE), ['booking', 'search']);
  assert.deepEqual(pestanasDeRol(ROLES.BARBERO), ['agenda']);
  assert.deepEqual(pestanasDeRol(ROLES.ADMIN), ['search', 'admin']);
  assert.deepEqual(pestanasDeRol('desconocido'), []);
  assert.equal(pestanaInicial(ROLES.CLIENTE), 'booking');
  assert.equal(puedeVerPestana(ROLES.CLIENTE, 'admin'), false);
  assert.equal(puedeVerPestana(ROLES.BARBERO, 'booking'), false);
  assert.equal(puedeVerPestana(ROLES.ADMIN, 'admin'), true);
  assert.equal(ROLES.ADMIN, 'administrador');
});

test('formatearFechaLarga: solo la primera letra en mayúscula y sin desfase de zona horaria', () => {
  assert.equal(formatearFechaLarga('2026-11-05'), 'Jueves, 5 de noviembre de 2026');
});
