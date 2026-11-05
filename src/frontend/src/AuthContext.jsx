import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import {
  api,
  guardarSesion,
  limpiarSesion,
  obtenerToken,
  obtenerUsuarioGuardado,
  registrarAlExpirarSesion,
} from './api';

// Estado global de autenticación: usuario en sesión (con su rol), inicio y cierre de sesión,
// y aviso cuando el backend invalida la sesión (401: inactividad de 15 min, sesión cerrada o inválida).
// El backend no tiene un endpoint /me: la validez del token se comprueba con la primera petición protegida.

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [usuario, setUsuario] = useState(() => (obtenerToken() ? obtenerUsuarioGuardado() : null));
  const [avisoSesion, setAvisoSesion] = useState('');

  useEffect(
    () =>
      registrarAlExpirarSesion((mensaje) => {
        setUsuario(null);
        setAvisoSesion(mensaje || 'Tu sesión expiró. Inicia sesión de nuevo.');
      }),
    [],
  );

  const iniciarSesion = useCallback(async (email, password) => {
    const respuesta = await api.login(email, password);
    guardarSesion(respuesta.access_token, respuesta.usuario);
    setAvisoSesion('');
    setUsuario(respuesta.usuario);
    return respuesta.usuario;
  }, []);

  const cerrarSesion = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      // Si la sesión ya no es válida o no hay conexión, igualmente se descarta la sesión local.
    }
    limpiarSesion();
    setAvisoSesion('');
    setUsuario(null);
  }, []);

  const descartarSesionLocal = useCallback(() => {
    limpiarSesion();
    setUsuario(null);
  }, []);

  const valor = useMemo(
    () => ({
      usuario,
      rol: usuario?.rol ?? null,
      avisoSesion,
      limpiarAviso: () => setAvisoSesion(''),
      iniciarSesion,
      cerrarSesion,
      descartarSesionLocal,
    }),
    [usuario, avisoSesion, iniciarSesion, cerrarSesion, descartarSesionLocal],
  );

  return <AuthContext.Provider value={valor}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const contexto = useContext(AuthContext);
  if (!contexto) throw new Error('useAuth debe usarse dentro de <AuthProvider>.');
  return contexto;
}
