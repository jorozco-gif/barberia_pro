import React, { useCallback, useState } from 'react';
import { Check, Clock, Info, Sparkles } from 'lucide-react';
import { formatearPrecio } from '../../formato';
import Alerta from '../Alerta';
import FotoEstilo from '../FotoEstilo';
import ModalDescripcion from '../ModalDescripcion';
import { BotonAnterior, BotonSiguiente, Cargando, EncabezadoPaso, Vacio, claseTarjeta } from './comunes';

function EstadoEleccion({ elegido, textoNoElegido = 'Elegir' }) {
  return (
    <span className={`font-semibold inline-flex items-center gap-1 ${elegido ? 'text-amber-400' : 'text-slate-500'}`}>
      {elegido ? (
        <>
          Seleccionado <Check className="w-3.5 h-3.5" />
        </>
      ) : (
        textoNoElegido
      )}
    </span>
  );
}

function BotonDescripcion({ nombre, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={`Ver descripción de ${nombre}`}
      aria-haspopup="dialog"
      className="inline-flex items-center gap-1.5 text-xs font-medium text-sky-300 hover:text-sky-200 transition rounded-md focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-400"
    >
      <Info className="w-4 h-4" /> Ver descripción
    </button>
  );
}

function TarjetaServicio({ servicio, elegido, onAlternar, onVerDescripcion }) {
  return (
    <div className={`rounded-2xl border transition flex flex-col ${claseTarjeta(elegido)}`}>
      <button
        type="button"
        onClick={() => onAlternar(servicio.id)}
        aria-pressed={elegido}
        className="p-5 pb-4 text-left flex flex-col rounded-2xl focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
      >
        <div className="flex items-start justify-between w-full gap-3">
          <h3 className="font-bold text-lg text-white">{servicio.nombre}</h3>
          <span className="text-amber-400 font-bold text-lg whitespace-nowrap">{formatearPrecio(servicio.precio)}</span>
        </div>
        <div className="flex items-center justify-between mt-4 pt-3 border-t border-slate-800 text-xs text-slate-400 w-full">
          <span className="flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-amber-400" /> {servicio.duracion_minutos} minutos
          </span>
          <EstadoEleccion elegido={elegido} />
        </div>
      </button>
      {servicio.descripcion && (
        <div className="px-5 pb-4 -mt-1">
          <BotonDescripcion nombre={servicio.nombre} onClick={() => onVerDescripcion(servicio)} />
        </div>
      )}
    </div>
  );
}

function TarjetaEstilo({ estilo, elegido, onElegir, onVerDescripcion }) {
  return (
    <div className={`rounded-2xl border transition flex flex-col overflow-hidden ${claseTarjeta(elegido)}`}>
      <button
        type="button"
        onClick={() => onElegir(estilo.id)}
        aria-pressed={elegido}
        className="text-left flex-1 flex flex-col focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-amber-500"
      >
        <FotoEstilo
          fotoUrl={estilo.foto_url}
          alt={estilo.nombre}
          className="w-full h-28 border-b border-slate-800"
          iconoClassName="w-8 h-8 opacity-70"
        />
        <div className="px-4 pt-3 pb-2 flex items-start justify-between gap-2 text-xs">
          <h4 className="font-bold text-sm text-white">{estilo.nombre}</h4>
          <EstadoEleccion elegido={elegido} />
        </div>
      </button>
      <div className="px-4 pb-3">
        <BotonDescripcion nombre={estilo.nombre} onClick={() => onVerDescripcion(estilo)} />
      </div>
    </div>
  );
}

