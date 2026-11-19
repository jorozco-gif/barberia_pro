import React from 'react';
import { Check } from 'lucide-react';
import { BotonSiguiente, Cargando, EncabezadoPaso, Vacio, claseTarjeta } from './comunes';

// Paso 1 (v1.2): el cliente elige primero al barbero (RF-13).
export default function PasoBarbero({ barberos, cargando, barberoId, onElegir, onSiguiente }) {
  return (
    <div>
      <EncabezadoPaso titulo="Selecciona a tu Barbero">Elige con quién quieres atenderte.</EncabezadoPaso>

      {cargando ? (
        <Cargando>Cargando barberos...</Cargando>
      ) : barberos.length === 0 ? (
        <Vacio>No hay barberos disponibles por el momento.</Vacio>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
          {barberos.map((b) => {
            const elegido = barberoId === b.id;
            return (
              <button
                type="button"
                key={b.id}
                onClick={() => onElegir(b)}
                aria-pressed={elegido}
                className={`p-5 rounded-2xl border cursor-pointer transition text-center flex flex-col justify-between ${claseTarjeta(elegido)}`}
              >
                <div>
                  {b.foto_url ? (
                    <img
                      src={b.foto_url}
                      alt={b.nombre}
                      className="w-16 h-16 rounded-2xl object-cover border border-slate-700 mx-auto mb-3"
                    />
                  ) : (
                    <div className="w-16 h-16 rounded-2xl bg-slate-800 border border-slate-700 mx-auto flex items-center justify-center text-amber-400 font-bold text-xl mb-3">
                      {b.nombre[0]}
                    </div>
                  )}
                  <h3 className="font-bold text-base text-white">{b.nombre}</h3>
                </div>
                <div className="mt-4 pt-3 border-t border-slate-800 w-full">
                  <span
                    className={`text-xs font-semibold inline-flex items-center gap-1 ${elegido ? 'text-amber-400' : 'text-slate-500'}`}
                  >
                    {elegido ? (
                      <>
                        Seleccionado <Check className="w-3.5 h-3.5" />
                      </>
                    ) : (
                      'Seleccionar'
                    )}
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      )}

      <div className="mt-8 flex justify-end">
        <BotonSiguiente disabled={!barberoId} onClick={onSiguiente}>
          Siguiente: Servicios
        </BotonSiguiente>
      </div>
    </div>
  );
}
