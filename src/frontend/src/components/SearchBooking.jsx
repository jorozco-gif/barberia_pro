import React, { useState } from 'react';
import { Search, Calendar, Clock, Scissors, User, Phone, CheckCircle, AlertCircle } from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000/api';

export default function SearchBooking() {
  const [codigo, setCodigo] = useState('');
  const [cita, setCita] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!codigo.trim()) return;

    setLoading(true);
    setError('');
    setCita(null);

    try {
      const res = await fetch(`${API_BASE}/citas/codigo/${codigo.trim().toUpperCase()}`);
      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || "Cita no encontrada con ese código.");
      }

      setCita(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold text-white flex items-center justify-center gap-2">
          <Search className="w-6 h-6 text-amber-400" />
          Consulta tu Cita
        </h2>
        <p className="text-slate-400 text-sm mt-1">
          Ingresa el código alfanumérico que recibiste al confirmar tu reserva (ej. BSP-4CD0AA).
        </p>
      </div>

      <form onSubmit={handleSearch} className="flex gap-2 mb-8">
        <input
          type="text"
          placeholder="BSP-XXXXXX"
          value={codigo}
          onChange={(e) => setCodigo(e.target.value)}
          className="flex-1 px-4 py-3 bg-slate-900 border border-slate-800 rounded-xl text-white font-mono tracking-wider focus:border-amber-500 focus:outline-none uppercase"
        />
        <button
          type="submit"
          disabled={loading || !codigo.trim()}
          className="px-6 py-3 bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-slate-950 font-bold rounded-xl transition flex items-center gap-2"
        >
          {loading ? 'Buscando...' : 'Buscar'}
        </button>
      </form>

      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm flex items-center gap-2 mb-6">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {cita && (
        <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-4">
            <div>
              <span className="text-xs text-slate-500 font-mono">Código de Reserva</span>
              <h3 className="text-xl font-bold font-mono text-amber-400">{cita.codigo_reserva}</h3>
            </div>
            <span className="px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/30">
              {cita.estado}
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
            <div>
              <span className="text-slate-400 flex items-center gap-1.5 mb-1">
                <Scissors className="w-3.5 h-3.5 text-amber-400" /> Servicio
              </span>
              <p className="font-semibold text-white text-sm">{cita.servicio?.nombre || 'Servicio'}</p>
              <p className="text-slate-400">{cita.servicio?.duracion_minutos} min — ${Number(cita.servicio?.precio).toFixed(2)}</p>
            </div>

            <div>
              <span className="text-slate-400 flex items-center gap-1.5 mb-1">
                <User className="w-3.5 h-3.5 text-amber-400" /> Barbero
              </span>
              <p className="font-semibold text-white text-sm">{cita.barbero?.nombre || 'Barbero'}</p>
              <p className="text-slate-400">{cita.barbero?.especialidad}</p>
            </div>

            <div>
              <span className="text-slate-400 flex items-center gap-1.5 mb-1">
                <Calendar className="w-3.5 h-3.5 text-amber-400" /> Fecha
              </span>
              <p className="font-semibold text-white text-sm">{cita.fecha}</p>
            </div>

            <div>
              <span className="text-slate-400 flex items-center gap-1.5 mb-1">
                <Clock className="w-3.5 h-3.5 text-amber-400" /> Horario
              </span>
              <p className="font-semibold text-amber-400 text-sm">
                {cita.hora_inicio?.slice(0, 5)} a {cita.hora_fin?.slice(0, 5)}
              </p>
            </div>
          </div>

          <div className="pt-3 border-t border-slate-800 text-xs text-slate-400">
            <span>Cliente: <strong className="text-white">{cita.cliente_nombre}</strong> ({cita.cliente_telefono})</span>
          </div>
        </div>
      )}
    </div>
  );
}
