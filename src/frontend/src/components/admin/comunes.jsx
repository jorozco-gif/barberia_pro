import React from 'react';

// Estilos y piezas compartidas por las secciones del panel de administración.

export const CLASE_INPUT =
  'w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-white text-sm placeholder-slate-600 focus:border-amber-500 focus:outline-none';
export const CLASE_LABEL = 'block text-xs uppercase tracking-wider text-slate-400 font-semibold mb-1.5';
export const CLASE_BOTON_PRIMARIO =
  'px-4 py-2 bg-amber-500 hover:bg-amber-400 disabled:opacity-50 disabled:hover:bg-amber-500 text-slate-950 font-bold text-sm rounded-xl transition flex items-center justify-center gap-2';
export const CLASE_BOTON_SECUNDARIO =
  'px-4 py-2 border border-slate-700 hover:bg-slate-800 text-slate-300 text-sm rounded-xl transition';
export const CLASE_BOTON_EDITAR =
  'px-3 py-1.5 rounded-lg bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 border border-blue-500/30 text-xs font-medium flex items-center gap-1.5 transition';
export const CLASE_BOTON_ELIMINAR =
  'px-3 py-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 text-xs font-medium flex items-center gap-1.5 transition';

export function Campo({ id, etiqueta, ayuda, className = '', children }) {
  return (
    <div className={className}>
      <label htmlFor={id} className={CLASE_LABEL}>
        {etiqueta}
      </label>
      {children}
      {ayuda && <p className="text-[11px] text-slate-500 mt-1">{ayuda}</p>}
    </div>
  );
}

/** Confirmación en línea antes de una baja lógica. */
export function ConfirmarEliminacion({ texto, procesando, textoConfirmar, onCancelar, onConfirmar }) {
  return (
    <div className="flex flex-col sm:items-end gap-2 sm:max-w-sm">
      <p className="text-xs text-slate-300 sm:text-right">{texto}</p>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={onCancelar}
          className="px-3 py-1.5 rounded-lg border border-slate-700 hover:bg-slate-800 text-slate-300 text-xs transition"
        >
          No
        </button>
        <button
          type="button"
          disabled={procesando}
          onClick={onConfirmar}
          className="px-3 py-1.5 rounded-lg bg-rose-500 hover:bg-rose-400 disabled:opacity-50 text-white text-xs font-semibold transition"
        >
          {procesando ? 'Eliminando...' : textoConfirmar}
        </button>
      </div>
    </div>
  );
}
