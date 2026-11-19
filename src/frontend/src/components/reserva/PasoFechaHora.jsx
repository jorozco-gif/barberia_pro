import React from 'react';
import { Clock, RefreshCw } from 'lucide-react';
import { INTERVALO_MINUTOS, formatearFecha, formatearHora, hoyColombia } from '../../formato';
import Alerta from '../Alerta';
import { BotonAnterior, BotonSiguiente, EncabezadoPaso } from './comunes';

// Paso 3 (v1.2, RF-16 y RF-17): al elegir la fecha se muestran de una vez todos los turnos libres del día,
// sin pedir antes una franja (Mañana, Tarde o Noche).
export default function PasoFechaHora({
  barbero,
  fecha,
  duracionTotal,
  turnos,
  cargando,
  error,
  turno,
  onCambiarFecha,
  onElegirTurno,
  onReintentar,
  onAnterior,
  onSiguiente,
}) {
  return (
    <div>
      <EncabezadoPaso titulo="Fecha y Horario">
        Los turnos se consultan en vivo según la duración total de tus servicios ({duracionTotal} min) y se ofrecen
        cada {INTERVALO_MINUTOS} minutos.
      </EncabezadoPaso>

      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 mb-6">
        <label htmlFor="cita-fecha" className="block text-xs uppercase tracking-wider text-slate-400 font-semibold mb-2">
          Seleccionar Fecha
        </label>
        <input
          id="cita-fecha"
          type="date"
          value={fecha}
          min={hoyColombia()}
          onChange={(e) => onCambiarFecha(e.target.value)}
          className="w-full sm:w-64 px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-white font-medium focus:border-amber-500 focus:outline-none"
        />
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
          <h3 className="font-semibold text-sm text-slate-300 flex items-center gap-2">
            <Clock className="w-4 h-4 text-amber-400" />
            Turnos disponibles con {barbero?.nombre} {fecha ? `el ${formatearFecha(fecha)}` : ''}
          </h3>
          {!cargando && fecha && !error && (
            <span className="text-xs text-slate-500" aria-live="polite">
              {turnos.length} {turnos.length === 1 ? 'turno libre' : 'turnos libres'}
            </span>
          )}
        </div>

        {error && (
          <Alerta tipo="error" className="mb-4">
            <p>{error}</p>
            <button
              type="button"
              onClick={onReintentar}
              className="mt-2 inline-flex items-center gap-1.5 underline underline-offset-2 hover:text-rose-200 transition"
            >
              <RefreshCw className="w-3.5 h-3.5" /> Reintentar
            </button>
          </Alerta>
        )}

        {!fecha ? (
          <div className="py-8 text-center text-slate-500 text-sm">Elige una fecha para ver los turnos disponibles.</div>
        ) : cargando ? (
          <div className="py-8 text-center text-slate-400 text-sm">Consultando disponibilidad en tiempo real...</div>
        ) : turnos.length === 0 ? (
          !error && (
            <div className="py-8 text-center text-slate-500 text-sm">
              No hay turnos disponibles para esta fecha. Prueba con otro día.
            </div>
          )
        ) : (
          <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-3" role="group" aria-label="Turnos disponibles">
            {turnos.map((s) => {
              const elegido = turno?.hora_inicio === s.hora_inicio;
              return (
                <button
                  type="button"
                  key={s.hora_inicio}
                  onClick={() => onElegirTurno({ hora_inicio: s.hora_inicio, hora_fin: s.hora_fin })}
                  aria-pressed={elegido}
                  className={`p-3 rounded-xl border text-center transition flex flex-col items-center justify-center ${
                    elegido
                      ? 'bg-amber-500 text-slate-950 font-bold border-amber-500 shadow-md shadow-amber-500/20'
                      : 'bg-slate-950 border-slate-800 text-slate-200 hover:border-slate-700'
                  }`}
                >
                  <span className="text-sm font-semibold">{formatearHora(s.hora_inicio)}</span>
                  <span className="text-[10px] opacity-70">a {formatearHora(s.hora_fin)}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>

      <div className="mt-8 flex justify-between">
        <BotonAnterior onClick={onAnterior}>Volver a Servicios</BotonAnterior>
        <BotonSiguiente disabled={!turno} onClick={onSiguiente}>
          Siguiente: Confirmar
        </BotonSiguiente>
      </div>
    </div>
  );
}
