import React, { createContext, useCallback, useContext, useEffect, useMemo, useReducer } from 'react';
import { useAuth } from './AuthContext';
import { ACCIONES, crearEstadoInicial, reservaReducer } from './reservaEstado';

// Estado global de la reserva en curso del cliente (v1.2): barbero, servicios, estilo (RF-34), fecha y turno.
// Vive fuera de BookingWizard para que la reserva no se pierda si el cliente cambia de pestaña (por ejemplo,
// a Mis Citas) y vuelve. Se reinicia al cambiar de usuario o al cerrar la sesión, y después de agendar.

const BookingContext = createContext(null);

export function BookingProvider({ children }) {
  const { usuario } = useAuth();
  const [estado, dispatch] = useReducer(reservaReducer, undefined, () => crearEstadoInicial());

  const usuarioId = usuario?.id ?? null;
  useEffect(() => {
    dispatch({ type: ACCIONES.REINICIAR }); // la reserva a medias no pasa de una cuenta a otra
  }, [usuarioId]);

  const elegirBarbero = useCallback((barbero) => dispatch({ type: ACCIONES.ELEGIR_BARBERO, barbero }), []);
  const alternarServicio = useCallback((id) => dispatch({ type: ACCIONES.ALTERNAR_SERVICIO, id }), []);
  const elegirEstilo = useCallback((id) => dispatch({ type: ACCIONES.ELEGIR_ESTILO, id }), []);
  const elegirFecha = useCallback((fecha) => dispatch({ type: ACCIONES.ELEGIR_FECHA, fecha }), []);
  const elegirTurno = useCallback((turno) => dispatch({ type: ACCIONES.ELEGIR_TURNO, turno }), []);
  const descartarTurno = useCallback(() => dispatch({ type: ACCIONES.DESCARTAR_TURNO }), []);
  const sincronizarTurnos = useCallback((libres) => dispatch({ type: ACCIONES.SINCRONIZAR_TURNOS, libres }), []);
  const sincronizarCatalogo = useCallback(
    (catalogo) => dispatch({ type: ACCIONES.SINCRONIZAR_CATALOGO, catalogo }),
    [],
  );
  const irAPaso = useCallback((paso) => dispatch({ type: ACCIONES.IR_A_PASO, paso }), []);
  const reiniciar = useCallback(() => dispatch({ type: ACCIONES.REINICIAR }), []);

  const valor = useMemo(
    () => ({
      estado,
      elegirBarbero,
      alternarServicio,
      elegirEstilo,
      elegirFecha,
      elegirTurno,
      descartarTurno,
      sincronizarTurnos,
      sincronizarCatalogo,
      irAPaso,
      reiniciar,
    }),
    [estado, elegirBarbero, alternarServicio, elegirEstilo, elegirFecha, elegirTurno, descartarTurno,
      sincronizarTurnos, sincronizarCatalogo, irAPaso, reiniciar],
  );

  return <BookingContext.Provider value={valor}>{children}</BookingContext.Provider>;
}

export function useBooking() {
  const contexto = useContext(BookingContext);
  if (!contexto) throw new Error('useBooking debe usarse dentro de <BookingProvider>.');
  return contexto;
}
