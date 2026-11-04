import React, { useState, useEffect, useCallback } from 'react';
import {
  Calendar,
  Clock,
  Scissors,
  CheckCircle,
  XCircle,
  UserX,
  Phone,
  Mail,
  Trash2,
  Plus,
  ChevronLeft,
  ChevronRight,
  Ban,
  MessageSquare,
} from 'lucide-react';
import { api } from '../api';
import {
  DIAS_SEMANA,
  INTERVALO_MINUTOS,
  claseEstado,
  formatearFecha,
  formatearFechaLarga,
  formatearHora,
  formatearPrecio,
  hoyColombia,
  opcionesDeHora,
  sumarDias,
} from '../formato';
import Alerta from './Alerta';

const CLASE_CONTROL =
  'px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-white text-sm focus:border-amber-500 focus:outline-none';
const CLASE_BOTON_PRIMARIO =
  'px-4 py-2 bg-amber-500 hover:bg-amber-400 disabled:opacity-50 disabled:hover:bg-amber-500 text-slate-950 font-bold text-sm rounded-xl transition flex items-center justify-center gap-2';

// Acciones de estado disponibles para el barbero (RF-27). El backend aplica PN-06 (solo desde la hora
// de inicio) y la regla de estados terminales, y responde 400 con el motivo si no corresponde.
const ACCIONES_ESTADO = [
  {
    estado: 'Atendida',
    etiqueta: 'Atendida',
    Icono: CheckCircle,
    clase: 'bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    confirmar: false,
  },
  {
    estado: 'Inasistencia',
    etiqueta: 'Inasistencia',
    Icono: UserX,
    clase: 'bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border-amber-500/30',
    confirmar: '¿Registrar que el cliente no asistió? Dos inasistencias en tres meses suspenden su cuenta.',
  },
  {
    estado: 'Cancelada',
    etiqueta: 'Cancelar',
    Icono: XCircle,
    clase: 'bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border-rose-500/30',
    confirmar: '¿Cancelar esta cita? Se notificará al cliente.',
  },
];

