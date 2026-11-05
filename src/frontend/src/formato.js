// Utilidades de presentación compartidas (fechas, horas, precios, estados de cita).
// RNF-05: las fechas y horas se manejan en la zona horaria de Colombia (UTC-5), no en la del navegador.

export const ZONA_HORARIA = 'America/Bogota';

// Debe coincidir con PN-02 (INTERVALO_MINUTOS en politicas.py). El backend valida y rechaza otros valores.
export const INTERVALO_MINUTOS = 30;

export const DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']; // 0 = lunes

// Valores aceptados por el parámetro `franja` del backend (PN-03).
export const FRANJAS = ['Mañana', 'Tarde', 'Noche'];

/** Fecha de hoy (YYYY-MM-DD) en Colombia. */
export function hoyColombia(ahora = new Date()) {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: ZONA_HORARIA,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(ahora);
}

/** Suma (o resta) días a una fecha YYYY-MM-DD sin depender de la zona horaria del navegador. */
export function sumarDias(fechaIso, dias) {
  const [a, m, d] = fechaIso.split('-').map(Number);
  return new Date(Date.UTC(a, m - 1, d + dias)).toISOString().slice(0, 10);
}

/** YYYY-MM-DD -> DD/MM/YYYY */
export function formatearFecha(fechaIso) {
  if (!fechaIso) return '';
  const [a, m, d] = String(fechaIso).slice(0, 10).split('-');
  return `${d}/${m}/${a}`;
}

/** YYYY-MM-DD -> "miércoles, 4 de noviembre de 2026" */
export function formatearFechaLarga(fechaIso) {
  if (!fechaIso) return '';
  const [a, m, d] = fechaIso.split('-').map(Number);
  const texto = new Date(Date.UTC(a, m - 1, d)).toLocaleDateString('es-CO', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  });
  return texto.charAt(0).toUpperCase() + texto.slice(1); // solo la primera letra en mayúscula
}

/** "HH:MM:SS" -> "HH:MM" */
export function formatearHora(hora) {
  return hora ? String(hora).slice(0, 5) : '';
}

/** El backend serializa los Decimal como texto ("20000.00"). */
export function formatearPrecio(valor) {
  const n = Number(valor);
  if (!Number.isFinite(n)) return '$0';
  return `$${n.toLocaleString('es-CO', { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;
}

/** Lista de opciones HH:MM cada INTERVALO_MINUTOS, de 00:00 a 23:30. */
export function opcionesDeHora() {
  const opciones = [];
  for (let min = 0; min < 24 * 60; min += INTERVALO_MINUTOS) {
    const h = String(Math.floor(min / 60)).padStart(2, '0');
    const m = String(min % 60).padStart(2, '0');
    opciones.push(`${h}:${m}`);
  }
  return opciones;
}

export const ESTADOS_CITA = ['Programada', 'Atendida', 'Cancelada', 'Inasistencia'];

/** Clases de la insignia de estado (Programada, Atendida, Cancelada, Inasistencia). */
export function claseEstado(estado) {
  switch (estado) {
    case 'Programada':
      return 'bg-blue-500/10 text-blue-400 border-blue-500/30';
    case 'Atendida':
      return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
    case 'Cancelada':
      return 'bg-rose-500/10 text-rose-400 border-rose-500/30';
    case 'Inasistencia':
      return 'bg-amber-500/10 text-amber-400 border-amber-500/30';
    default:
      return 'bg-slate-800 text-slate-400 border-slate-700';
  }
}

// Textos informativos de las políticas de negocio (PN-04, PN-05, PN-09, PN-11). Son solo avisos para el
// usuario: las reglas las valida y aplica el backend, que responde con el mensaje exacto cuando no se cumplen.
export const TEXTOS_POLITICAS = {
  anticipacion: 'Puedes cancelar o reprogramar tu cita hasta 12 horas antes de su hora de inicio.',
  reprogramacion: 'Cada cita se puede reprogramar una sola vez, con el mismo barbero.',
  limite: 'Puedes tener hasta 2 citas programadas a la vez.',
  pago: 'El pago se realiza en el local.',
};
