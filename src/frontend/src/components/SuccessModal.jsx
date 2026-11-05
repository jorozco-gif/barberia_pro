import React, { useState } from 'react';
import { CheckCircle2, XCircle, Copy, Check, Calendar, Clock, User, Scissors, Wallet, Mail } from 'lucide-react';
import { claseEstado, formatearFecha, formatearHora, formatearPrecio, TEXTOS_POLITICAS } from '../formato';

// Mensajes según la operación realizada. La información mostrada sale de la CitaResponse real del backend.
const TEXTOS = {
  agendada: {
    titulo: '¡Cita Confirmada!',
    subtitulo: 'Tu cita fue registrada correctamente con estado Programada.',
    boton: 'Entendido',
  },
  reprogramada: {
    titulo: 'Cita Reprogramada',
    subtitulo: 'Tu cita fue movida al nuevo horario y el anterior quedó libre.',
    boton: 'Entendido',
  },
  cancelada: {
    titulo: 'Cita Cancelada',
    subtitulo: 'Tu cita fue cancelada y el horario quedó libre para otros clientes.',
    boton: 'Entendido',
  },
};

export default function SuccessModal({ cita, tipo = 'agendada', onClose }) {
  const [copied, setCopied] = useState(false);

  if (!cita) return null;

  const textos = TEXTOS[tipo] || TEXTOS.agendada;
  const cancelada = tipo === 'cancelada';
  const servicios = cita.servicios || [];
  const duracionTotal = servicios.reduce((suma, s) => suma + (s.duracion_minutos || 0), 0);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(cita.codigo_reserva);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      setCopied(false); // el portapapeles puede no estar disponible (p. ej. sin HTTPS)
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-resultado-titulo"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-fade-in"
    >
      <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full max-h-[92vh] overflow-y-auto p-6 shadow-2xl relative">
        <div className="text-center mb-6">
          <div
            className={`w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4 border ${
              cancelada
                ? 'bg-rose-500/10 border-rose-500/30 text-rose-400'
                : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
            }`}
          >
            {cancelada ? <XCircle className="w-8 h-8" /> : <CheckCircle2 className="w-8 h-8" />}
          </div>
          <h2 id="modal-resultado-titulo" className="text-2xl font-bold text-white">{textos.titulo}</h2>
          <p className="text-slate-400 text-sm mt-1">{textos.subtitulo}</p>
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
          <span className={`inline-block mt-3 text-[11px] font-semibold px-2.5 py-0.5 rounded-full border ${claseEstado(cita.estado)}`}>
            {cita.estado}
          </span>
        </div>

        <div className="space-y-2.5 text-sm mb-5 bg-slate-800/40 p-4 rounded-xl border border-slate-800">
          <div className="flex items-start justify-between gap-3 text-slate-300">
            <span className="flex items-center gap-2 text-slate-400 text-xs pt-0.5">
              <Scissors className="w-3.5 h-3.5" /> {servicios.length === 1 ? 'Servicio:' : 'Servicios:'}
            </span>
            <ul className="text-right space-y-0.5">
              {servicios.map((s) => (
                <li key={s.id} className="font-semibold text-white">
                  {s.servicio?.nombre || 'Servicio'}{' '}
                  <span className="font-normal text-slate-400 text-xs">({formatearPrecio(s.precio_aplicado)})</span>
                </li>
              ))}
            </ul>
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
            <span className="font-semibold text-white">{formatearFecha(cita.fecha)}</span>
          </div>
          <div className="flex items-center justify-between text-slate-300">
            <span className="flex items-center gap-2 text-slate-400 text-xs">
              <Clock className="w-3.5 h-3.5" /> Horario:
            </span>
            <span className="font-semibold text-amber-400">
              {formatearHora(cita.hora_inicio)} — {formatearHora(cita.hora_fin)}
              {duracionTotal > 0 && <span className="text-slate-400 font-normal text-xs"> ({duracionTotal} min)</span>}
            </span>
          </div>
          <div className="flex items-center justify-between text-slate-300 pt-2 border-t border-slate-800">
            <span className="flex items-center gap-2 text-slate-400 text-xs">
              <Wallet className="w-3.5 h-3.5" /> Total:
            </span>
            <span className="font-bold text-emerald-400 text-base">{formatearPrecio(cita.total)}</span>
          </div>
        </div>

        {tipo === 'agendada' && (
          <div className="text-[11px] text-slate-400 space-y-1.5 mb-5">
            {cita.cliente?.email && (
              <p className="flex items-start gap-1.5">
                <Mail className="w-3.5 h-3.5 mt-0.5 flex-shrink-0 text-slate-500" />
                La confirmación de la cita se envía a {cita.cliente.email}.
              </p>
            )}
            <p>{TEXTOS_POLITICAS.anticipacion} Puedes gestionarla desde Mis Citas.</p>
            <p>{TEXTOS_POLITICAS.pago}</p>
          </div>
        )}
        {tipo === 'reprogramada' && (
          <p className="text-[11px] text-slate-400 mb-5">
            Esta cita ya fue reprogramada: no admite otra reprogramación. Si no puedes asistir, aún puedes cancelarla
            con la anticipación indicada.
          </p>
        )}

        <button
          onClick={onClose}
          className="w-full py-3 bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold rounded-xl transition shadow-lg shadow-amber-500/20"
        >
          {textos.boton}
        </button>
      </div>
    </div>
  );
}