// Paso 2 (v1.2): servicios (RF-14, con su descripción opcional en un modal) y estilo del corte (RF-34).
export default function PasoServicios({
  barbero,
  servicios,
  estilos,
  cargando,
  serviciosIds,
  estiloId,
  resumen,
  cargandoResumen,
  errorResumen,
  onAlternarServicio,
  onElegirEstilo,
  onAnterior,
  onSiguiente,
}) {
  const [detalle, setDetalle] = useState(null); // { tipo: 'Servicio' | 'Estilo', item }
  const cerrarDetalle = useCallback(() => setDetalle(null), []);

  const hayEstilos = estilos.length > 0;
  const estiloElegido = estilos.find((e) => e.id === estiloId) || null;
  const faltaEstilo = hayEstilos && !estiloElegido;
  const cantidad = serviciosIds.length;
  const puedeSeguir = cantidad > 0 && !faltaEstilo && Boolean(resumen) && !cargandoResumen;

  const pendientes = [];
  if (cantidad === 0) pendientes.push('al menos un servicio');
  if (faltaEstilo) pendientes.push('tu estilo');

  return (
    <div>
      <EncabezadoPaso titulo="Selecciona tus Servicios">
        {barbero ? `Con ${barbero.nombre}. ` : ''}Puedes elegir uno o varios servicios para la misma cita.
      </EncabezadoPaso>

      {cargando ? (
        <Cargando>Cargando servicios...</Cargando>
      ) : servicios.length === 0 ? (
        <Vacio>No hay servicios disponibles por el momento.</Vacio>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {servicios.map((s) => (
            <TarjetaServicio
              key={s.id}
              servicio={s}
              elegido={serviciosIds.includes(s.id)}
              onAlternar={onAlternarServicio}
              onVerDescripcion={(item) => setDetalle({ tipo: 'Servicio', item })}
            />
          ))}
        </div>
      )}

      {/* Estilo del corte (RF-34): reemplaza a las notas libres de versiones anteriores */}
      {!cargando && hayEstilos && (
        <section className="mt-8" aria-labelledby="titulo-estilos">
          <div className="mb-4">
            <h3 id="titulo-estilos" className="text-lg font-bold text-white flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-amber-400" /> Elige tu estilo
            </h3>
            <p className="text-slate-400 text-sm mt-0.5">
              Indica cómo quieres el resultado. Pulsa «Ver descripción» para conocer cada estilo.
            </p>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3" role="group" aria-labelledby="titulo-estilos">
            {estilos.map((e) => (
              <TarjetaEstilo
                key={e.id}
                estilo={e}
                elegido={estiloId === e.id}
                onElegir={onElegirEstilo}
                onVerDescripcion={(item) => setDetalle({ tipo: 'Estilo', item })}
              />
            ))}
          </div>
        </section>
      )}

      {/* Resumen calculado por el backend (RF-15) */}
      <div className="mt-6 bg-slate-900 border border-slate-800 rounded-2xl p-5">
        <Alerta tipo="error" className="mb-3">{errorResumen}</Alerta>
        <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
          <div className="text-slate-400 space-y-0.5">
            <p>
              {cantidad === 0
                ? 'Aún no eliges servicios.'
                : `${cantidad} ${cantidad === 1 ? 'servicio elegido' : 'servicios elegidos'}`}
            </p>
            {hayEstilos && (
              <p>
                Estilo: <strong className="text-white">{estiloElegido ? estiloElegido.nombre : 'sin elegir'}</strong>
              </p>
            )}
          </div>
          <div className="flex items-center gap-6">
            <span className="text-slate-400">
              Duración total:{' '}
              <strong className="text-white">{cantidad === 0 ? '0' : resumen?.duracion_total_minutos ?? '...'} min</strong>
            </span>
            <span className="text-slate-400">
              Total:{' '}
              <strong className="text-emerald-400 text-lg">
                {cantidad === 0 ? '$0' : resumen ? formatearPrecio(resumen.total) : '...'}
              </strong>
            </span>
          </div>
        </div>
        {pendientes.length > 0 && !cargando && (
          <p className="text-xs text-amber-300/90 mt-3">Para continuar, elige {pendientes.join(' y ')}.</p>
        )}
      </div>

      <div className="mt-8 flex justify-between">
        <BotonAnterior onClick={onAnterior}>Volver a Barberos</BotonAnterior>
        <BotonSiguiente disabled={!puedeSeguir} onClick={onSiguiente}>
          Siguiente: Fecha y Hora
        </BotonSiguiente>
      </div>

      {detalle && (
        <ModalDescripcion
          subtitulo={detalle.tipo}
          titulo={detalle.item.nombre}
          descripcion={detalle.item.descripcion}
          imagenUrl={detalle.tipo === 'Estilo' ? detalle.item.foto_url : null}
          onCerrar={cerrarDetalle}
        />
      )}
    </div>
  );
}
