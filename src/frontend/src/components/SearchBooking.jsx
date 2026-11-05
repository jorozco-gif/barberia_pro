import React, { useState, useEffect, useCallback } from 'react';
import { Search, Calendar, Clock, Scissors, User, Phone, Mail, Wallet, X, RefreshCw, MessageSquare } from 'lucide-react';
import { api } from '../api';
import { useAuth } from '../AuthContext';
import { ROLES } from '../roles';
import {
  ESTADOS_CITA,
  FRANJAS,
  TEXTOS_POLITICAS,
  claseEstado,
  formatearFecha,
  formatearHora,
  formatearPrecio,
  hoyColombia,
} from '../formato';
import Alerta from './Alerta';

const CLASE_CONTROL =
  'px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-white text-sm focus:border-amber-500 focus:outline-none';

// ---------------------------------------------------------------------------
// Tarjeta de cita (compartida por la vista del cliente y la del administrador)
// ---------------------------------------------------------------------------
function TarjetaCita({ cita, modo, children }) {
  const servicios = cita.servicios || [];
  const duracionTotal = servicios.reduce((suma, s) => suma + (s.duracion_minutos || 0), 0);

  return (
    <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 shadow-xl space-y-4 transition hover:border-slate-700">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 border-b border-slate-800 pb-4">
        <div>
          <span className="text-xs text-slate-500 font-mono">Código de Reserva</span>
          <h3 className="text-xl font-bold font-mono text-amber-400 whitespace-nowrap">{cita.codigo_reserva}</h3>
        </div>
        <div className="flex flex-wrap sm:justify-end gap-2">
          {cita.reprogramada && (
            <span className="px-3 py-1 rounded-full text-xs font-semibold bg-slate-800 text-slate-300 border border-slate-700">
              Reprogramada
            </span>
          )}
          <span className={`px-3 py-1 rounded-full text-xs font-semibold border ${claseEstado(cita.estado)}`}>
            {cita.estado}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
        <div>
          <span className="text-slate-400 flex items-center gap-1.5 mb-1">
            <Scissors className="w-3.5 h-3.5 text-amber-400" /> {servicios.length === 1 ? 'Servicio' : 'Servicios'}
          </span>
          <ul className="space-y-0.5">
            {servicios.map((s) => (
              <li key={s.id} className="font-semibold text-white text-sm">
                {s.servicio?.nombre || 'Servicio'}{' '}
                <span className="font-normal text-xs text-slate-400">
                  — {s.duracion_minutos} min, {formatearPrecio(s.precio_aplicado)}
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <span className="text-slate-400 flex items-center gap-1.5 mb-1">
            <User className="w-3.5 h-3.5 text-amber-400" /> Barbero
          </span>
          <p className="font-semibold text-white text-sm">{cita.barbero?.nombre || 'Barbero'}</p>
        </div>

        <div>
          <span className="text-slate-400 flex items-center gap-1.5 mb-1">
            <Calendar className="w-3.5 h-3.5 text-amber-400" /> Fecha
          </span>
          <p className="font-semibold text-white text-sm">{formatearFecha(cita.fecha)}</p>
        </div>

        <div>
          <span className="text-slate-400 flex items-center gap-1.5 mb-1">
            <Clock className="w-3.5 h-3.5 text-amber-400" /> Horario
          </span>
          <p className="font-semibold text-amber-400 text-sm">
            {formatearHora(cita.hora_inicio)} a {formatearHora(cita.hora_fin)}
            {duracionTotal > 0 && <span className="text-slate-400 font-normal text-xs"> ({duracionTotal} min)</span>}
          </p>
        </div>

        <div>
          <span className="text-slate-400 flex items-center gap-1.5 mb-1">
            <Wallet className="w-3.5 h-3.5 text-amber-400" /> Total
          </span>
          <p className="font-semibold text-emerald-400 text-sm">{formatearPrecio(cita.total)}</p>
        </div>

        {modo === 'admin' && cita.cliente && (
          <div>
            <span className="text-slate-400 flex items-center gap-1.5 mb-1">
              <User className="w-3.5 h-3.5 text-amber-400" /> Cliente
            </span>
            <p className="font-semibold text-white text-sm">{cita.cliente.nombre}</p>
            <p className="text-slate-400 flex items-center gap-1.5 mt-0.5">
              <Phone className="w-3 h-3" /> {cita.cliente.telefono}
            </p>
            <p className="text-slate-400 flex items-center gap-1.5">
              <Mail className="w-3 h-3" /> {cita.cliente.email}
            </p>
          </div>
        )}
      </div>

      {cita.notas && (
        <p className="text-xs text-slate-400/80 bg-slate-950/60 p-2 rounded-lg border border-slate-800/80 flex items-start gap-1.5">
          <MessageSquare className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
          <span>
            <span className="font-medium text-slate-300">Nota:</span> {cita.notas}
          </span>
        </p>
      )}

      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Reprogramación (RF-24): el cliente elige un nuevo horario libre del mismo barbero
// ---------------------------------------------------------------------------
function ReprogramarModal({ cita, onCerrar, onReprogramada }) {
  const [fecha, setFecha] = useState(cita.fecha);
  const [franja, setFranja] = useState('');
  const [slots, setSlots] = useState([]);
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [errorSlots, setErrorSlots] = useState('');
  const [recarga, setRecarga] = useState(0);
  const [slot, setSlot] = useState(null);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setSlot(null);
    setErrorSlots('');
    if (!fecha || !franja) {
      setSlots([]);
      return undefined;
    }
    let activo = true;
    setLoadingSlots(true);
    api
      .disponibilidadReprogramacion(cita.id, { fecha, franja })
      .then((data) => activo && setSlots(data.filter((s) => s.disponible)))
      .catch((err) => {
        if (!activo) return;
        setSlots([]);
        setErrorSlots(err.message);
      })
      .finally(() => activo && setLoadingSlots(false));
    return () => {
      activo = false;
    };
  }, [cita.id, fecha, franja, recarga]);

  const confirmar = async () => {
    setError('');
    setEnviando(true);
    try {
      const actualizada = await api.reprogramarCita(cita.id, { fecha, hora_inicio: slot.hora_inicio });
      onReprogramada(actualizada);
    } catch (err) {
      setError(err.message);
      if (err.status === 409) setRecarga((n) => n + 1); // el horario se ocupó: se actualiza la lista
      setEnviando(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="reprogramar-titulo"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm"
    >
      <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full max-h-[92vh] overflow-y-auto p-6 shadow-2xl">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 id="reprogramar-titulo" className="text-xl font-bold text-white">Reprogramar cita</h2>
            <p className="text-slate-400 text-xs mt-1">
              {cita.codigo_reserva} con {cita.barbero?.nombre} — actualmente {formatearFecha(cita.fecha)} a las{' '}
              {formatearHora(cita.hora_inicio)}
            </p>
          </div>
          <button onClick={onCerrar} className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 transition" title="Cerrar">
            <X className="w-5 h-5" />
          </button>
        </div>

        <p className="text-xs text-slate-400 mb-4">
          {TEXTOS_POLITICAS.anticipacion} {TEXTOS_POLITICAS.reprogramacion}
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
          <div>
            <label htmlFor="rep-fecha" className="block text-xs uppercase tracking-wider text-slate-400 font-semibold mb-2">
              Nueva fecha
            </label>
            <input
              id="rep-fecha"
              type="date"
              value={fecha}
              min={hoyColombia()}
              onChange={(e) => {
                setError('');
                setFecha(e.target.value);
              }}
              className={`w-full ${CLASE_CONTROL}`}
            />
          </div>
          <div>
            <span className="block text-xs uppercase tracking-wider text-slate-400 font-semibold mb-2">Franja</span>
            <div className="flex gap-2" role="group" aria-label="Franja del día">
              {FRANJAS.map((f) => (
                <button
                  type="button"
                  key={f}
                  onClick={() => setFranja(f)}
                  aria-pressed={franja === f}
                  className={`flex-1 px-2 py-2 rounded-xl border text-sm font-medium transition ${
                    franja === f
                      ? 'bg-amber-500 text-slate-950 font-bold border-amber-500'
                      : 'bg-slate-950 border-slate-800 text-slate-200 hover:border-slate-700'
                  }`}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>
        </div>

        <Alerta tipo="error" className="mb-4">{errorSlots}</Alerta>

        <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-4 mb-4">
          {!franja ? (
            <p className="py-4 text-center text-slate-500 text-sm">Elige una franja del día para ver los horarios.</p>
          ) : loadingSlots ? (
            <p className="py-4 text-center text-slate-400 text-sm">Consultando disponibilidad...</p>
          ) : slots.length === 0 ? (
            !errorSlots && (
              <p className="py-4 text-center text-slate-500 text-sm">
                No hay horarios disponibles en esa fecha y franja.
              </p>
            )
          ) : (
            <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
              {slots.map((s) => (
                <button
                  type="button"
                  key={s.hora_inicio}
                  onClick={() => {
                    setSlot(s);
                    setError('');
                  }}
                  aria-pressed={slot?.hora_inicio === s.hora_inicio}
                  className={`p-2 rounded-xl border text-center text-sm font-semibold transition ${
                    slot?.hora_inicio === s.hora_inicio
                      ? 'bg-amber-500 text-slate-950 border-amber-500'
                      : 'bg-slate-950 border-slate-800 text-slate-200 hover:border-slate-700'
                  }`}
                >
                  {formatearHora(s.hora_inicio)}
                </button>
              ))}
            </div>
          )}
        </div>

        <Alerta tipo="error" className="mb-4">{error}</Alerta>

        <div className="flex justify-end gap-2">
          <button
            onClick={onCerrar}
            className="px-5 py-2.5 border border-slate-700 hover:bg-slate-800 text-slate-300 font-medium rounded-xl transition"
          >
            Volver
          </button>
          <button
            disabled={!slot || enviando}
            onClick={confirmar}
            className="px-5 py-2.5 bg-amber-500 hover:bg-amber-400 disabled:opacity-40 disabled:hover:bg-amber-500 text-slate-950 font-bold rounded-xl transition"
          >
            {enviando ? 'Reprogramando...' : 'Confirmar nuevo horario'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Vista del cliente: Mis citas (RF-22, RF-23, RF-24)
// ---------------------------------------------------------------------------
function MisCitas({ onOperacionExitosa }) {
  const [citas, setCitas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [codigo, setCodigo] = useState('');
  const [confirmandoId, setConfirmandoId] = useState(null);
  const [procesandoId, setProcesandoId] = useState(null);
  const [errorAccion, setErrorAccion] = useState(null); // { id, mensaje }
  const [citaReprogramar, setCitaReprogramar] = useState(null);

  const cargar = useCallback(async ({ silencioso = false } = {}) => {
    if (!silencioso) setLoading(true);
    setError('');
    try {
      setCitas(await api.misCitas());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const cancelar = async (cita) => {
    setProcesandoId(cita.id);
    setErrorAccion(null);
    try {
      const actualizada = await api.cancelarCita(cita.id);
      setConfirmandoId(null);
      onOperacionExitosa('cancelada', actualizada);
      await cargar({ silencioso: true });
    } catch (err) {
      setConfirmandoId(null);
      setErrorAccion({ id: cita.id, mensaje: err.message });
      if (err.status !== 0) await cargar({ silencioso: true }); // el estado pudo cambiar en el servidor
    } finally {
      setProcesandoId(null);
    }
  };

  const filtro = codigo.trim().toUpperCase();
  const visibles = filtro ? citas.filter((c) => c.codigo_reserva.toUpperCase().includes(filtro)) : citas;
  const programadas = visibles
    .filter((c) => c.estado === 'Programada')
    .sort((a, b) => `${a.fecha} ${a.hora_inicio}`.localeCompare(`${b.fecha} ${b.hora_inicio}`));
  const historial = visibles.filter((c) => c.estado !== 'Programada');

  const renderAcciones = (cita) => {
    if (cita.estado !== 'Programada') return null;
    const mensaje = errorAccion?.id === cita.id ? errorAccion.mensaje : '';
    return (
      <div className="pt-3 border-t border-slate-800 space-y-3">
        <Alerta tipo="error">{mensaje}</Alerta>
        {confirmandoId === cita.id ? (
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <p className="text-sm text-slate-300">¿Seguro que deseas cancelar esta cita?</p>
            <div className="flex gap-2">
              <button
                onClick={() => setConfirmandoId(null)}
                className="px-4 py-2 rounded-lg border border-slate-700 hover:bg-slate-800 text-slate-300 text-sm transition"
              >
                No, conservar
              </button>
              <button
                disabled={procesandoId === cita.id}
                onClick={() => cancelar(cita)}
                className="px-4 py-2 rounded-lg bg-rose-500 hover:bg-rose-400 disabled:opacity-50 text-white text-sm font-semibold transition"
              >
                {procesandoId === cita.id ? 'Cancelando...' : 'Sí, cancelar cita'}
              </button>
            </div>
          </div>
        ) : (
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <p className="text-[11px] text-slate-500">
              {TEXTOS_POLITICAS.anticipacion}{' '}
              {cita.reprogramada ? 'Esta cita ya fue reprogramada una vez.' : TEXTOS_POLITICAS.reprogramacion}
            </p>
            <div className="flex gap-2 flex-shrink-0">
              {!cita.reprogramada && (
                <button
                  onClick={() => {
                    setErrorAccion(null);
                    setCitaReprogramar(cita);
                  }}
                  className="px-3 py-1.5 rounded-lg bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 border border-blue-500/30 text-xs font-medium flex items-center gap-1.5 transition"
                >
                  <RefreshCw className="w-3.5 h-3.5" /> Reprogramar
                </button>
              )}
              <button
                onClick={() => {
                  setErrorAccion(null);
                  setConfirmandoId(cita.id);
                }}
                className="px-3 py-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 text-xs font-medium flex items-center gap-1.5 transition"
              >
                <X className="w-3.5 h-3.5" /> Cancelar
              </button>
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold text-white flex items-center justify-center gap-2">
          <Search className="w-6 h-6 text-amber-400" />
          Mis Citas
        </h2>
        <p className="text-slate-400 text-sm mt-1">
          Consulta tus citas programadas y tu historial. Puedes buscar por código de reserva (ej. BSP-4CD0AA).
        </p>
      </div>

      <div className="mb-6">
        <input
          type="text"
          placeholder="Buscar por código: BSP-XXXXXX"
          aria-label="Buscar por código de reserva"
          value={codigo}
          onChange={(e) => setCodigo(e.target.value)}
          className="w-full px-4 py-3 bg-slate-900 border border-slate-800 rounded-xl text-white font-mono tracking-wider focus:border-amber-500 focus:outline-none uppercase"
        />
      </div>

      <Alerta tipo="error" className="mb-6">{error}</Alerta>

      {loading ? (
        <div className="py-16 text-center text-slate-400 text-sm">Cargando tus citas...</div>
      ) : citas.length === 0 && !error ? (
        <div className="py-16 text-center bg-slate-900/50 border border-slate-800/80 rounded-2xl">
          <Calendar className="w-10 h-10 text-slate-600 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-slate-300">Aún no tienes citas</h3>
          <p className="text-slate-500 text-xs mt-1">Cuando agendes una, aparecerá aquí.</p>
        </div>
      ) : visibles.length === 0 && !error ? (
        <div className="py-12 text-center text-slate-500 text-sm">No se encontró ninguna cita con ese código.</div>
      ) : (
        <div className="space-y-8">
          <section>
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-3">
              Programadas ({programadas.length})
            </h3>
            {programadas.length === 0 ? (
              <p className="text-slate-500 text-sm">No tienes citas programadas.</p>
            ) : (
              <div className="space-y-4">
                {programadas.map((c) => (
                  <TarjetaCita key={c.id} cita={c} modo="cliente">{renderAcciones(c)}</TarjetaCita>
                ))}
              </div>
            )}
          </section>

          <section>
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-3">
              Historial ({historial.length})
            </h3>
            {historial.length === 0 ? (
              <p className="text-slate-500 text-sm">Todavía no tienes citas en tu historial.</p>
            ) : (
              <div className="space-y-4">
                {historial.map((c) => (
                  <TarjetaCita key={c.id} cita={c} modo="cliente" />
                ))}
              </div>
            )}
          </section>
        </div>
      )}

      {citaReprogramar && (
        <ReprogramarModal
          cita={citaReprogramar}
          onCerrar={() => setCitaReprogramar(null)}
          onReprogramada={async (actualizada) => {
            setCitaReprogramar(null);
            onOperacionExitosa('reprogramada', actualizada);
            await cargar({ silencioso: true });
          }}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Vista del administrador: todas las citas con filtros (RF-28)
// ---------------------------------------------------------------------------
function CitasAdmin() {
  const [barberos, setBarberos] = useState([]);
  const [barberoId, setBarberoId] = useState('');
  const [fecha, setFecha] = useState('');
  const [estado, setEstado] = useState('');
  const [citas, setCitas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    api.adminBarberos().then(setBarberos).catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    let activo = true;
    setLoading(true);
    setError('');
    api
      .adminCitas({ barberoId, fecha, estado })
      .then((data) => activo && setCitas(data))
      .catch((err) => {
        if (!activo) return;
        setCitas([]);
        setError(err.message);
      })
      .finally(() => activo && setLoading(false));
    return () => {
      activo = false;
    };
  }, [barberoId, fecha, estado]);

  const hayFiltros = barberoId || fecha || estado;

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 mb-8">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            <Search className="w-6 h-6 text-amber-400" />
            Consulta de Citas
          </h2>
          <p className="text-slate-400 text-xs sm:text-sm mt-1">
            Todas las citas del sistema. Filtra por barbero, fecha o estado.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <select aria-label="Filtrar por barbero" value={barberoId} onChange={(e) => setBarberoId(e.target.value)} className={CLASE_CONTROL}>
            <option value="">Todos los barberos</option>
            {barberos.map((b) => (
              <option key={b.id} value={b.id}>
                {b.nombre}
                {b.activo ? '' : ' (inactivo)'}
              </option>
            ))}
          </select>
          <input type="date" aria-label="Filtrar por fecha" value={fecha} onChange={(e) => setFecha(e.target.value)} className={CLASE_CONTROL} />
          <select aria-label="Filtrar por estado" value={estado} onChange={(e) => setEstado(e.target.value)} className={CLASE_CONTROL}>
            <option value="">Todos los estados</option>
            {ESTADOS_CITA.map((e) => (
              <option key={e} value={e}>{e}</option>
            ))}
          </select>
          {hayFiltros && (
            <button
              onClick={() => {
                setBarberoId('');
                setFecha('');
                setEstado('');
              }}
              className="px-3 py-2 rounded-xl border border-slate-700 hover:bg-slate-800 text-slate-300 text-sm transition"
            >
              Limpiar filtros
            </button>
          )}
        </div>
      </div>

      <Alerta tipo="error" className="mb-6">{error}</Alerta>

      {loading ? (
        <div className="py-16 text-center text-slate-400 text-sm">Cargando citas...</div>
      ) : citas.length === 0 && !error ? (
        <div className="py-16 text-center bg-slate-900/50 border border-slate-800/80 rounded-2xl">
          <Calendar className="w-10 h-10 text-slate-600 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-slate-300">No hay citas</h3>
          <p className="text-slate-500 text-xs mt-1">
            {hayFiltros ? 'No hay citas que coincidan con los filtros seleccionados.' : 'Todavía no hay citas registradas.'}
          </p>
        </div>
      ) : (
        <>
          <p className="text-xs text-slate-500 mb-3">{citas.length} {citas.length === 1 ? 'cita' : 'citas'}</p>
          <div className="space-y-4">
            {citas.map((c) => (
              <TarjetaCita key={c.id} cita={c} modo="admin" />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Consulta de citas según el rol (el backend aplica el control de acceso real)
// ---------------------------------------------------------------------------
export default function SearchBooking({ onOperacionExitosa }) {
  const { rol } = useAuth();
  if (rol === ROLES.ADMIN) return <CitasAdmin />;
  return <MisCitas onOperacionExitosa={onOperacionExitosa} />;
}
