import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../api';
import { useAuth } from '../AuthContext';
import { useBooking } from '../BookingContext';
import {
  PASO_BARBERO,
  PASO_CONFIRMACION,
  PASO_FECHA_HORA,
  PASO_SERVICIOS,
  cuerpoDeCita,
  pasoMaximo,
} from '../reservaEstado';
import Alerta from './Alerta';
import IndicadorPasos from './reserva/IndicadorPasos';
import PasoBarbero from './reserva/PasoBarbero';
import PasoServicios from './reserva/PasoServicios';
import PasoFechaHora from './reserva/PasoFechaHora';
import PasoConfirmacion from './reserva/PasoConfirmacion';

// Asistente de reserva del cliente (v1.2): Barbero -> Servicios y estilo -> Fecha y hora -> Confirmación.
// Las elecciones viven en BookingContext; aquí se cargan los catálogos, el resumen (RF-15) y los turnos libres
// del día (RF-17), y se envía la cita (RF-19). El backend valida todas las reglas de negocio.
export default function BookingWizard({ onBookingSuccess, onVerMisCitas }) {
  const { usuario } = useAuth();
  const {
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
  } = useBooking();
  const { paso, barbero, serviciosIds, estiloId, fecha, turno } = estado;

  // Catálogos activos: barberos (RF-13), servicios (RF-14) y estilos (RF-34)
  const [catalogo, setCatalogo] = useState({ barberos: [], servicios: [], estilos: [] });
  const [cargandoCatalogo, setCargandoCatalogo] = useState(true);
  const [errorCatalogo, setErrorCatalogo] = useState('');
  const [resumen, setResumen] = useState(null); // { servicios, total, duracion_total_minutos } calculado por el backend
  const [cargandoResumen, setCargandoResumen] = useState(false);
  const [errorResumen, setErrorResumen] = useState('');
  const [turnos, setTurnos] = useState([]);
  const [cargandoTurnos, setCargandoTurnos] = useState(false);
  const [errorTurnos, setErrorTurnos] = useState('');
  const [recargaTurnos, setRecargaTurnos] = useState(0);
  const [enviando, setEnviando] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [limiteAlcanzado, setLimiteAlcanzado] = useState(false);

  const cargarCatalogo = useCallback(async () => {
    setCargandoCatalogo(true);
    setErrorCatalogo('');
    try {
      const [barberos, servicios, estilos] = await Promise.all([api.barberos(), api.servicios(), api.estilos()]);
      const nuevo = { barberos, servicios, estilos };
      setCatalogo(nuevo);
      sincronizarCatalogo(nuevo); // descarta lo que el administrador haya retirado mientras se reservaba
      return nuevo;
    } catch (err) {
      setErrorCatalogo(err.message);
      return null;
    } finally {
      setCargandoCatalogo(false);
    }
  }, [sincronizarCatalogo]);

  useEffect(() => {
    cargarCatalogo();
  }, [cargarCatalogo]);

  // Total y duración de los servicios elegidos: los calcula el backend (RF-15)
  useEffect(() => {
    if (serviciosIds.length === 0) {
      setResumen(null);
      setErrorResumen('');
      return undefined;
    }
    let activo = true;
    setCargandoResumen(true);
    setErrorResumen('');
    api
      .resumenCita(serviciosIds)
      .then((data) => activo && setResumen(data))
      .catch((err) => {
        if (!activo) return;
        setResumen(null);
        setErrorResumen(err.message);
        if (err.status === 404) cargarCatalogo(); // un servicio dejó de estar disponible: se descarta
      })
      .finally(() => activo && setCargandoResumen(false));
    return () => {
      activo = false;
    };
  }, [serviciosIds, cargarCatalogo]);

  // Todos los turnos libres del día para el barbero y la duración total (RF-17, RF-18), sin franja (v1.2).
  // Solo se consultan en el paso de fecha y hora.
  const barberoId = barbero?.id ?? null;
  useEffect(() => {
    if (paso !== PASO_FECHA_HORA) return undefined;
    setErrorTurnos('');
    if (!barberoId || !fecha || serviciosIds.length === 0) {
      setTurnos([]);
      return undefined;
    }
    let activo = true;
    setCargandoTurnos(true);
    api
      .disponibilidad({ barberoId, fecha, serviciosIds })
      .then((data) => {
        if (!activo) return;
        const libres = data.filter((s) => s.disponible);
        setTurnos(libres);
        sincronizarTurnos(libres); // el turno elegido se conserva solo si sigue libre
      })
      .catch((err) => {
        if (!activo) return;
        setTurnos([]);
        setErrorTurnos(err.message);
      })
      .finally(() => activo && setCargandoTurnos(false));
    return () => {
      activo = false;
    };
  }, [paso, barberoId, fecha, serviciosIds, recargaTurnos, sincronizarTurnos]);

  // No se puede estar en un paso cuyo anterior quedó incompleto (por ejemplo, si el administrador retiró el barbero
  // elegido o publicó estilos nuevos mientras el cliente reservaba): se vuelve al primer paso pendiente.
  useEffect(() => {
    const maximo = pasoMaximo(estado, { estilos: catalogo.estilos });
    if (paso > maximo) irAPaso(maximo);
  }, [estado, paso, catalogo.estilos, irAPaso]);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, [paso]);

  const limpiarError = () => {
    setErrorMessage('');
    setLimiteAlcanzado(false);
  };

  const conLimpieza =
    (accion) =>
    (...args) => {
      limpiarError();
      accion(...args);
    };

  const confirmar = async () => {
    limpiarError();
    setEnviando(true);
    try {
      const cita = await api.crearCita(cuerpoDeCita(estado));
      // Éxito: el padre abre el modal y la reserva en curso se reinicia
      onBookingSuccess(cita);
      reiniciar();
    } catch (err) {
      setErrorMessage(err.message);
      const mensaje = err.message || '';
      if (err.status === 409) {
        if (/l[ií]mite/i.test(mensaje)) {
          // Límite de citas programadas (CA-19.2): no se resuelve eligiendo otro horario.
          setLimiteAlcanzado(true);
        } else {
          // Horario ocupado por otra reserva (CA-20.2): volver a elegir con la disponibilidad actualizada.
          descartarTurno();
          irAPaso(PASO_FECHA_HORA);
          setRecargaTurnos((n) => n + 1);
        }
      } else if ((err.status === 400 || err.status === 404) && /estilo/i.test(mensaje)) {
        // Falta el estilo o el elegido se retiró del catálogo (RF-34, PN-14)
        await cargarCatalogo();
        irAPaso(PASO_SERVICIOS);
      } else if (err.status === 404 && /barbero/i.test(mensaje)) {
        await cargarCatalogo();
        irAPaso(PASO_BARBERO);
      } else if (err.status === 404 && /servicio/i.test(mensaje)) {
        await cargarCatalogo();
        irAPaso(PASO_SERVICIOS);
      }
    } finally {
      setEnviando(false);
    }
  };

  const estiloElegido = catalogo.estilos.find((e) => e.id === estiloId) || null;

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <IndicadorPasos paso={paso} onIrAPaso={conLimpieza(irAPaso)} />

      {/* Alertas de error */}
      {errorCatalogo && (
        <Alerta tipo="error" className="mb-6">
          <p>{errorCatalogo}</p>
          <button
            type="button"
            onClick={cargarCatalogo}
            className="mt-2 underline underline-offset-2 hover:text-rose-200 transition"
          >
            Reintentar
          </button>
        </Alerta>
      )}
      {errorMessage && (
        <Alerta tipo="error" className="mb-6">
          <p>{errorMessage}</p>
          {limiteAlcanzado && onVerMisCitas && (
            <button
              type="button"
              onClick={onVerMisCitas}
              className="mt-2 underline underline-offset-2 hover:text-rose-200 transition"
            >
              Ver mis citas
            </button>
          )}
        </Alerta>
      )}

      {paso === PASO_BARBERO && (
        <PasoBarbero
          barberos={catalogo.barberos}
          cargando={cargandoCatalogo}
          barberoId={barberoId}
          onElegir={conLimpieza(elegirBarbero)}
          onSiguiente={() => irAPaso(PASO_SERVICIOS)}
        />
      )}

      {paso === PASO_SERVICIOS && (
        <PasoServicios
          barbero={barbero}
          servicios={catalogo.servicios}
          estilos={catalogo.estilos}
          cargando={cargandoCatalogo}
          serviciosIds={serviciosIds}
          estiloId={estiloId}
          resumen={resumen}
          cargandoResumen={cargandoResumen}
          errorResumen={errorResumen}
          onAlternarServicio={conLimpieza(alternarServicio)}
          onElegirEstilo={conLimpieza(elegirEstilo)}
          onAnterior={() => irAPaso(PASO_BARBERO)}
          onSiguiente={() => irAPaso(PASO_FECHA_HORA)}
        />
      )}

      {paso === PASO_FECHA_HORA && (
        <PasoFechaHora
          barbero={barbero}
          fecha={fecha}
          duracionTotal={resumen?.duracion_total_minutos}
          turnos={turnos}
          cargando={cargandoTurnos}
          error={errorTurnos}
          turno={turno}
          onCambiarFecha={conLimpieza(elegirFecha)}
          onElegirTurno={conLimpieza(elegirTurno)}
          onReintentar={() => setRecargaTurnos((n) => n + 1)}
          onAnterior={() => irAPaso(PASO_SERVICIOS)}
          onSiguiente={() => irAPaso(PASO_CONFIRMACION)}
        />
      )}

      {paso === PASO_CONFIRMACION && (
        <PasoConfirmacion
          usuario={usuario}
          barbero={barbero}
          resumen={resumen}
          estilo={estiloElegido}
          fecha={fecha}
          turno={turno}
          enviando={enviando}
          onAnterior={() => irAPaso(PASO_FECHA_HORA)}
          onConfirmar={confirmar}
        />
      )}
    </div>
  );
}
