import React, { useEffect, useState } from 'react';
import { Scissors, LogIn, UserPlus, KeyRound, ArrowLeft } from 'lucide-react';
import { api, ApiError } from '../api';
import { useAuth } from '../AuthContext';
import { formatearFecha } from '../formato';
import Alerta from './Alerta';

const CLASE_INPUT =
  'w-full px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-white placeholder-slate-600 focus:border-amber-500 focus:outline-none';
const CLASE_LABEL = 'block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5';
const CLASE_BOTON =
  'w-full py-3 bg-amber-500 hover:bg-amber-400 disabled:opacity-50 disabled:hover:bg-amber-500 text-slate-950 font-bold rounded-xl transition shadow-lg shadow-amber-500/20 flex items-center justify-center gap-2';

function Tarjeta({ icono: Icono, titulo, subtitulo, children }) {
  return (
    <div className="max-w-md mx-auto px-4 py-10">
      <div className="text-center mb-6">
        <div className="w-14 h-14 rounded-2xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center mx-auto text-amber-400 mb-4">
          <Icono className="w-7 h-7" />
        </div>
        <h2 className="text-2xl font-bold text-white">{titulo}</h2>
        {subtitulo && <p className="text-slate-400 text-sm mt-1">{subtitulo}</p>}
      </div>
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4">{children}</div>
    </div>
  );
}

function EnlaceTexto({ onClick, children }) {
  return (
    <button type="button" onClick={onClick} className="text-amber-400 hover:text-amber-300 font-medium transition">
      {children}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Inicio de sesión (RF-02, RF-30)
// ---------------------------------------------------------------------------
function Login({ emailInicial, aviso, onCambiarVista }) {
  const { iniciarSesion, avisoSesion } = useAuth();
  const [email, setEmail] = useState(emailInicial || '');
  const [password, setPassword] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState(null);

  const enviar = async (e) => {
    e.preventDefault();
    setError(null);
    setEnviando(true);
    try {
      await iniciarSesion(email.trim(), password);
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, 'No se pudo iniciar sesión. Inténtalo de nuevo.'));
      setEnviando(false);
    }
  };

  return (
    <Tarjeta icono={LogIn} titulo="Iniciar sesión" subtitulo="Ingresa con tu correo y contraseña para continuar.">
      {aviso && <Alerta tipo="exito">{aviso}</Alerta>}
      {avisoSesion && <Alerta tipo="aviso">{avisoSesion}</Alerta>}

      {error &&
        (error.status === 403 && error.suspendidoHasta ? (
          <Alerta tipo="aviso" titulo="Cuenta suspendida">
            <p>{error.message}</p>
            <p className="mt-1">Fecha de reactivación: <strong>{formatearFecha(error.suspendidoHasta)}</strong></p>
          </Alerta>
        ) : (
          <Alerta tipo="error">{error.message}</Alerta>
        ))}

      <form onSubmit={enviar} className="space-y-4">
        <div>
          <label htmlFor="login-email" className={CLASE_LABEL}>Correo electrónico</label>
          <input
            id="login-email"
            type="email"
            required
            autoComplete="email"
            placeholder="correo@ejemplo.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={CLASE_INPUT}
          />
        </div>
        <div>
          <label htmlFor="login-password" className={CLASE_LABEL}>Contraseña</label>
          <input
            id="login-password"
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={CLASE_INPUT}
          />
        </div>
        <button type="submit" disabled={enviando} className={CLASE_BOTON}>
          {enviando ? 'Ingresando...' : 'Ingresar'}
        </button>
      </form>

      <div className="flex flex-col items-center gap-2 text-sm text-slate-400 pt-2">
        <EnlaceTexto onClick={() => onCambiarVista('recuperar')}>¿Olvidaste tu contraseña?</EnlaceTexto>
        <span>
          ¿No tienes cuenta? <EnlaceTexto onClick={() => onCambiarVista('registro')}>Regístrate</EnlaceTexto>
        </span>
      </div>
    </Tarjeta>
  );
}

