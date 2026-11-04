import React from 'react';
import { AlertCircle, CheckCircle2, Info } from 'lucide-react';

// Mensaje en línea reutilizable (errores del backend, confirmaciones y avisos). Reemplaza los bloques
// de alerta que cada componente repetía con el mismo estilo.
const ESTILOS = {
  error: { caja: 'bg-rose-500/10 border-rose-500/30 text-rose-300', Icono: AlertCircle },
  exito: { caja: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300', Icono: CheckCircle2 },
  aviso: { caja: 'bg-amber-500/10 border-amber-500/30 text-amber-300', Icono: AlertCircle },
  info: { caja: 'bg-blue-500/10 border-blue-500/30 text-blue-300', Icono: Info },
};

export default function Alerta({ tipo = 'error', titulo, children, className = '' }) {
  if (!children && !titulo) return null;
  const { caja, Icono } = ESTILOS[tipo] || ESTILOS.error;
  return (
    <div role={tipo === 'error' ? 'alert' : 'status'} className={`p-4 rounded-xl border flex items-start gap-3 ${caja} ${className}`}>
      <Icono className="w-5 h-5 flex-shrink-0 mt-0.5" />
      <div className="text-sm">
        {titulo && <p className="font-semibold">{titulo}</p>}
        {children && <div className={titulo ? 'mt-0.5' : ''}>{children}</div>}
      </div>
    </div>
  );
}
