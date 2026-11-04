import React, { useState } from 'react';
import { CheckCircle2, Copy, Check, Calendar, Clock, User, Scissors } from 'lucide-react';

export default function SuccessModal({ cita, onClose }) {
  const [copied, setCopied] = useState(false);

  if (!cita) return null;

  const handleCopy = () => {
    navigator.clipboard.writeText(cita.codigo_reserva);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-fade-in">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl relative">
        <div className="text-center mb-6">
          <div className="w-16 h-16 bg-emerald-500/10 border border-emerald-500/30 rounded-2xl flex items-center justify-center mx-auto text-emerald-400 mb-4">
            <CheckCircle2 className="w-8 h-8" />
          </div>
          <h2 className="text-2xl font-bold text-white">¡Cita Confirmada!</h2>
          <p className="text-slate-400 text-sm mt-1">
            Tu reserva ha sido registrada exitosamente en nuestro sistema.
          </p>
        </div>

        <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-4 mb-5 text-center">
          <span className="text-xs uppercase tracking-wider text-slate-500 font-medium">Código de Reserva</span>
          <div className="flex items-center justify-center gap-2 mt-1">
            <span className="text-2xl font-mono font-bold tracking-wider text-amber-400">
              {cita.codigo_reserva}
            </span>
            <button
              onClick={handleCopy}
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
              title="Copiar código"
            >
              {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
            </button>
          </div>
          <p className="text-[11px] text-slate-400 mt-2">
            Guarda este código para consultar o gestionar tu turno en cualquier momento.
          </p>
        </div>

        <div className="space-y-2.5 text-sm mb-6 bg-slate-800/40 p-4 rounded-xl border border-slate-800">
          <div className="flex items-center justify-between text-slate-300">
            <span className="flex items-center gap-2 text-slate-400 text-xs">
              <Scissors className="w-3.5 h-3.5" /> Servicio:
            </span>
            <span className="font-semibold text-white">{cita.servicio?.nombre || 'Servicio'}</span>
          </div>
          <div className="flex items-center justify-between text-slate-300">
            <span className="flex items-center gap-2 text-slate-400 text-xs">
              <User className="w-3.5 h-3.5" /> Barbero:
            </span>
            <span className="font-semibold text-white">{cita.barbero?.nombre || 'Barbero'}</span>
          </div>
          <div className="flex items-center justify-between text-slate-300">
            <span className="flex items-center gap-2 text-slate-400 text-xs">
              <Calendar className="w-3.5 h-3.5" /> Fecha:
            </span>
            <span className="font-semibold text-white">{cita.fecha}</span>
          </div>
          <div className="flex items-center justify-between text-slate-300">
            <span className="flex items-center gap-2 text-slate-400 text-xs">
              <Clock className="w-3.5 h-3.5" /> Horario:
            </span>
            <span className="font-semibold text-amber-400">
              {cita.hora_inicio?.slice(0, 5)} — {cita.hora_fin?.slice(0, 5)}
            </span>
          </div>
        </div>

        <button
          onClick={onClose}
          className="w-full py-3 bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold rounded-xl transition shadow-lg shadow-amber-500/20"
        >
          Entendido / Agendar Otra Cita
        </button>
      </div>
    </div>
  );
}