// ---------------------------------------------------------------------------
// Registro de clientes (RF-01) con aviso de privacidad y autorización (RNF-06)
// ---------------------------------------------------------------------------
function Registro({ onCambiarVista, onRegistrado }) {
  const [form, setForm] = useState({ nombre: '', telefono: '', email: '', password: '' });
  const [acepta, setAcepta] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState('');

  const cambiar = (campo) => (e) => setForm({ ...form, [campo]: e.target.value });

  const enviar = async (e) => {
    e.preventDefault();
    setError('');
    setEnviando(true);
    try {
      await api.registro({
        nombre: form.nombre.trim(),
        telefono: form.telefono.trim(),
        email: form.email.trim(),
        password: form.password,
        acepta_tratamiento_datos: acepta,
      });
      onRegistrado(form.email.trim());
    } catch (err) {
      setError(err.message);
      setEnviando(false);
    }
  };

  return (
    <Tarjeta icono={UserPlus} titulo="Crear cuenta" subtitulo="Regístrate como cliente para agendar y gestionar tus citas.">
      <Alerta tipo="error">{error}</Alerta>
      <form onSubmit={enviar} className="space-y-4">
        <div>
          <label htmlFor="reg-nombre" className={CLASE_LABEL}>Nombre completo</label>
          <input id="reg-nombre" type="text" required minLength={2} maxLength={120} autoComplete="name" placeholder="Ej: Carlos Mendoza" value={form.nombre} onChange={cambiar('nombre')} className={CLASE_INPUT} />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label htmlFor="reg-telefono" className={CLASE_LABEL}>Teléfono móvil</label>
            <input id="reg-telefono" type="tel" required minLength={7} maxLength={25} autoComplete="tel" placeholder="3001234567" value={form.telefono} onChange={cambiar('telefono')} className={CLASE_INPUT} />
          </div>
          <div>
            <label htmlFor="reg-email" className={CLASE_LABEL}>Correo electrónico</label>
            <input id="reg-email" type="email" required autoComplete="email" placeholder="carlos@example.com" value={form.email} onChange={cambiar('email')} className={CLASE_INPUT} />
          </div>
        </div>
        <div>
          <label htmlFor="reg-password" className={CLASE_LABEL}>Contraseña</label>
          <input id="reg-password" type="password" required minLength={8} maxLength={128} autoComplete="new-password" placeholder="Mínimo 8 caracteres" value={form.password} onChange={cambiar('password')} className={CLASE_INPUT} />
        </div>

        <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-4 text-xs text-slate-400 leading-relaxed">
          <p className="font-semibold text-slate-300 mb-1">Aviso de privacidad</p>
          <p>
            BarberShop Pro usará tu nombre, teléfono y correo electrónico para crear tu cuenta, gestionar tus citas y
            enviarte las notificaciones relacionadas con ellas, conforme a la Ley 1581 de 2012 de protección de datos
            personales.
          </p>
          <label className="flex items-start gap-2 mt-3 text-slate-300 cursor-pointer">
            <input
              type="checkbox"
              checked={acepta}
              onChange={(e) => setAcepta(e.target.checked)}
              className="mt-0.5 accent-amber-500"
            />
            <span>Autorizo el tratamiento de mis datos personales para las finalidades indicadas.</span>
          </label>
        </div>

        <button type="submit" disabled={enviando || !acepta} className={CLASE_BOTON}>
          {enviando ? 'Creando cuenta...' : 'Crear cuenta'}
        </button>
      </form>
      <p className="text-sm text-slate-400 text-center">
        ¿Ya tienes cuenta? <EnlaceTexto onClick={() => onCambiarVista('login')}>Inicia sesión</EnlaceTexto>
      </p>
    </Tarjeta>
  );
}

