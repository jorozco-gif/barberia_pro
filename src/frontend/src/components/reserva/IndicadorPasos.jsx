import React from 'react';
import { User, Scissors, Calendar as CalendarIcon, Check } from 'lucide-react';
import { PASOS } from '../../reservaEstado';

const ICONOS = { barbero: User, servicios: Scissors, fechaHora: CalendarIcon, confirmacion: Check };

// Stepper de la reserva (v1.2): Barbero -> Servicios -> Fecha y Hora -> Confirmación.
// Los pasos ya completados se pueden pulsar para volver a ellos y cambiar la elección.
export default function IndicadorPasos({ paso, onIrAPaso }) {
  return (
    <nav aria-label="Pasos de la reserva" className="mb-8">
      <ol className="flex items-center justify-between relative">
        <div className="absolute left-0 top-5 -translate-y-1/2 h-0.5 w-full bg-slate-800" aria-hidden="true" />
        {PASOS.map((item) => {
          const Icono = ICONOS[item.id];
          const hecho = paso > item.num;
          const actual = paso === item.num;
          const circulo = (
            <span
              className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-sm transition ${
                actual
                  ? 'bg-amber-500 text-slate-950 ring-4 ring-amber-500/20'
                  : hecho
                  ? 'bg-emerald-500 text-white'
                  : 'bg-slate-800 text-slate-400 border border-slate-700'
              }`}
            >
              {hecho ? <Check className="w-5 h-5" /> : <Icono className="w-4 h-4" />}
            </span>
          );
          const etiqueta = (
            <span className={`text-xs mt-2 font-medium ${actual ? 'text-amber-400' : 'text-slate-400'}`}>
              {item.etiqueta}
            </span>
          );
          return (
            <li key={item.num} className="relative z-10" aria-current={actual ? 'step' : undefined}>
              {hecho ? (
                <button
                  type="button"
                  onClick={() => onIrAPaso(item.num)}
                  className="flex flex-col items-center rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
                  title={`Volver a ${item.etiqueta}`}
                >
                  {circulo}
                  {etiqueta}
                </button>
              ) : (
                <div className="flex flex-col items-center">
                  {circulo}
                  {etiqueta}
                </div>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
