// Estado de la reserva en curso del cliente (v1.2): reducer y selectores puros, sin React, para poder
// probarlos con `node --test`. BookingContext.jsx los expone a los componentes del asistente.
//
// Orden del asistente (v1.2): Barbero -> Servicios y estilo -> Fecha y hora -> Confirmación.
// Las reglas (horario libre, límite de citas, estilo obligatorio con catálogo, PN-14) las valida el backend;
// aquí solo se guarda lo que eligió el cliente y se descarta lo que deja de ser válido al cambiar otra elección.

import { hoyColombia, sumarDias } from './formato.js';

export const PASOS = [
  { num: 1, id: 'barbero', etiqueta: 'Barbero' },
  { num: 2, id: 'servicios', etiqueta: 'Servicios' },
  { num: 3, id: 'fechaHora', etiqueta: 'Fecha y Hora' },
  { num: 4, id: 'confirmacion', etiqueta: 'Confirmación' },
];

export const PASO_BARBERO = 1;
export const PASO_SERVICIOS = 2;
export const PASO_FECHA_HORA = 3;
export const PASO_CONFIRMACION = 4;

/** Estado inicial: por defecto la fecha es mañana (hora de Colombia, RNF-05). */
export function crearEstadoInicial(hoy = hoyColombia()) {
  return {
    paso: PASO_BARBERO,
    barbero: null, // { id, nombre, foto_url } (BarberoPublico)
    serviciosIds: [], // en el orden en que se eligieron (RF-14)
    estiloId: null, // v1.2 (RF-34): id del estilo elegido; null si aún no elige o si el catálogo está vacío
    fecha: sumarDias(hoy, 1),
    turno: null, // { hora_inicio, hora_fin } elegido de la lista de turnos libres del día
  };
}

export const ACCIONES = {
  ELEGIR_BARBERO: 'ELEGIR_BARBERO',
  ALTERNAR_SERVICIO: 'ALTERNAR_SERVICIO',
  ELEGIR_ESTILO: 'ELEGIR_ESTILO',
  ELEGIR_FECHA: 'ELEGIR_FECHA',
  ELEGIR_TURNO: 'ELEGIR_TURNO',
  DESCARTAR_TURNO: 'DESCARTAR_TURNO',
  SINCRONIZAR_TURNOS: 'SINCRONIZAR_TURNOS',
  SINCRONIZAR_CATALOGO: 'SINCRONIZAR_CATALOGO',
  IR_A_PASO: 'IR_A_PASO',
  REINICIAR: 'REINICIAR',
};

export function reservaReducer(estado, accion) {
  switch (accion.type) {
    case ACCIONES.ELEGIR_BARBERO: {
      const mismo = estado.barbero?.id === accion.barbero?.id;
      // El turno elegido era de la agenda de otro barbero: se descarta
      return { ...estado, barbero: accion.barbero, turno: mismo ? estado.turno : null };
    }
    case ACCIONES.ALTERNAR_SERVICIO: {
      const { id } = accion;
      const serviciosIds = estado.serviciosIds.includes(id)
        ? estado.serviciosIds.filter((x) => x !== id)
        : [...estado.serviciosIds, id];
      // Cambia la duración total, así que el turno elegido puede dejar de alcanzar (RF-18)
      return { ...estado, serviciosIds, turno: null };
    }
    case ACCIONES.ELEGIR_ESTILO:
      return { ...estado, estiloId: accion.id ?? null };
    case ACCIONES.ELEGIR_FECHA:
      return estado.fecha === accion.fecha ? estado : { ...estado, fecha: accion.fecha, turno: null };
    case ACCIONES.ELEGIR_TURNO:
      return { ...estado, turno: accion.turno };
    case ACCIONES.DESCARTAR_TURNO:
      return estado.turno ? { ...estado, turno: null } : estado;
    case ACCIONES.SINCRONIZAR_TURNOS: {
      // Al volver a consultar los turnos del día se conserva el elegido solo si sigue libre
      const { turno } = estado;
      if (!turno) return estado;
      const sigueLibre = (accion.libres || []).some(
        (s) => s.hora_inicio === turno.hora_inicio && s.hora_fin === turno.hora_fin,
      );
      return sigueLibre ? estado : { ...estado, turno: null };
    }
    case ACCIONES.SINCRONIZAR_CATALOGO:
      return sincronizarConCatalogo(estado, accion.catalogo);
    case ACCIONES.IR_A_PASO:
      return { ...estado, paso: Math.min(Math.max(accion.paso, PASO_BARBERO), PASO_CONFIRMACION) };
    case ACCIONES.REINICIAR:
      return crearEstadoInicial(accion.hoy);
    default:
      return estado;
  }
}

/**
 * Descarta las elecciones que ya no están en el catálogo vigente (un barbero dado de baja, un servicio o un
 * estilo eliminados por el administrador mientras el cliente reservaba). Devuelve el mismo objeto si nada cambia.
 */
export function sincronizarConCatalogo(estado, { barberos, servicios, estilos } = {}) {
  let siguiente = estado;
  const cambiar = (cambios) => {
    siguiente = { ...siguiente, ...cambios };
  };
  if (barberos && siguiente.barbero) {
    const vigente = barberos.find((b) => b.id === siguiente.barbero.id);
    if (!vigente) {
      cambiar({ barbero: null, turno: null });
    } else if (vigente.nombre !== siguiente.barbero.nombre || vigente.foto_url !== siguiente.barbero.foto_url) {
      cambiar({ barbero: vigente }); // el administrador cambió su nombre o su foto mientras se reservaba
    }
  }
  if (servicios) {
    const vigentes = siguiente.serviciosIds.filter((id) => servicios.some((s) => s.id === id));
    if (vigentes.length !== siguiente.serviciosIds.length) cambiar({ serviciosIds: vigentes, turno: null });
  }
  if (estilos && siguiente.estiloId !== null && !estilos.some((e) => e.id === siguiente.estiloId)) {
    cambiar({ estiloId: null });
  }
  return siguiente;
}

// ---------------------------------------------------------------------------
// Selectores
// ---------------------------------------------------------------------------

/** PN-14: el estilo es obligatorio solo si el catálogo tiene estilos activos. */
export function faltaEstilo(estado, estilos) {
  return Array.isArray(estilos) && estilos.length > 0 && estado.estiloId === null;
}

/** ¿El paso indicado tiene todo lo necesario para pasar al siguiente? */
export function pasoCompleto(estado, paso, { estilos = [] } = {}) {
  switch (paso) {
    case PASO_BARBERO:
      return estado.barbero !== null;
    case PASO_SERVICIOS:
      return estado.serviciosIds.length > 0 && !faltaEstilo(estado, estilos);
    case PASO_FECHA_HORA:
      return Boolean(estado.fecha) && estado.turno !== null;
    default:
      return false;
  }
}

/** Primer paso incompleto (o la confirmación si todo está listo). Se usa para no saltar pasos. */
export function pasoMaximo(estado, opciones) {
  for (const { num } of PASOS.slice(0, -1)) {
    if (!pasoCompleto(estado, num, opciones)) return num;
  }
  return PASO_CONFIRMACION;
}

/** Cuerpo de POST /api/citas (CitaCreate v1.2: sin notas, con estilo_id). */
export function cuerpoDeCita(estado) {
  return {
    barbero_id: estado.barbero?.id,
    servicios_ids: estado.serviciosIds,
    estilo_id: estado.estiloId,
    fecha: estado.fecha,
    hora_inicio: estado.turno?.hora_inicio,
  };
}
