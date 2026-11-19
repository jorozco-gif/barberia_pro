import React from 'react';
import { TEXTOS_POLITICAS, formatearFecha, formatearHora, formatearPrecio } from '../../formato';
import FotoEstilo from '../FotoEstilo';
import { BotonAnterior, EncabezadoPaso } from './comunes';

// Paso 4 (v1.2, RF-19): resumen y confirmación. Ya no hay campo de notas: la personalización la da el estilo.
export default function PasoConfirmacion({ usuario, barbero, resumen, estilo, fecha, turno, enviando, onAnterior, onConfirmar }) {
  const enviar = (e) => {
    e.preventDefault();
    onConfirmar();
  };

  return (
    <div>
      <EncabezadoPaso titulo="Confirmar Reserva">Revisa el resumen y confirma tu cita.</EncabezadoPaso>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Resumen de la cita */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 h-fit">
          <h3 className="font-bold text-sm text-slate-300 uppercase tracking-wider mb-4 border-b border-slate-800 pb-2">
            Resumen de Reserva
          </h3>
          <div className="space-y-3 text-xs">
            <div>
              <span className="text-slate-400">Barbero:</span>
              <p className="font-semibold text-white text-sm mt-0.5">{barbero?.nombre}</p>
            </div>
            <div>
              <span className="text-slate-400">Servicios:</span>
              <ul className="mt-0.5 space-y-1">
                {(resumen?.servicios || []).map((s) => (
                  <li key={s.id} className="flex justify-between gap-2 text-white text-sm font-semibold">
                    <span>{s.nombre}</span>
                    <span className="text-slate-300 font-normal">{formatearPrecio(s.precio)}</span>
                  </li>
                ))}
              </ul>
            </div>
            {estilo && (
              <div>
                <span className="text-slate-400">Estilo:</span>
                <div className="flex items-center gap-2 mt-1">
                  <FotoEstilo fotoUrl={estilo.foto_url} className="w-8 h-8 rounded-lg border border-slate-700" />
                  <p className="font-semibold text-white text-sm">{estilo.nombre}</p>
                </div>
              </div>
            )}
            <div>
              <span className="text-slate-400">Fecha y Hora:</span>
              <p className="font-semibold text-amber-400 text-sm mt-0.5">
                {formatearFecha(fecha)} ({formatearHora(turno?.hora_inicio)} — {formatearHora(turno?.hora_fin)})
              </p>
            </div>
            <div>
              <span className="text-slate-400">Duración total:</span>
              <p className="font-semibold text-white text-sm mt-0.5">{resumen?.duracion_total_minutos} minutos</p>
            </div>
            <div className="pt-3 border-t border-slate-800 flex justify-between items-center text-sm">
              <span className="text-slate-400">Total a Pagar:</span>
              <span className="font-bold text-lg text-emerald-400">{formatearPrecio(resumen?.total)}</span>
            </div>
          </div>
        </div>

        {/* Confirmación */}
        <form onSubmit={enviar} className="md:col-span-2 bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4">
          <div className="text-sm text-slate-300 bg-slate-950/60 border border-slate-800 rounded-xl p-3">
            Reservando como <strong className="text-white">{usuario?.nombre}</strong>
            <span className="text-slate-400"> ({usuario?.email})</span>
          </div>

          <ul className="text-xs text-slate-400 space-y-1 list-disc pl-5">
            <li>{TEXTOS_POLITICAS.anticipacion}</li>
            <li>{TEXTOS_POLITICAS.reprogramacion}</li>
            <li>{TEXTOS_POLITICAS.limite}</li>
            <li>{TEXTOS_POLITICAS.pago}</li>
          </ul>

          <div className="pt-4 flex flex-wrap gap-3 justify-between items-center">
            <BotonAnterior onClick={onAnterior}>Modificar Horario</BotonAnterior>
            <button
              type="submit"
              disabled={enviando}
              className="px-8 py-3 bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-slate-950 font-bold rounded-xl transition shadow-lg shadow-amber-500/20 flex items-center gap-2"
            >
              {enviando ? 'Confirmando...' : 'Confirmar y Agendar'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
