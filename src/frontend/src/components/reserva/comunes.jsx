import React from 'react';
import { ArrowLeft, ArrowRight } from 'lucide-react';

// Piezas compartidas por los pasos del asistente de reserva (v1.2).

export function EncabezadoPaso({ titulo, children }) {
  return (
    <div className="text-center mb-6">
      <h2 className="text-2xl font-bold text-white">{titulo}</h2>
      {children && <p className="text-slate-400 text-sm mt-1">{children}</p>}
    </div>
  );
}

export function BotonAnterior({ onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="px-5 py-3 border border-slate-700 hover:bg-slate-800 text-slate-300 font-medium rounded-xl transition flex items-center gap-2"
    >
      <ArrowLeft className="w-4 h-4" /> {children}
    </button>
  );
}

export function BotonSiguiente({ onClick, disabled, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="px-6 py-3 bg-amber-500 hover:bg-amber-400 disabled:opacity-40 disabled:hover:bg-amber-500 text-slate-950 font-bold rounded-xl transition flex items-center gap-2"
    >
      {children} <ArrowRight className="w-4 h-4" />
    </button>
  );
}

/** Clases de una tarjeta elegible (barbero, servicio, estilo) según esté elegida o no. */
export function claseTarjeta(elegida) {
  return elegida
    ? 'bg-amber-500/10 border-amber-500 shadow-lg shadow-amber-500/10'
    : 'bg-slate-900 border-slate-800 hover:border-slate-700';
}

export function Cargando({ children }) {
  return <div className="py-12 text-center text-slate-400 text-sm">{children}</div>;
}

export function Vacio({ children }) {
  return <div className="py-12 text-center text-slate-500 text-sm">{children}</div>;
}
