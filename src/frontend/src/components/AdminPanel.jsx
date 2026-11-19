import React, { useState, useEffect, useCallback } from 'react';
import { ShieldCheck, Users, Scissors, Plus, Pencil, Trash2, Clock, Sparkles } from 'lucide-react';
import { api } from '../api';
import { formatearPrecio } from '../formato';
import Alerta from './Alerta';
import {
  CLASE_BOTON_EDITAR,
  CLASE_BOTON_ELIMINAR,
  CLASE_BOTON_PRIMARIO,
  CLASE_BOTON_SECUNDARIO,
  CLASE_INPUT,
  Campo,
  ConfirmarEliminacion,
} from './admin/comunes';
import PanelEstilos from './admin/PanelEstilos';

// ---------------------------------------------------------------------------
// Barberos: alta, modificación de perfil y baja lógica (RF-05, RF-06, RF-07).
// v1.2 (RF-06): el administrador puede modificar los 4 campos del registro: nombre, correo, contraseña y foto.
// ---------------------------------------------------------------------------
const BARBERO_VACIO = { nombre: '', email: '', password: '', foto_url: '' };

function PanelBarberos() {
  const [barberos, setBarberos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [mensaje, setMensaje] = useState('');
  const [nuevo, setNuevo] = useState(BARBERO_VACIO);
  const [creando, setCreando] = useState(false);
  const [editando, setEditando] = useState(null); // { id, nombre, email, emailOriginal, password, foto_url }
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
    // Solo se envían el correo y la contraseña si cambian: la contraseña vacía conserva la actual.
    const datos = { nombre: editando.nombre.trim(), foto_url: editando.foto_url.trim() || null };
    const email = editando.email.trim();
    if (email.toLowerCase() !== editando.emailOriginal.toLowerCase()) datos.email = email;
    if (editando.password) datos.password = editando.password;
    try {
      await api.adminActualizarBarbero(editando.id, datos);
      setEditando(null);
      setMensaje(
        datos.password
          ? 'Perfil del barbero actualizado. Se cerraron sus sesiones abiertas: debe ingresar con la nueva contraseña.'
          : datos.email
          ? 'Perfil del barbero actualizado. Desde ahora inicia sesión con el nuevo correo.'
          : 'Perfil del barbero actualizado.',
      );
      await cargar();
    } catch (err) {
      setError(err.message); // en 400 o 422 el perfil conserva los datos anteriores (CA-06.2, CA-06.3)
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
                  <h4 className="font-bold text-sm text-slate-300">Editar a {b.nombre}</h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <Campo id={`edit-nombre-${b.id}`} etiqueta="Nombre">
                      <input id={`edit-nombre-${b.id}`} required minLength={2} maxLength={120} autoComplete="off" value={editando.nombre} onChange={(e) => setEditando({ ...editando, nombre: e.target.value })} className={CLASE_INPUT} />
                    </Campo>
                    <Campo id={`edit-email-${b.id}`} etiqueta="Correo electrónico">
                      <input id={`edit-email-${b.id}`} type="email" required maxLength={255} autoComplete="off" value={editando.email} onChange={(e) => setEditando({ ...editando, email: e.target.value })} className={CLASE_INPUT} />
                    </Campo>
                    <Campo id={`edit-password-${b.id}`} etiqueta="Nueva contraseña (opcional)" ayuda="Si la cambias, se cierran las sesiones abiertas del barbero.">
                      <input id={`edit-password-${b.id}`} type="password" minLength={8} maxLength={128} autoComplete="new-password" placeholder="Déjala vacía para no cambiarla" value={editando.password} onChange={(e) => setEditando({ ...editando, password: e.target.value })} className={CLASE_INPUT} />
                    </Campo>
                    <Campo id={`edit-foto-${b.id}`} etiqueta="URL de la foto (opcional)" ayuda="Déjala vacía para quitar la foto.">
                      <div className="flex items-center gap-3">
                        {editando.foto_url.trim() ? (
                          <img src={editando.foto_url.trim()} alt="" className="w-10 h-10 rounded-xl object-cover border border-slate-700 flex-shrink-0" />
                        ) : (
                          <div className="w-10 h-10 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-amber-400 font-bold flex-shrink-0">
                            {(editando.nombre.trim() || b.nombre)[0]}
                          </div>
                        )}
                        <input id={`edit-foto-${b.id}`} type="url" maxLength={255} placeholder="https://..." value={editando.foto_url} onChange={(e) => setEditando({ ...editando, foto_url: e.target.value })} className={CLASE_INPUT} />
                      </div>
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
                      <ConfirmarEliminacion
                        texto="Se dará de baja el perfil, se cancelarán sus citas futuras y se notificará a los clientes. El historial se conserva. ¿Continuar?"
                        procesando={procesando}
                        textoConfirmar="Sí, dar de baja"
                        onCancelar={() => setEliminandoId(null)}
                        onConfirmar={() => eliminar(b)}
                      />
                    ) : (
                      <div className="flex gap-2">
                        <button
                          onClick={() => {
                            setError('');
                            setMensaje('');
                            setEditando({
                              id: b.id,
                              nombre: b.nombre,
                              email: b.email,
                              emailOriginal: b.email,
                              password: '',
                              foto_url: b.foto_url || '',
                            });
                          }}
                          className={CLASE_BOTON_EDITAR}
                        >
                          <Pencil className="w-3.5 h-3.5" /> Editar
                        </button>
                        <button
                          onClick={() => setEliminandoId(b.id)}
                          className={CLASE_BOTON_ELIMINAR}
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
// Servicios: alta, modificación y baja lógica (RF-08, RF-09, RF-10).
// v1.2: descripción opcional que el cliente ve en un modal al elegir servicios.
// ---------------------------------------------------------------------------
const SERVICIO_VACIO = { nombre: '', duracion_minutos: '', precio: '', descripcion: '' };

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
  // La descripción vacía se envía como null: el servicio queda sin descripción y el cliente no ve el botón.
  const aPayload = (f) => ({
    nombre: f.nombre.trim(),
    duracion_minutos: Number(f.duracion_minutos),
    precio: String(f.precio).trim(),
    descripcion: f.descripcion.trim() || null,
  });

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
      <Campo
        id={`${prefijo}-descripcion`}
        etiqueta="Descripción (opcional)"
        ayuda={`Si la escribes, el cliente verá el botón «Ver descripción» en este servicio. ${valor.descripcion.length}/1000 caracteres.`}
        className="sm:col-span-3"
      >
        <textarea id={`${prefijo}-descripcion`} rows={2} maxLength={1000} placeholder="Qué incluye el servicio, recomendaciones..." value={valor.descripcion} onChange={(e) => setValor({ ...valor, descripcion: e.target.value })} className={CLASE_INPUT} />
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
                  <div className="min-w-0">
                    <h4 className="font-bold text-white">{s.nombre}</h4>
                    <p className="text-xs text-slate-400 flex items-center gap-3 mt-0.5">
                      <span className="flex items-center gap-1"><Clock className="w-3.5 h-3.5 text-amber-400" /> {s.duracion_minutos} min</span>
                      <span className="text-amber-400 font-semibold">{formatearPrecio(s.precio)}</span>
                    </p>
                    {s.descripcion ? (
                      <p className="text-xs text-slate-400 mt-1 line-clamp-2 break-words">{s.descripcion}</p>
                    ) : (
                      <p className="text-xs text-slate-600 mt-1">Sin descripción</p>
                    )}
                  </div>

                  {eliminandoId === s.id ? (
                    <ConfirmarEliminacion
                      texto="El servicio dejará de ofrecerse a los clientes. Las citas pasadas y agendadas no cambian. ¿Continuar?"
                      procesando={procesando}
                      textoConfirmar="Sí, eliminar"
                      onCancelar={() => setEliminandoId(null)}
                      onConfirmar={() => eliminar(s)}
                    />
                  ) : (
                    <div className="flex gap-2">
                      <button
                        onClick={() => {
                          setError('');
                          setMensaje('');
                          setEditando({
                            id: s.id,
                            nombre: s.nombre,
                            duracion_minutos: String(s.duracion_minutos),
                            precio: String(Number(s.precio)),
                            descripcion: s.descripcion || '',
                          });
                        }}
                        className={CLASE_BOTON_EDITAR}
                      >
                        <Pencil className="w-3.5 h-3.5" /> Editar
                      </button>
                      <button
                        onClick={() => setEliminandoId(s.id)}
                        className={CLASE_BOTON_ELIMINAR}
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
  { id: 'estilos', etiqueta: 'Estilos', Icono: Sparkles },
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
        <p className="text-slate-400 text-xs sm:text-sm mt-1">Gestiona los barberos y los catálogos de servicios y estilos.</p>
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
      {seccion === 'estilos' && <PanelEstilos />}
    </div>
  );
}
