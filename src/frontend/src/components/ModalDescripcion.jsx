import React, { useEffect, useId, useRef, useState } from 'react';
import { X } from 'lucide-react';

// Ventana flotante con la descripción de un servicio o de un estilo (v1.2, RF-14 y RF-34).
// Se cierra con el botón X, con la tecla Escape o haciendo clic fuera del recuadro. Mientras está abierta,
// el foco queda dentro del modal y, al cerrarse, vuelve al botón que la abrió.
export default function ModalDescripcion({ titulo, subtitulo, descripcion, imagenUrl, onCerrar }) {
  const idTitulo = useId();
  const idDescripcion = useId();
  const panel = useRef(null);
  const botonCerrar = useRef(null);
  const [imagenFallo, setImagenFallo] = useState(false);

  useEffect(() => {
    const anterior = document.activeElement;
    const overflowAnterior = document.body.style.overflow;
    const paddingAnterior = document.body.style.paddingRight;
    const anchoBarra = window.innerWidth - document.documentElement.clientWidth;
    document.body.style.overflow = 'hidden'; // la página de fondo no se desplaza
    if (anchoBarra > 0) document.body.style.paddingRight = `${anchoBarra}px`; // sin salto al ocultar la barra
    botonCerrar.current?.focus();

    const alPresionar = (e) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onCerrar();
        return;
      }
      if (e.key !== 'Tab' || !panel.current) return;
      const enfocables = panel.current.querySelectorAll('button, [href], [tabindex]:not([tabindex="-1"])');
      if (enfocables.length === 0) return;
      const primero = enfocables[0];
      const ultimo = enfocables[enfocables.length - 1];
      if (e.shiftKey && document.activeElement === primero) {
        e.preventDefault();
        ultimo.focus();
      } else if (!e.shiftKey && document.activeElement === ultimo) {
        e.preventDefault();
        primero.focus();
      }
    };
    document.addEventListener('keydown', alPresionar);
    return () => {
      document.removeEventListener('keydown', alPresionar);
      document.body.style.overflow = overflowAnterior;
      document.body.style.paddingRight = paddingAnterior;
      if (anterior && typeof anterior.focus === 'function') anterior.focus();
    };
  }, [onCerrar]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onCerrar(); // clic en el fondo, fuera del recuadro
      }}
    >
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={idTitulo}
        aria-describedby={idDescripcion}
        className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full max-h-[85vh] overflow-y-auto shadow-2xl relative"
      >
        {imagenUrl && !imagenFallo && (
          <img
            src={imagenUrl}
            alt={titulo}
            onError={() => setImagenFallo(true)}
            className="w-full h-48 object-cover rounded-t-2xl border-b border-slate-800"
          />
        )}
        <button
          ref={botonCerrar}
          type="button"
          onClick={onCerrar}
          aria-label="Cerrar"
          title="Cerrar"
          className="absolute top-3 right-3 p-1.5 rounded-lg bg-slate-900/80 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-700 transition"
        >
          <X className="w-5 h-5" />
        </button>
        <div className="p-6">
          {subtitulo && (
            <span className="text-[11px] uppercase tracking-wider text-amber-400 font-semibold">{subtitulo}</span>
          )}
          <h2 id={idTitulo} className="text-xl font-bold text-white pr-10 mt-0.5">
            {titulo}
          </h2>
          <p id={idDescripcion} className="text-sm text-slate-300 mt-3 leading-relaxed whitespace-pre-line">
            {descripcion}
          </p>
        </div>
      </div>
    </div>
  );
}
