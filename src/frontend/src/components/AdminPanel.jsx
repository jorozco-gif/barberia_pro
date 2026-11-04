import React, { useState, useEffect, useCallback } from 'react';
import { ShieldCheck, Users, Scissors, Plus, Pencil, Trash2, Clock } from 'lucide-react';
import { api } from '../api';
import { formatearPrecio } from '../formato';
import Alerta from './Alerta';

const CLASE_INPUT =
  'w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-white text-sm placeholder-slate-600 focus:border-amber-500 focus:outline-none';
const CLASE_LABEL = 'block text-xs uppercase tracking-wider text-slate-400 font-semibold mb-1.5';
const CLASE_BOTON_PRIMARIO =
  'px-4 py-2 bg-amber-500 hover:bg-amber-400 disabled:opacity-50 disabled:hover:bg-amber-500 text-slate-950 font-bold text-sm rounded-xl transition flex items-center justify-center gap-2';
const CLASE_BOTON_SECUNDARIO =
  'px-4 py-2 border border-slate-700 hover:bg-slate-800 text-slate-300 text-sm rounded-xl transition';

function Campo({ id, etiqueta, children }) {
  return (
    <div>
      <label htmlFor={id} className={CLASE_LABEL}>{etiqueta}</label>
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Barberos: alta, modificación de perfil y baja lógica (RF-05, RF-06, RF-07)
// ---------------------------------------------------------------------------
const BARBERO_VACIO = { nombre: '', email: '', password: '', foto_url: '' };

function PanelBarberos() {
  const [barberos, setBarberos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [mensaje, setMensaje] = useState('');
  const [nuevo, setNuevo] = useState(BARBERO_VACIO);
  const [creando, setCreando] = useState(false);
  const [editando, setEditando] = useState(null); // { id, nombre, foto_url }
  const [guardando, setGuardando] = useState(false);
  const [eliminandoId, setEliminandoId] = useState(null); // confirmación pendiente
  const [procesando, setProcesando] = useState(false);

  const cargar = useCallback(async () => {
    try {
      setBarberos(await api.adminBarberos());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const crear = async (e) => {
    e.preventDefault();
    setError('');
    setMensaje('');
    setCreando(true);
    try {
      const creado = await api.adminCrearBarbero({
        nombre: nuevo.nombre.trim(),
        email: nuevo.email.trim(),
        password: nuevo.password,
        foto_url: nuevo.foto_url.trim() || null,
      });
      setNuevo(BARBERO_VACIO);
      setMensaje(`Barbero ${creado.nombre} registrado. Ya puede iniciar sesión con su correo y contraseña.`);
      await cargar();
    } catch (err) {
      setError(err.message);
    } finally {
      setCreando(false);
    }
  };

  const guardar = async (e) => {
    e.preventDefault();
    setError('');
    setMensaje('');
    setGuardando(true);
    try {
      await api.adminActualizarBarbero(editando.id, {
        nombre: editando.nombre.trim(),
        foto_url: editando.foto_url.trim() || null,
      });
      setEditando(null);
      setMensaje('Perfil del barbero actualizado.');
      await cargar();
    } catch (err) {
      setError(err.message); // en 422 el perfil conserva los datos anteriores (CA-06.2)
    } finally {
      setGuardando(false);
    }
  };

  const eliminar = async (barbero) => {
    setError('');
    setMensaje('');
    setProcesando(true);
    try {
      await api.adminEliminarBarbero(barbero.id);
      setEliminandoId(null);
      setMensaje(`El perfil de ${barbero.nombre} fue dado de baja. Sus citas futuras se cancelaron y se notificó a los clientes.`);
      await cargar();
    } catch (err) {
      setEliminandoId(null);
      setError(err.message);
      if (err.status !== 0) await cargar();
    } finally {
      setProcesando(false);
    }
  };

  return (
    <div className="space-y-6">
      <form onSubmit={crear} className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
        <h3 className="font-bold text-sm text-slate-300 uppercase tracking-wider mb-4">Registrar barbero</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Campo id="barb-nombre" etiqueta="Nombre">
            <input id="barb-nombre" required minLength={2} maxLength={120} value={nuevo.nombre} onChange={(e) => setNuevo({ ...nuevo, nombre: e.target.value })} className={CLASE_INPUT} />
          </Campo>
          <Campo id="barb-email" etiqueta="Correo electrónico">
            <input id="barb-email" type="email" required value={nuevo.email} onChange={(e) => setNuevo({ ...nuevo, email: e.target.value })} className={CLASE_INPUT} />
          </Campo>
          <Campo id="barb-password" etiqueta="Contraseña">
            <input id="barb-password" type="password" required minLength={8} maxLength={128} autoComplete="new-password" placeholder="Mínimo 8 caracteres" value={nuevo.password} onChange={(e) => setNuevo({ ...nuevo, password: e.target.value })} className={CLASE_INPUT} />
          </Campo>
          <Campo id="barb-foto" etiqueta="URL de la foto (opcional)">
            <input id="barb-foto" type="url" maxLength={255} placeholder="https://..." value={nuevo.foto_url} onChange={(e) => setNuevo({ ...nuevo, foto_url: e.target.value })} className={CLASE_INPUT} />
          </Campo>
        </div>
        <div className="mt-4 flex justify-end">
          <button type="submit" disabled={creando} className={CLASE_BOTON_PRIMARIO}>
            <Plus className="w-4 h-4" /> {creando ? 'Registrando...' : 'Registrar barbero'}
          </button>
        </div>
      </form>

      <Alerta tipo="error">{error}</Alerta>
      <Alerta tipo="exito">{mensaje}</Alerta>

      {loading ? (
        <div className="py-12 text-center text-slate-400 text-sm">Cargando barberos...</div>
      ) : barberos.length === 0 ? (
        <div className="py-12 text-center text-slate-500 text-sm">No hay barberos registrados.</div>
      ) : (
        <div className="space-y-3">
          {barberos.map((b) => (
            <div key={b.id} className="p-4 rounded-2xl bg-slate-900 border border-slate-800">
              {editando?.id === b.id ? (
                <form onSubmit={guardar} className="space-y-4">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <Campo id={`edit-nombre-${b.id}`} etiqueta="Nombre">
                      <input id={`edit-nombre-${b.id}`} required minLength={2} maxLength={120} value={editando.nombre} onChange={(e) => setEditando({ ...editando, nombre: e.target.value })} className={CLASE_INPUT} />
                    </Campo>
                    <Campo id={`edit-foto-${b.id}`} etiqueta="URL de la foto">
                      <input id={`edit-foto-${b.id}`} type="url" maxLength={255} placeholder="https://..." value={editando.foto_url} onChange={(e) => setEditando({ ...editando, foto_url: e.target.value })} className={CLASE_INPUT} />
                    </Campo>
                  </div>
                  <div className="flex justify-end gap-2">
                    <button type="button" onClick={() => setEditando(null)} className={CLASE_BOTON_SECUNDARIO}>Cancelar</button>
                    <button type="submit" disabled={guardando} className={CLASE_BOTON_PRIMARIO}>{guardando ? 'Guardando...' : 'Guardar cambios'}</button>
                  </div>
                </form>
              ) : (
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    {b.foto_url ? (
                      <img src={b.foto_url} alt={b.nombre} className="w-12 h-12 rounded-xl object-cover border border-slate-700" />
                    ) : (
                      <div className="w-12 h-12 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-amber-400 font-bold">
                        {b.nombre[0]}
                      </div>
                    )}
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="font-bold text-white">{b.nombre}</h4>
                        <span
                          className={`text-[11px] font-semibold px-2 py-0.5 rounded-full border ${
                            b.activo
                              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                              : 'bg-slate-800 text-slate-400 border-slate-700'
                          }`}
                        >
                          {b.activo ? 'Activo' : 'Inactivo'}
                        </span>
                      </div>
                      <p className="text-xs text-slate-400">{b.email}</p>
                    </div>
                  </div>

                  {b.activo &&
                    (eliminandoId === b.id ? (
                      <div className="flex flex-col sm:items-end gap-2 sm:max-w-sm">
                        <p className="text-xs text-slate-300 sm:text-right">
                          Se dará de baja el perfil, se cancelarán sus citas futuras y se notificará a los clientes.
                          El historial se conserva. ¿Continuar?
                        </p>
                        <div className="flex gap-2">
                          <button onClick={() => setEliminandoId(null)} className="px-3 py-1.5 rounded-lg border border-slate-700 hover:bg-slate-800 text-slate-300 text-xs transition">No</button>
                          <button
                            disabled={procesando}
                            onClick={() => eliminar(b)}
                            className="px-3 py-1.5 rounded-lg bg-rose-500 hover:bg-rose-400 disabled:opacity-50 text-white text-xs font-semibold transition"
                          >
                            {procesando ? 'Eliminando...' : 'Sí, dar de baja'}
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex gap-2">
                        <button
                          onClick={() => {
                            setError('');
                            setMensaje('');
                            setEditando({ id: b.id, nombre: b.nombre, foto_url: b.foto_url || '' });
                          }}
                          className="px-3 py-1.5 rounded-lg bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 border border-blue-500/30 text-xs font-medium flex items-center gap-1.5 transition"
                        >
                          <Pencil className="w-3.5 h-3.5" /> Editar
                        </button>
                        <button
                          onClick={() => setEliminandoId(b.id)}
                          className="px-3 py-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 text-xs font-medium flex items-center gap-1.5 transition"
                        >
                          <Trash2 className="w-3.5 h-3.5" /> Eliminar
                        </button>
                      </div>
                    ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Servicios: alta, modificación y baja lógica (RF-08, RF-09, RF-10)
// ---------------------------------------------------------------------------
const SERVICIO_VACIO = { nombre: '', duracion_minutos: '', precio: '' };

function PanelServicios() {
  const [servicios, setServicios] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [mensaje, setMensaje] = useState('');
  const [nuevo, setNuevo] = useState(SERVICIO_VACIO);
  const [creando, setCreando] = useState(false);
  const [editando, setEditando] = useState(null);
  const [guardando, setGuardando] = useState(false);
  const [eliminandoId, setEliminandoId] = useState(null);
  const [procesando, setProcesando] = useState(false);

  const cargar = useCallback(async () => {
    try {
      setServicios(await api.servicios());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  // El precio se envía como texto: el backend lo interpreta como Decimal sin pérdida de precisión.
  const aPayload = (f) => ({ nombre: f.nombre.trim(), duracion_minutos: Number(f.duracion_minutos), precio: String(f.precio).trim() });

  const crear = async (e) => {
    e.preventDefault();
    setError('');
    setMensaje('');
    setCreando(true);
    try {
      const creado = await api.adminCrearServicio(aPayload(nuevo));
      setNuevo(SERVICIO_VACIO);
      setMensaje(`Servicio ${creado.nombre} agregado al catálogo.`);
      await cargar();
    } catch (err) {
      setError(err.message);
    } finally {
      setCreando(false);
    }
  };

  const guardar = async (e) => {
    e.preventDefault();
    setError('');
    setMensaje('');
    setGuardando(true);
    try {
      await api.adminActualizarServicio(editando.id, aPayload(editando));
      setEditando(null);
      setMensaje('Servicio actualizado. Las citas ya agendadas conservan el precio con el que se reservaron.');
      await cargar();
    } catch (err) {
      setError(err.message);
    } finally {
      setGuardando(false);
    }
  };

  const eliminar = async (servicio) => {
    setError('');
    setMensaje('');
    setProcesando(true);
    try {
      await api.adminEliminarServicio(servicio.id);
      setEliminandoId(null);
      setMensaje(`El servicio ${servicio.nombre} ya no está disponible para nuevas citas. Las citas existentes no cambian.`);
      await cargar();
    } catch (err) {
      setEliminandoId(null);
      setError(err.message);
      if (err.status !== 0) await cargar();
    } finally {
      setProcesando(false);
    }
  };

  const camposServicio = (valor, setValor, prefijo) => (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <Campo id={`${prefijo}-nombre`} etiqueta="Nombre">
        <input id={`${prefijo}-nombre`} required minLength={2} maxLength={100} value={valor.nombre} onChange={(e) => setValor({ ...valor, nombre: e.target.value })} className={CLASE_INPUT} />
      </Campo>
      <Campo id={`${prefijo}-duracion`} etiqueta="Duración (minutos)">
        <input id={`${prefijo}-duracion`} type="number" required min={1} max={240} step={1} value={valor.duracion_minutos} onChange={(e) => setValor({ ...valor, duracion_minutos: e.target.value })} className={CLASE_INPUT} />
      </Campo>
      <Campo id={`${prefijo}-precio`} etiqueta="Precio (COP)">
        <input id={`${prefijo}-precio`} type="number" required min={0} step="any" value={valor.precio} onChange={(e) => setValor({ ...valor, precio: e.target.value })} className={CLASE_INPUT} />
      </Campo>
    </div>
  );

  return (
    <div className="space-y-6">
      <form onSubmit={crear} className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
        <h3 className="font-bold text-sm text-slate-300 uppercase tracking-wider mb-4">Agregar servicio</h3>
        {camposServicio(nuevo, setNuevo, 'srv-nuevo')}
        <div className="mt-4 flex justify-end">
          <button type="submit" disabled={creando} className={CLASE_BOTON_PRIMARIO}>
            <Plus className="w-4 h-4" /> {creando ? 'Agregando...' : 'Agregar servicio'}
          </button>
        </div>
      </form>

      <Alerta tipo="error">{error}</Alerta>
      <Alerta tipo="exito">{mensaje}</Alerta>

      {loading ? (
        <div className="py-12 text-center text-slate-400 text-sm">Cargando servicios...</div>
      ) : servicios.length === 0 ? (
        <div className="py-12 text-center text-slate-500 text-sm">No hay servicios en el catálogo.</div>
      ) : (
        <div className="space-y-3">
          {servicios.map((s) => (
            <div key={s.id} className="p-4 rounded-2xl bg-slate-900 border border-slate-800">
              {editando?.id === s.id ? (
                <form onSubmit={guardar} className="space-y-4">
                  {camposServicio(editando, setEditando, `srv-${s.id}`)}
                  <div className="flex justify-end gap-2">
                    <button type="button" onClick={() => setEditando(null)} className={CLASE_BOTON_SECUNDARIO}>Cancelar</button>
                    <button type="submit" disabled={guardando} className={CLASE_BOTON_PRIMARIO}>{guardando ? 'Guardando...' : 'Guardar cambios'}</button>
                  </div>
                </form>
              ) : (
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <h4 className="font-bold text-white">{s.nombre}</h4>
                    <p className="text-xs text-slate-400 flex items-center gap-3 mt-0.5">
                      <span className="flex items-center gap-1"><Clock className="w-3.5 h-3.5 text-amber-400" /> {s.duracion_minutos} min</span>
                      <span className="text-amber-400 font-semibold">{formatearPrecio(s.precio)}</span>
                    </p>
                  </div>

                  {eliminandoId === s.id ? (
                    <div className="flex flex-col sm:items-end gap-2 sm:max-w-sm">
                      <p className="text-xs text-slate-300 sm:text-right">
                        El servicio dejará de ofrecerse a los clientes. Las citas pasadas y agendadas no cambian. ¿Continuar?
                      </p>
                      <div className="flex gap-2">
                        <button onClick={() => setEliminandoId(null)} className="px-3 py-1.5 rounded-lg border border-slate-700 hover:bg-slate-800 text-slate-300 text-xs transition">No</button>
                        <button
                          disabled={procesando}
                          onClick={() => eliminar(s)}
                          className="px-3 py-1.5 rounded-lg bg-rose-500 hover:bg-rose-400 disabled:opacity-50 text-white text-xs font-semibold transition"
                        >
                          {procesando ? 'Eliminando...' : 'Sí, eliminar'}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex gap-2">
                      <button
                        onClick={() => {
                          setError('');
                          setMensaje('');
                          setEditando({ id: s.id, nombre: s.nombre, duracion_minutos: String(s.duracion_minutos), precio: String(Number(s.precio)) });
                        }}
                        className="px-3 py-1.5 rounded-lg bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 border border-blue-500/30 text-xs font-medium flex items-center gap-1.5 transition"
                      >
                        <Pencil className="w-3.5 h-3.5" /> Editar
                      </button>
                      <button
                        onClick={() => setEliminandoId(s.id)}
                        className="px-3 py-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 text-xs font-medium flex items-center gap-1.5 transition"
                      >
                        <Trash2 className="w-3.5 h-3.5" /> Eliminar
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Panel de administración
// ---------------------------------------------------------------------------
const SECCIONES = [
  { id: 'barberos', etiqueta: 'Barberos', Icono: Users },
  { id: 'servicios', etiqueta: 'Servicios', Icono: Scissors },
];

export default function AdminPanel() {
  const [seccion, setSeccion] = useState('barberos');

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-white flex items-center gap-2">
          <ShieldCheck className="w-6 h-6 text-amber-400" />
          Administración
        </h2>
        <p className="text-slate-400 text-xs sm:text-sm mt-1">Gestiona los barberos y el catálogo de servicios.</p>
        <div className="flex gap-1 sm:gap-2 mt-4 border-b border-slate-800">
          {SECCIONES.map(({ id, etiqueta, Icono }) => (
            <button
              key={id}
              onClick={() => setSeccion(id)}
              className={`px-3 sm:px-4 py-2 text-sm font-medium flex items-center gap-2 border-b-2 -mb-px transition ${
                seccion === id ? 'border-amber-500 text-amber-400' : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <Icono className="w-4 h-4" /> {etiqueta}
            </button>
          ))}
        </div>
      </div>

      {seccion === 'barberos' && <PanelBarberos />}
      {seccion === 'servicios' && <PanelServicios />}
    </div>
  );
}
