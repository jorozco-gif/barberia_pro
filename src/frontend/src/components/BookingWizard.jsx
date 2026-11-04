import React, { useState, useEffect } from 'react';
import { Scissors, User, Calendar as CalendarIcon, Clock, Check, AlertCircle, ArrowRight, ArrowLeft } from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000/api';

export default function BookingWizard({ onBookingSuccess }) {
  const [step, setStep] = useState(1);
  const [servicios, setServicios] = useState([]);
  const [barberos, setBarberos] = useState([]);
  const [slots, setSlots] = useState([]);
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  // Estado del formulario de reserva
  const [selectedServicio, setSelectedServicio] = useState(null);
  const [selectedBarbero, setSelectedBarbero] = useState(null);
  const [selectedDate, setSelectedDate] = useState(() => {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    return tomorrow.toISOString().split('T')[0];
  });
  const [selectedSlot, setSelectedSlot] = useState(null);
  const [cliente, setCliente] = useState({
    nombre: '',
    telefono: '',
    email: '',
    notas: ''
  });

  // Cargar servicios y barberos al montar
  useEffect(() => {
    fetch(`${API_BASE}/servicios`)
      .then(res => res.json())
      .then(data => setServicios(data))
      .catch(err => console.error("Error al cargar servicios:", err));

    fetch(`${API_BASE}/barberos`)
      .then(res => res.json())
      .then(data => setBarberos(data))
      .catch(err => console.error("Error al cargar barberos:", err));
  }, []);

  // Cargar slots cuando cambie barbero, servicio o fecha
  useEffect(() => {
    if (selectedBarbero && selectedServicio && selectedDate) {
      setLoadingSlots(true);
      setSelectedSlot(null);
      fetch(`${API_BASE}/disponibilidad?barbero_id=${selectedBarbero.id}&fecha=${selectedDate}&servicio_id=${selectedServicio.id}`)
        .then(res => res.json())
        .then(data => {
          setSlots(data);
          setLoadingSlots(false);
        })
        .catch(err => {
          console.error("Error al cargar disponibilidad:", err);
          setLoadingSlots(false);
        });
    }
  }, [selectedBarbero, selectedServicio, selectedDate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage('');
    setSubmitting(true);

    const payload = {
      barbero_id: selectedBarbero.id,
      servicio_id: selectedServicio.id,
      cliente_nombre: cliente.nombre,
      cliente_telefono: cliente.telefono,
      cliente_email: cliente.email || null,
      fecha: selectedDate,
      hora_inicio: selectedSlot.hora_inicio,
      notas: cliente.notas || null
    };

    try {
      const res = await fetch(`${API_BASE}/citas`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const data = await res.json();

      if (!res.ok) {
        if (res.status === 409) {
          throw new Error("El horario seleccionado ya no está disponible. Por favor elige otro turno.");
        } else if (res.status === 422) {
          throw new Error("Por favor revisa que todos los datos ingresados sean correctos.");
        } else {
          throw new Error(data.detail || "Ocurrió un error al procesar la reserva.");
        }
      }

      // Éxito: notificar al padre para abrir el modal
      onBookingSuccess(data);

      // Reiniciar formulario
      setStep(1);
      setSelectedServicio(null);
      setSelectedBarbero(null);
      setSelectedSlot(null);
      setCliente({ nombre: '', telefono: '', email: '', notas: '' });

    } catch (err) {
      setErrorMessage(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Indicador de Pasos */}
      <div className="flex items-center justify-between mb-8 relative">
        <div className="absolute left-0 top-1/2 -translate-y-1/2 h-0.5 w-full bg-slate-800 -z-0" />
        {[
          { num: 1, label: 'Servicio', icon: Scissors },
          { num: 2, label: 'Barbero', icon: User },
          { num: 3, label: 'Fecha y Hora', icon: CalendarIcon },
          { num: 4, label: 'Confirmación', icon: Check }
        ].map((item) => {
          const Icon = item.icon;
          const isDone = step > item.num;
          const isCurrent = step === item.num;
          return (
            <div key={item.num} className="relative z-10 flex flex-col items-center">
              <div
                className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-sm transition ${
                  isCurrent
                    ? 'bg-amber-500 text-slate-950 ring-4 ring-amber-500/20'
                    : isDone
                    ? 'bg-emerald-500 text-white'
                    : 'bg-slate-800 text-slate-400 border border-slate-700'
                }`}
              >
                {isDone ? <Check className="w-5 h-5" /> : <Icon className="w-4 h-4" />}
              </div>
              <span className={`text-xs mt-2 font-medium ${isCurrent ? 'text-amber-400' : 'text-slate-400'}`}>
                {item.label}
              </span>
            </div>
          );
        })}
      </div>

      {/* Alerta de Error */}
      {errorMessage && (
        <div className="mb-6 p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-center gap-3 text-rose-300">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <p className="text-sm">{errorMessage}</p>
        </div>
      )}

      {/* ================= PASO 1: SERVICIOS ================= */}
      {step === 1 && (
        <div>
          <div className="text-center mb-6">
            <h2 className="text-2xl font-bold text-white">Selecciona un Servicio</h2>
            <p className="text-slate-400 text-sm mt-1">Elige la experiencia o tratamiento que deseas recibir.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {servicios.map((s) => {
              const selected = selectedServicio?.id === s.id;
              return (
                <div
                  key={s.id}
                  onClick={() => setSelectedServicio(s)}
                  className={`p-5 rounded-2xl border cursor-pointer transition relative flex flex-col justify-between ${
                    selected
                      ? 'bg-amber-500/10 border-amber-500 shadow-lg shadow-amber-500/10'
                      : 'bg-slate-900 border-slate-800 hover:border-slate-700'
                  }`}
                >
                  <div>
                    <div className="flex items-start justify-between">
                      <h3 className="font-bold text-lg text-white">{s.nombre}</h3>
                      <span className="text-amber-400 font-bold text-lg">${Number(s.precio).toFixed(2)}</span>
                    </div>
                    <p className="text-slate-400 text-xs mt-2 leading-relaxed">{s.descripcion}</p>
                  </div>
                  <div className="flex items-center justify-between mt-4 pt-3 border-t border-slate-800 text-xs text-slate-400">
                    <span className="flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5 text-amber-400" /> {s.duracion_minutos} minutos
                    </span>
                    <span className={`font-semibold ${selected ? 'text-amber-400' : 'text-slate-500'}`}>
                      {selected ? 'Seleccionado ✓' : 'Elegir'}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="mt-8 flex justify-end">
            <button
              disabled={!selectedServicio}
              onClick={() => setStep(2)}
              className="px-6 py-3 bg-amber-500 hover:bg-amber-400 disabled:opacity-40 disabled:hover:bg-amber-500 text-slate-950 font-bold rounded-xl transition flex items-center gap-2"
            >
              Siguiente: Elegir Barbero <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* ================= PASO 2: BARBEROS ================= */}
      {step === 2 && (
        <div>
          <div className="text-center mb-6">
            <h2 className="text-2xl font-bold text-white">Selecciona a tu Barbero</h2>
            <p className="text-slate-400 text-sm mt-1">Nuestros profesionales cuentan con especialidades certificadas.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {barberos.map((b) => {
              const selected = selectedBarbero?.id === b.id;
              return (
                <div
                  key={b.id}
                  onClick={() => setSelectedBarbero(b)}
                  className={`p-5 rounded-2xl border cursor-pointer transition text-center flex flex-col justify-between ${
                    selected
                      ? 'bg-amber-500/10 border-amber-500 shadow-lg shadow-amber-500/10'
                      : 'bg-slate-900 border-slate-800 hover:border-slate-700'
                  }`}
                >
                  <div>
                    <div className="w-16 h-16 rounded-2xl bg-slate-800 border border-slate-700 mx-auto flex items-center justify-center text-amber-400 font-bold text-xl mb-3">
                      {b.nombre[0]}
                    </div>
                    <h3 className="font-bold text-base text-white">{b.nombre}</h3>
                    <p className="text-xs text-amber-400/90 mt-1 font-medium">{b.especialidad}</p>
                  </div>
                  <div className="mt-4 pt-3 border-t border-slate-800">
                    <span className={`text-xs font-semibold ${selected ? 'text-amber-400' : 'text-slate-500'}`}>
                      {selected ? 'Seleccionado ✓' : 'Seleccionar'}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="mt-8 flex justify-between">
            <button
              onClick={() => setStep(1)}
              className="px-5 py-3 border border-slate-700 hover:bg-slate-800 text-slate-300 font-medium rounded-xl transition flex items-center gap-2"
            >
              <ArrowLeft className="w-4 h-4" /> Volver a Servicios
            </button>
            <button
              disabled={!selectedBarbero}
              onClick={() => setStep(3)}
              className="px-6 py-3 bg-amber-500 hover:bg-amber-400 disabled:opacity-40 disabled:hover:bg-amber-500 text-slate-950 font-bold rounded-xl transition flex items-center gap-2"
            >
              Siguiente: Fecha y Turno <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* ================= PASO 3: FECHA Y SLOTS ================= */}
      {step === 3 && (
        <div>
          <div className="text-center mb-6">
            <h2 className="text-2xl font-bold text-white">Fecha y Horario</h2>
            <p className="text-slate-400 text-sm mt-1">Los turnos se calculan en vivo según la duración del servicio ({selectedServicio?.duracion_minutos} min).</p>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 mb-6">
            <label className="block text-xs uppercase tracking-wider text-slate-400 font-semibold mb-2">
              Seleccionar Fecha
            </label>
            <input
              type="date"
              value={selectedDate}
              min={new Date().toISOString().split('T')[0]}
              onChange={(e) => setSelectedDate(e.target.value)}
              className="w-full sm:w-64 px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-white font-medium focus:border-amber-500 focus:outline-none"
            />
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
            <h3 className="font-semibold text-sm text-slate-300 mb-4 flex items-center gap-2">
              <Clock className="w-4 h-4 text-amber-400" />
              Turnos Disponibles para el {selectedDate}:
            </h3>

            {loadingSlots ? (
              <div className="py-8 text-center text-slate-400 text-sm">Consultando disponibilidad en tiempo real...</div>
            ) : slots.length === 0 ? (
              <div className="py-8 text-center text-slate-500 text-sm">No hay horarios disponibles para esta fecha.</div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 gap-3">
                {slots.map((s, idx) => {
                  const isSelected = selectedSlot?.hora_inicio === s.hora_inicio;
                  return (
                    <button
                      key={idx}
                      disabled={!s.disponible}
                      onClick={() => setSelectedSlot(s)}
                      className={`p-3 rounded-xl border text-center transition flex flex-col items-center justify-center ${
                        !s.disponible
                          ? 'bg-slate-950/40 border-slate-900 text-slate-600 cursor-not-allowed line-through'
                          : isSelected
                          ? 'bg-amber-500 text-slate-950 font-bold border-amber-500 shadow-md shadow-amber-500/20'
                          : 'bg-slate-950 border-slate-800 text-slate-200 hover:border-slate-700'
                      }`}
                    >
                      <span className="text-sm font-semibold">{s.hora_inicio}</span>
                      <span className="text-[10px] opacity-70">a {s.hora_fin}</span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <div className="mt-8 flex justify-between">
            <button
              onClick={() => setStep(2)}
              className="px-5 py-3 border border-slate-700 hover:bg-slate-800 text-slate-300 font-medium rounded-xl transition flex items-center gap-2"
            >
              <ArrowLeft className="w-4 h-4" /> Volver a Barberos
            </button>
            <button
              disabled={!selectedSlot}
              onClick={() => setStep(4)}
              className="px-6 py-3 bg-amber-500 hover:bg-amber-400 disabled:opacity-40 disabled:hover:bg-amber-500 text-slate-950 font-bold rounded-xl transition flex items-center gap-2"
            >
              Siguiente: Datos de Contacto <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* ================= PASO 4: FORMULARIO Y CONFIRMACIÓN ================= */}
      {step === 4 && (
        <div>
          <div className="text-center mb-6">
            <h2 className="text-2xl font-bold text-white">Confirmar Reserva</h2>
            <p className="text-slate-400 text-sm mt-1">Ingresa tus datos para generar el código de tu cita.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Resumen de la Cita */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 h-fit">
              <h3 className="font-bold text-sm text-slate-300 uppercase tracking-wider mb-4 border-b border-slate-800 pb-2">
                Resumen de Reserva
              </h3>
              <div className="space-y-3 text-xs">
                <div>
                  <span className="text-slate-400">Servicio:</span>
                  <p className="font-semibold text-white text-sm mt-0.5">{selectedServicio?.nombre}</p>
                </div>
                <div>
                  <span className="text-slate-400">Barbero:</span>
                  <p className="font-semibold text-white text-sm mt-0.5">{selectedBarbero?.nombre}</p>
                </div>
                <div>
                  <span className="text-slate-400">Fecha y Hora:</span>
                  <p className="font-semibold text-amber-400 text-sm mt-0.5">
                    {selectedDate} ({selectedSlot?.hora_inicio} — {selectedSlot?.hora_fin})
                  </p>
                </div>
                <div className="pt-3 border-t border-slate-800 flex justify-between items-center text-sm">
                  <span className="text-slate-400">Total a Pagar:</span>
                  <span className="font-bold text-lg text-emerald-400">${Number(selectedServicio?.precio).toFixed(2)}</span>
                </div>
              </div>
            </div>

            {/* Formulario del Cliente */}
            <form onSubmit={handleSubmit} className="md:col-span-2 bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                  Nombre Completo *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Ej: Carlos Mendoza"
                  value={cliente.nombre}
                  onChange={(e) => setCliente({ ...cliente, nombre: e.target.value })}
                  className="w-full px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-white placeholder-slate-600 focus:border-amber-500 focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                    Teléfono Móvil *
                  </label>
                  <input
                    type="tel"
                    required
                    placeholder="3001234567"
                    value={cliente.telefono}
                    onChange={(e) => setCliente({ ...cliente, telefono: e.target.value })}
                    className="w-full px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-white placeholder-slate-600 focus:border-amber-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                    Correo Electrónico (Opcional)
                  </label>
                  <input
                    type="email"
                    placeholder="carlos@example.com"
                    value={cliente.email}
                    onChange={(e) => setCliente({ ...cliente, email: e.target.value })}
                    className="w-full px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-white placeholder-slate-600 focus:border-amber-500 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                  Notas o Preferencias Especiales
                </label>
                <textarea
                  rows={2}
                  placeholder="Ej: Degradado bajo con navaja, poco corte arriba..."
                  value={cliente.notas}
                  onChange={(e) => setCliente({ ...cliente, notas: e.target.value })}
                  className="w-full px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-white placeholder-slate-600 focus:border-amber-500 focus:outline-none text-sm"
                />
              </div>

              <div className="pt-4 flex justify-between items-center">
                <button
                  type="button"
                  onClick={() => setStep(3)}
                  className="px-5 py-3 border border-slate-700 hover:bg-slate-800 text-slate-300 font-medium rounded-xl transition flex items-center gap-2"
                >
                  <ArrowLeft className="w-4 h-4" /> Modificar Horario
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-8 py-3 bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-slate-950 font-bold rounded-xl transition shadow-lg shadow-amber-500/20 flex items-center gap-2"
                >
                  {submitting ? 'Confirmando...' : 'Confirmar y Agendar'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