// ---------------------------------------------------------------------------
// Agenda por día o semana (RF-26) y cambio de estado (RF-27)
// ---------------------------------------------------------------------------
function PanelAgenda() {
  const [fecha, setFecha] = useState(() => hoyColombia());
  const [vista, setVista] = useState('dia');
  const [citas, setCitas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionError, setActionError] = useState('');
  const [pendiente, setPendiente] = useState(null); // { id, estado } esperando confirmación
  const [procesandoId, setProcesandoId] = useState(null);

  const cargar = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setCitas(await api.agenda({ fecha, vista }));
    } catch (err) {
      setCitas([]);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [fecha, vista]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const cambiarEstado = async (cita, estado) => {
    setActionError('');
    setProcesandoId(cita.id);
    try {
      await api.cambiarEstadoCita(cita.id, estado);
      setPendiente(null);
      await cargar();
    } catch (err) {
      setPendiente(null);
      setActionError(`${cita.codigo_reserva}: ${err.message}`);
      if (err.status !== 0) await cargar();
    } finally {
      setProcesandoId(null);
    }
  };

  const mover = (direccion) => setFecha((f) => sumarDias(f, direccion * (vista === 'semana' ? 7 : 1)));

  // Agrupa por fecha conservando el orden cronológico que entrega el backend.
  const grupos = [];
  citas.forEach((c) => {
    const ultimo = grupos[grupos.length - 1];
    if (ultimo && ultimo.fecha === c.fecha) ultimo.citas.push(c);
    else grupos.push({ fecha: c.fecha, citas: [c] });
  });

  return (
    <div>
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 mb-6">
        <p className="text-slate-400 text-xs sm:text-sm">
          Tus citas con los datos del cliente y los servicios. Los estados se pueden marcar desde la hora de inicio de la cita.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex rounded-xl overflow-hidden border border-slate-800" role="group" aria-label="Vista de la agenda">
            {[
              { id: 'dia', etiqueta: 'Día' },
              { id: 'semana', etiqueta: 'Semana' },
            ].map((v) => (
              <button
                key={v.id}
                onClick={() => setVista(v.id)}
                aria-pressed={vista === v.id}
                className={`px-4 py-2 text-sm font-medium transition ${
                  vista === v.id ? 'bg-amber-500 text-slate-950 font-semibold' : 'bg-slate-900 text-slate-300 hover:bg-slate-800'
                }`}
              >
                {v.etiqueta}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-1">
            <button onClick={() => mover(-1)} className="p-2 rounded-lg hover:bg-slate-800 text-slate-300 transition" title="Anterior">
              <ChevronLeft className="w-4 h-4" />
            </button>
            <input type="date" aria-label="Fecha de la agenda" value={fecha} onChange={(e) => e.target.value && setFecha(e.target.value)} className={CLASE_CONTROL} />
            <button onClick={() => mover(1)} className="p-2 rounded-lg hover:bg-slate-800 text-slate-300 transition" title="Siguiente">
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
          <button
            onClick={() => setFecha(hoyColombia())}
            className="px-3 py-2 rounded-xl border border-slate-700 hover:bg-slate-800 text-slate-300 text-sm transition"
          >
            Hoy
          </button>
        </div>
      </div>

      <Alerta tipo="error" className="mb-6">{error}</Alerta>
      <Alerta tipo="error" className="mb-6">{actionError}</Alerta>

      {loading ? (
        <div className="py-16 text-center text-slate-400 text-sm">Cargando agenda...</div>
      ) : citas.length === 0 ? (
        !error && (
          <div className="py-16 text-center bg-slate-900/50 border border-slate-800/80 rounded-2xl">
            <Calendar className="w-10 h-10 text-slate-600 mx-auto mb-3" />
            <h3 className="text-base font-semibold text-slate-300">No hay citas registradas</h3>
            <p className="text-slate-500 text-xs mt-1">
              {vista === 'semana' ? 'Para la semana de la fecha seleccionada.' : 'Para la fecha seleccionada.'}
            </p>
          </div>
        )
      ) : (
        <div className="space-y-6">
          {grupos.map((g) => (
            <section key={g.fecha}>
              <h3 className="text-sm font-semibold text-slate-300 mb-3">{formatearFechaLarga(g.fecha)}</h3>
              <div className="space-y-3">
                {g.citas.map((cita) => {
                  const accionPendiente = pendiente?.id === cita.id ? ACCIONES_ESTADO.find((a) => a.estado === pendiente.estado) : null;
                  return (
                    <div
                      key={cita.id}
                      className="p-5 rounded-2xl bg-slate-900 border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4 transition hover:border-slate-700"
                    >
                      <div className="flex items-start gap-4">
                        <div className="w-14 h-14 rounded-xl bg-slate-950 border border-slate-800 flex flex-col items-center justify-center text-center flex-shrink-0">
                          <span className="text-amber-400 font-bold text-sm">{formatearHora(cita.hora_inicio)}</span>
                          <span className="text-[10px] text-slate-500">{formatearHora(cita.hora_fin)}</span>
                        </div>

                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="font-bold text-white text-base">{cita.cliente?.nombre || 'Cliente'}</h3>
                            <span className="text-xs font-mono font-medium text-slate-500">#{cita.codigo_reserva}</span>
                            <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full border ${claseEstado(cita.estado)}`}>
                              {cita.estado}
                            </span>
                            {cita.reprogramada && (
                              <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full border bg-slate-800 text-slate-300 border-slate-700">
                                Reprogramada
                              </span>
                            )}
                          </div>

                          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-xs text-slate-400">
                            <span className="flex items-center gap-1.5">
                              <Scissors className="w-3.5 h-3.5 text-amber-400" />
                              {(cita.servicios || []).map((s) => s.servicio?.nombre || 'Servicio').join(', ')}
                            </span>
                            <span className="flex items-center gap-1.5">
                              <Phone className="w-3.5 h-3.5 text-slate-400" />
                              {cita.cliente?.telefono}
                            </span>
                            <span className="flex items-center gap-1.5">
                              <Mail className="w-3.5 h-3.5 text-slate-400" />
                              {cita.cliente?.email}
                            </span>
                            <span className="font-semibold text-emerald-400">{formatearPrecio(cita.total)}</span>
                          </div>

                          {cita.notas && (
                            <p className="text-xs text-slate-400/80 bg-slate-950/60 p-2 rounded-lg mt-2 border border-slate-800/80 flex items-start gap-1.5">
                              <MessageSquare className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
                              <span>
                                <span className="font-medium text-slate-300">Nota:</span> {cita.notas}
                              </span>
                            </p>
                          )}
                        </div>
                      </div>

                      {/* Acciones de estado */}
                      {cita.estado === 'Programada' && (
                        <div className="flex flex-col items-stretch md:items-end gap-2 pt-3 md:pt-0 border-t md:border-t-0 border-slate-800 flex-shrink-0 md:max-w-xs">
                          {accionPendiente ? (
                            <>
                              <p className="text-xs text-slate-300 md:text-right">{accionPendiente.confirmar}</p>
                              <div className="flex gap-2 md:justify-end">
                                <button
                                  onClick={() => setPendiente(null)}
                                  className="px-3 py-1.5 rounded-lg border border-slate-700 hover:bg-slate-800 text-slate-300 text-xs transition"
                                >
                                  No
                                </button>
                                <button
                                  disabled={procesandoId === cita.id}
                                  onClick={() => cambiarEstado(cita, accionPendiente.estado)}
                                  className={`px-3 py-1.5 rounded-lg border text-xs font-semibold disabled:opacity-50 transition ${accionPendiente.clase}`}
                                >
                                  {procesandoId === cita.id ? 'Guardando...' : 'Sí, confirmar'}
                                </button>
                              </div>
                            </>
                          ) : (
                            <div className="flex flex-wrap items-center gap-2 md:justify-end">
                              {ACCIONES_ESTADO.map(({ estado, etiqueta, Icono, clase, confirmar }) => (
                                <button
                                  key={estado}
                                  disabled={procesandoId === cita.id}
                                  onClick={() => (confirmar ? setPendiente({ id: cita.id, estado }) : cambiarEstado(cita, estado))}
                                  className={`px-3 py-1.5 rounded-lg border text-xs font-medium flex items-center gap-1.5 transition disabled:opacity-50 ${clase}`}
                                >
                                  <Icono className="w-3.5 h-3.5" /> {etiqueta}
                                </button>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Horarios disponibles por día de la semana (RF-11)
// ---------------------------------------------------------------------------
function PanelDisponibilidad() {
  const horas = opcionesDeHora();
  const [rangos, setRangos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [form, setForm] = useState({ dia_semana: 0, hora_inicio: '08:00', hora_fin: '12:00' });
  const [enviando, setEnviando] = useState(false);

  const cargar = useCallback(async () => {
    try {
      setRangos(await api.listarDisponibilidad());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const agregar = async (e) => {
    e.preventDefault();
    setError('');
    setEnviando(true);
    try {
      await api.agregarDisponibilidad({ ...form, dia_semana: Number(form.dia_semana) });
      await cargar();
    } catch (err) {
      setError(err.message);
    } finally {
      setEnviando(false);
    }
  };

  const eliminar = async (id) => {
    setError('');
    try {
      await api.eliminarDisponibilidad(id);
      await cargar();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div>
      <p className="text-slate-400 text-xs sm:text-sm mb-6">
        Define en qué horarios atiendes cada día de la semana. Los clientes verán estos espacios en intervalos de{' '}
        {INTERVALO_MINUTOS} minutos.
      </p>

      <form onSubmit={agregar} className="bg-slate-900 border border-slate-800 rounded-2xl p-5 mb-6 grid grid-cols-1 sm:grid-cols-4 gap-4 items-end">
        <div>
          <label htmlFor="disp-dia" className="block text-xs uppercase tracking-wider text-slate-400 font-semibold mb-1.5">Día</label>
          <select id="disp-dia" value={form.dia_semana} onChange={(e) => setForm({ ...form, dia_semana: e.target.value })} className={`w-full ${CLASE_CONTROL}`}>
            {DIAS_SEMANA.map((d, i) => (
              <option key={d} value={i}>{d}</option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="disp-inicio" className="block text-xs uppercase tracking-wider text-slate-400 font-semibold mb-1.5">Desde</label>
          <select id="disp-inicio" value={form.hora_inicio} onChange={(e) => setForm({ ...form, hora_inicio: e.target.value })} className={`w-full ${CLASE_CONTROL}`}>
            {horas.map((h) => (
              <option key={h} value={h}>{h}</option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="disp-fin" className="block text-xs uppercase tracking-wider text-slate-400 font-semibold mb-1.5">Hasta</label>
          <select id="disp-fin" value={form.hora_fin} onChange={(e) => setForm({ ...form, hora_fin: e.target.value })} className={`w-full ${CLASE_CONTROL}`}>
            {horas.map((h) => (
              <option key={h} value={h}>{h}</option>
            ))}
          </select>
        </div>
        <button type="submit" disabled={enviando} className={CLASE_BOTON_PRIMARIO}>
          <Plus className="w-4 h-4" /> {enviando ? 'Agregando...' : 'Agregar horario'}
        </button>
      </form>

      <Alerta tipo="error" className="mb-6">{error}</Alerta>

      {loading ? (
        <div className="py-12 text-center text-slate-400 text-sm">Cargando horarios...</div>
      ) : rangos.length === 0 ? (
        <div className="py-12 text-center bg-slate-900/50 border border-slate-800/80 rounded-2xl">
          <Clock className="w-10 h-10 text-slate-600 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-slate-300">Aún no definiste horarios</h3>
          <p className="text-slate-500 text-xs mt-1">Sin horarios, los clientes no podrán agendar contigo.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {DIAS_SEMANA.map((dia, i) => {
            const delDia = rangos.filter((r) => r.dia_semana === i);
            if (delDia.length === 0) return null;
            return (
              <div key={dia} className="p-4 rounded-2xl bg-slate-900 border border-slate-800">
                <h3 className="text-sm font-semibold text-white mb-2">{dia}</h3>
                <div className="flex flex-wrap gap-2">
                  {delDia.map((r) => (
                    <span key={r.id} className="inline-flex items-center gap-2 pl-3 pr-1.5 py-1 rounded-lg bg-slate-950 border border-slate-800 text-sm text-amber-400 font-medium">
                      {formatearHora(r.hora_inicio)} — {formatearHora(r.hora_fin)}
                      <button onClick={() => eliminar(r.id)} className="p-1 rounded hover:bg-rose-500/10 text-slate-400 hover:text-rose-400 transition" title="Eliminar horario">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </span>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Bloqueos de días u horas (RF-12)
// ---------------------------------------------------------------------------
function PanelBloqueos() {
  const horas = opcionesDeHora();
  const [bloqueos, setBloqueos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [fecha, setFecha] = useState(() => sumarDias(hoyColombia(), 1));
  const [diaCompleto, setDiaCompleto] = useState(true);
  const [horaInicio, setHoraInicio] = useState('08:00');
  const [horaFin, setHoraFin] = useState('12:00');
  const [enviando, setEnviando] = useState(false);

  const cargar = useCallback(async () => {
    try {
      setBloqueos(await api.listarBloqueos());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const agregar = async (e) => {
    e.preventDefault();
    setError('');
    setEnviando(true);
    try {
      await api.agregarBloqueo(diaCompleto ? { fecha } : { fecha, hora_inicio: horaInicio, hora_fin: horaFin });
      await cargar();
    } catch (err) {
      setError(err.message);
    } finally {
      setEnviando(false);
    }
  };

  const eliminar = async (id) => {
    setError('');
    try {
      await api.eliminarBloqueo(id);
      await cargar();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div>
      <p className="text-slate-400 text-xs sm:text-sm mb-6">
        Bloquea días u horas en los que no podrás atender. No se pueden bloquear horarios que ya tienen citas programadas.
      </p>

      <form onSubmit={agregar} className="bg-slate-900 border border-slate-800 rounded-2xl p-5 mb-6 space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 items-end">
          <div>
            <label htmlFor="blq-fecha" className="block text-xs uppercase tracking-wider text-slate-400 font-semibold mb-1.5">Fecha</label>
            <input id="blq-fecha" type="date" required min={hoyColombia()} value={fecha} onChange={(e) => setFecha(e.target.value)} className={`w-full ${CLASE_CONTROL}`} />
          </div>
          {!diaCompleto && (
            <>
              <div>
                <label htmlFor="blq-inicio" className="block text-xs uppercase tracking-wider text-slate-400 font-semibold mb-1.5">Desde</label>
                <select id="blq-inicio" value={horaInicio} onChange={(e) => setHoraInicio(e.target.value)} className={`w-full ${CLASE_CONTROL}`}>
                  {horas.map((h) => (
                    <option key={h} value={h}>{h}</option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor="blq-fin" className="block text-xs uppercase tracking-wider text-slate-400 font-semibold mb-1.5">Hasta</label>
                <select id="blq-fin" value={horaFin} onChange={(e) => setHoraFin(e.target.value)} className={`w-full ${CLASE_CONTROL}`}>
                  {horas.map((h) => (
                    <option key={h} value={h}>{h}</option>
                  ))}
                </select>
              </div>
            </>
          )}
          <button type="submit" disabled={enviando} className={`${CLASE_BOTON_PRIMARIO} ${diaCompleto ? 'sm:col-start-4' : ''}`}>
            <Ban className="w-4 h-4" /> {enviando ? 'Bloqueando...' : 'Bloquear'}
          </button>
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
          <input type="checkbox" checked={diaCompleto} onChange={(e) => setDiaCompleto(e.target.checked)} className="accent-amber-500" />
          Bloquear el día completo
        </label>
      </form>

      <Alerta tipo="error" className="mb-6">{error}</Alerta>

      {loading ? (
        <div className="py-12 text-center text-slate-400 text-sm">Cargando bloqueos...</div>
      ) : bloqueos.length === 0 ? (
        <div className="py-12 text-center bg-slate-900/50 border border-slate-800/80 rounded-2xl">
          <Ban className="w-10 h-10 text-slate-600 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-slate-300">No tienes bloqueos próximos</h3>
        </div>
      ) : (
        <div className="space-y-2">
          {bloqueos.map((b) => (
            <div key={b.id} className="flex items-center justify-between gap-3 p-4 rounded-2xl bg-slate-900 border border-slate-800">
              <div>
                <p className="text-sm font-semibold text-white">{formatearFechaLarga(b.fecha)}</p>
                <p className="text-xs text-amber-400">
                  {b.hora_inicio ? `${formatearHora(b.hora_inicio)} — ${formatearHora(b.hora_fin)}` : 'Día completo'}
                  <span className="text-slate-500"> · {formatearFecha(b.fecha)}</span>
                </p>
              </div>
              <button onClick={() => eliminar(b.id)} className="p-2 rounded-lg hover:bg-rose-500/10 text-slate-400 hover:text-rose-400 transition" title="Quitar bloqueo">
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Panel del barbero
// ---------------------------------------------------------------------------
const SECCIONES = [
  { id: 'agenda', etiqueta: 'Agenda', Icono: Calendar },
  { id: 'disponibilidad', etiqueta: 'Mis horarios', Icono: Clock },
  { id: 'bloqueos', etiqueta: 'Bloqueos', Icono: Ban },
];

export default function BarberAgenda() {
  const [seccion, setSeccion] = useState('agenda');

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-white flex items-center gap-2">
          <Calendar className="w-6 h-6 text-amber-400" />
          Mi Agenda
        </h2>
        <div className="flex gap-1 sm:gap-2 mt-4 border-b border-slate-800">
          {SECCIONES.map(({ id, etiqueta, Icono }) => (
            <button
              key={id}
              onClick={() => setSeccion(id)}
              className={`px-3 sm:px-4 py-2 text-sm font-medium flex items-center gap-2 border-b-2 -mb-px transition ${
                seccion === id ? 'border-amber-500 text-amber-400' : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <Icono className="w-4 h-4" /> {etiqueta}
            </button>
          ))}
        </div>
      </div>

      {seccion === 'agenda' && <PanelAgenda />}
      {seccion === 'disponibilidad' && <PanelDisponibilidad />}
      {seccion === 'bloqueos' && <PanelBloqueos />}
    </div>
  );
}
