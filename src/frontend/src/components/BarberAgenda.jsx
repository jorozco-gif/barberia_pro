import React, { useState, useEffect } from 'react';
import { Calendar, User, Clock, Scissors, CheckCircle, Play, XCircle, Phone } from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000/api';

export default function BarberAgenda() {
  const [citas, setCitas] = useState([]);
  const [barberos, setBarberos] = useState([]);
  const [selectedBarberoId, setSelectedBarberoId] = useState('');
  const [selectedFecha, setSelectedFecha] = useState(() => new Date().toISOString().split('T')[0]);
  const [loading, setLoading] = useState(false);
  const [actionError, setActionError] = useState('');

  // Cargar lista de barberos
  useEffect(() => {
    fetch(`${API_BASE}/barberos`)
      .then(res => res.json())
      .then(data => setBarberos(data))
      .catch(err => console.error(err));
  }, []);

  // Cargar citas según filtros
  const fetchCitas = () => {
    setLoading(true);
    let url = `${API_BASE}/citas?fecha=${selectedFecha}`;
    if (selectedBarberoId) {
      url += `&barbero_id=${selectedBarberoId}`;
    }

    fetch(url)
      .then(res => res.json())
      .then(data => {
        setCitas(data);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchCitas();
  }, [selectedFecha, selectedBarberoId]);

  // Cambiar estado de una cita
  const handleCambiarEstado = async (citaId, nuevoEstado) => {
    setActionError('');
    try {
      const res = await fetch(`${API_BASE}/citas/${citaId}/estado`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ estado: nuevoEstado })
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Error al actualizar estado");
      }

      // Refrescar lista
      fetchCitas();
    } catch (err) {
      setActionError(err.message);
    }
  };

  const getBadgeStyle = (estado) => {
    switch (estado) {
      case 'Pendiente':
        return 'bg-amber-500/10 text-amber-400 border-amber-500/30';
      case 'En curso':
        return 'bg-blue-500/10 text-blue-400 border-blue-500/30';
      case 'Finalizada':
        return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
      case 'Cancelada':
        return 'bg-rose-500/10 text-rose-400 border-rose-500/30';
      default:
        return 'bg-slate-800 text-slate-400 border-slate-700';
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            <Calendar className="w-6 h-6 text-amber-400" />
            Agenda y Control de Citas
          </h2>
          <p className="text-slate-400 text-xs sm:text-sm mt-1">
            Supervisa los turnos del día y gestiona el flujo de atención del personal.
          </p>
        </div>

        {/* Filtros */}
        <div className="flex flex-wrap items-center gap-3">
          <input
            type="date"
            value={selectedFecha}
            onChange={(e) => setSelectedFecha(e.target.value)}
            className="px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-white text-sm focus:border-amber-500 focus:outline-none"
          />

          <select
            value={selectedBarberoId}
            onChange={(e) => setSelectedBarberoId(e.target.value)}
            className="px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-white text-sm focus:border-amber-500 focus:outline-none"
          >
            <option value="">Todos los barberos</option>
            {barberos.map(b => (
              <option key={b.id} value={b.id}>{b.nombre}</option>
            ))}
          </select>
        </div>
      </div>

      {actionError && (
        <div className="mb-6 p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm">
          {actionError}
        </div>
      )}

      {loading ? (
        <div className="py-16 text-center text-slate-400 text-sm">Cargando agenda...</div>
      ) : citas.length === 0 ? (
        <div className="py-16 text-center bg-slate-900/50 border border-slate-800/80 rounded-2xl">
          <Calendar className="w-10 h-10 text-slate-600 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-slate-300">No hay citas registradas</h3>
          <p className="text-slate-500 text-xs mt-1">Para la fecha y barbero seleccionados.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {citas.map((cita) => (
            <div
              key={cita.id}
              className="p-5 rounded-2xl bg-slate-900 border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4 transition hover:border-slate-700"
            >
              <div className="flex items-start gap-4">
                <div className="w-14 h-14 rounded-xl bg-slate-950 border border-slate-800 flex flex-col items-center justify-center text-center flex-shrink-0">
                  <span className="text-amber-400 font-bold text-sm">{cita.hora_inicio.slice(0, 5)}</span>
                  <span className="text-[10px] text-slate-500">{cita.hora_fin.slice(0, 5)}</span>
                </div>

                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-bold text-white text-base">{cita.cliente_nombre}</h3>
                    <span className="text-xs font-mono font-medium text-slate-500">#{cita.codigo_reserva}</span>
                    <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full border ${getBadgeStyle(cita.estado)}`}>
                      {cita.estado}
                    </span>
                  </div>

                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-xs text-slate-400">
                    <span className="flex items-center gap-1.5">
                      <Scissors className="w-3.5 h-3.5 text-amber-400" />
                      {cita.servicio?.nombre || 'Servicio'}
                    </span>
                    <span className="flex items-center gap-1.5">
                      <User className="w-3.5 h-3.5 text-slate-400" />
                      {cita.barbero?.nombre || 'Barbero'}
                    </span>
                    <span className="flex items-center gap-1.5">
                      <Phone className="w-3.5 h-3.5 text-slate-400" />
                      {cita.cliente_telefono}
                    </span>
                  </div>

                  {cita.notas && (
                    <p className="text-xs text-slate-400/80 bg-slate-950/60 p-2 rounded-lg mt-2 border border-slate-800/80">
                      💬 <span className="font-medium text-slate-300">Nota:</span> {cita.notas}
                    </p>
                  )}
                </div>
              </div>

              {/* Acciones de Estado */}
              <div className="flex items-center gap-2 pt-3 md:pt-0 border-t md:border-t-0 border-slate-800 flex-shrink-0">
                {cita.estado === 'Pendiente' && (
                  <button
                    onClick={() => handleCambiarEstado(cita.id, 'En curso')}
                    className="px-3 py-1.5 rounded-lg bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 border border-blue-500/30 text-xs font-medium flex items-center gap-1.5 transition"
                  >
                    <Play className="w-3.5 h-3.5" /> Iniciar
                  </button>
                )}

                {cita.estado === 'En curso' && (
                  <button
                    onClick={() => handleCambiarEstado(cita.id, 'Finalizada')}
                    className="px-3 py-1.5 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-xs font-medium flex items-center gap-1.5 transition"
                  >
                    <CheckCircle className="w-3.5 h-3.5" /> Finalizar
                  </button>
                )}

                {(cita.estado === 'Pendiente' || cita.estado === 'En curso') && (
                  <button
                    onClick={() => handleCambiarEstado(cita.id, 'Cancelada')}
                    className="px-3 py-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 text-xs font-medium flex items-center gap-1.5 transition"
                  >
                    <XCircle className="w-3.5 h-3.5" /> Cancelar
                  </button>
                )}

                {cita.estado === 'Finalizada' && (
                  <span className="text-xs text-emerald-400 font-semibold flex items-center gap-1">
                    <CheckCircle className="w-4 h-4" /> Completada
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