// ---------------------------------------------------------------------------
// Solicitud de recuperación de contraseña (RF-04)
// ---------------------------------------------------------------------------
function Recuperar({ onCambiarVista }) {
  const [email, setEmail] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState('');
  const [mensaje, setMensaje] = useState('');

  const enviar = async (e) => {
    e.preventDefault();
    setError('');
    setMensaje('');
    setEnviando(true);
    try {
      const respuesta = await api.recuperar(email.trim());
      setMensaje(respuesta?.detail || 'Si el correo está registrado, recibirás un enlace para restablecer tu contraseña.');
    } catch (err) {
      setError(err.message);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <Tarjeta icono={KeyRound} titulo="Recuperar contraseña" subtitulo="Te enviaremos un enlace por correo para definir una nueva contraseña.">
      <Alerta tipo="error">{error}</Alerta>
      {mensaje && <Alerta tipo="exito">{mensaje}</Alerta>}
      <form onSubmit={enviar} className="space-y-4">
        <div>
          <label htmlFor="rec-email" className={CLASE_LABEL}>Correo electrónico</label>
          <input id="rec-email" type="email" required autoComplete="email" placeholder="correo@ejemplo.com" value={email} onChange={(e) => setEmail(e.target.value)} className={CLASE_INPUT} />
        </div>
        <button type="submit" disabled={enviando} className={CLASE_BOTON}>
          {enviando ? 'Enviando...' : 'Enviar enlace'}
        </button>
      </form>
      <button
        type="button"
        onClick={() => onCambiarVista('login')}
        className="text-sm text-slate-400 hover:text-white flex items-center gap-1.5 mx-auto transition"
      >
        <ArrowLeft className="w-4 h-4" /> Volver a iniciar sesión
      </button>
    </Tarjeta>
  );
}

// ---------------------------------------------------------------------------
// Pantalla de acceso (sin sesión): inicio de sesión, registro y recuperación
// ---------------------------------------------------------------------------
export default function AuthPage() {
  const [vista, setVista] = useState('login');
  const [emailRegistrado, setEmailRegistrado] = useState('');
  const [aviso, setAviso] = useState('');

  if (vista === 'registro') {
    return (
      <Registro
        onCambiarVista={setVista}
        onRegistrado={(email) => {
          setEmailRegistrado(email);
          setAviso('Tu cuenta fue creada. Ya puedes iniciar sesión.');
          setVista('login');
        }}
      />
    );
  }
  if (vista === 'recuperar') return <Recuperar onCambiarVista={setVista} />;
  return <Login emailInicial={emailRegistrado} aviso={aviso} onCambiarVista={(v) => { setAviso(''); setVista(v); }} />;
}

// ---------------------------------------------------------------------------
// Restablecimiento de contraseña: se abre desde el enlace del correo (/restablecer?token=...) (RF-04)
// `onTerminar(restablecida)` se invoca al salir de la pantalla; `restablecida` indica si la contraseña cambió.
// ---------------------------------------------------------------------------
export function ResetPasswordPage({ token, onTerminar }) {
  const [estado, setEstado] = useState('validando'); // validando | valido | invalido | listo
  const [errorEnlace, setErrorEnlace] = useState('');
  const [password, setPassword] = useState('');
  const [repetir, setRepetir] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let activo = true;
    if (!token) {
      setErrorEnlace('El enlace no es válido.');
      setEstado('invalido');
      return undefined;
    }
    api
      .validarEnlaceRecuperacion(token)
      .then(() => activo && setEstado('valido'))
      .catch((err) => {
        if (!activo) return;
        setErrorEnlace(err.message);
        setEstado('invalido');
      });
    return () => {
      activo = false;
    };
  }, [token]);

  const enviar = async (e) => {
    e.preventDefault();
    setError('');
    if (password !== repetir) {
      setError('Las contraseñas no coinciden.');
      return;
    }
    setEnviando(true);
    try {
      await api.restablecer(token, password);
      setEstado('listo');
    } catch (err) {
      setError(err.message);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <Tarjeta icono={KeyRound} titulo="Restablecer contraseña" subtitulo="Define una nueva contraseña para tu cuenta.">
      {estado === 'validando' && <p className="text-sm text-slate-400 text-center">Verificando el enlace...</p>}

      {estado === 'invalido' && (
        <>
          <Alerta tipo="error">{errorEnlace}</Alerta>
          <button type="button" onClick={() => onTerminar(false)} className={CLASE_BOTON}>
            Volver al inicio de sesión
          </button>
        </>
      )}

      {estado === 'valido' && (
        <form onSubmit={enviar} className="space-y-4">
          <Alerta tipo="error">{error}</Alerta>
          <div>
            <label htmlFor="rst-password" className={CLASE_LABEL}>Nueva contraseña</label>
            <input id="rst-password" type="password" required minLength={8} maxLength={128} autoComplete="new-password" placeholder="Mínimo 8 caracteres" value={password} onChange={(e) => setPassword(e.target.value)} className={CLASE_INPUT} />
          </div>
          <div>
            <label htmlFor="rst-repetir" className={CLASE_LABEL}>Repite la contraseña</label>
            <input id="rst-repetir" type="password" required minLength={8} maxLength={128} autoComplete="new-password" value={repetir} onChange={(e) => setRepetir(e.target.value)} className={CLASE_INPUT} />
          </div>
          <button type="submit" disabled={enviando} className={CLASE_BOTON}>
            {enviando ? 'Guardando...' : 'Guardar contraseña'}
          </button>
        </form>
      )}

      {estado === 'listo' && (
        <>
          <Alerta tipo="exito">Tu contraseña fue actualizada. Ya puedes iniciar sesión con la nueva contraseña.</Alerta>
          <button type="button" onClick={() => onTerminar(true)} className={CLASE_BOTON}>
            <Scissors className="w-4 h-4 rotate-45" /> Ir a iniciar sesión
          </button>
        </>
      )}
    </Tarjeta>
  );
}
