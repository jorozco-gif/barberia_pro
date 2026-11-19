import React, { useCallback, useEffect, useState } from 'react';
import { Pencil, Plus, Trash2 } from 'lucide-react';
import { api } from '../../api';
import Alerta from '../Alerta';
import FotoEstilo from '../FotoEstilo';
import {
  CLASE_BOTON_EDITAR,
  CLASE_BOTON_ELIMINAR,
  CLASE_BOTON_PRIMARIO,
  CLASE_BOTON_SECUNDARIO,
  CLASE_INPUT,
  Campo,
  ConfirmarEliminacion,
} from './comunes';

// ---------------------------------------------------------------------------
// Estilos (v1.2, RF-33): listar, crear, editar y eliminar (baja lógica) el catálogo de estilos que el cliente
// elige al reservar (RF-34). Nombre y descripción son obligatorios; la foto es opcional (URL, como la del barbero).
// ---------------------------------------------------------------------------
const ESTILO_VACIO = { nombre: '', descripcion: '', foto_url: '' };
const MAX_DESCRIPCION = 1000;

const aPayload = (f) => ({
  nombre: f.nombre.trim(),
  descripcion: f.descripcion.trim(),
  foto_url: f.foto_url.trim() || null,
});

function MiniaturaEstilo({ fotoUrl, nombre, className = 'w-14 h-14' }) {
  return (
    <FotoEstilo
      fotoUrl={fotoUrl}
      alt={nombre || 'Vista previa'}
      className={`${className} rounded-xl border border-slate-700 flex-shrink-0`}
      iconoClassName="w-5 h-5"
    />
  );
}

function CamposEstilo({ valor, setValor, prefijo }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-[auto_1fr] gap-4">
      <div className="hidden sm:block pt-6">
        <MiniaturaEstilo fotoUrl={valor.foto_url.trim()} nombre={valor.nombre} className="w-20 h-20" />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Campo id={`${prefijo}-nombre`} etiqueta="Nombre">
          <input
            id={`${prefijo}-nombre`}
            required
            minLength={2}
            maxLength={100}
            placeholder="Ej: Fade bajo"
            value={valor.nombre}
            onChange={(e) => setValor({ ...valor, nombre: e.target.value })}
            className={CLASE_INPUT}
          />
        </Campo>
        <Campo id={`${prefijo}-foto`} etiqueta="URL de la foto (opcional)">
          <input
            id={`${prefijo}-foto`}
            type="url"
            maxLength={255}
            placeholder="https://..."
            value={valor.foto_url}
            onChange={(e) => setValor({ ...valor, foto_url: e.target.value })}
            className={CLASE_INPUT}
          />
        </Campo>
        <Campo
          id={`${prefijo}-descripcion`}
          etiqueta="Descripción"
          ayuda={`Se muestra al cliente en la ventana «Ver descripción». ${valor.descripcion.length}/${MAX_DESCRIPCION} caracteres.`}
          className="sm:col-span-2"
        >
          <textarea
            id={`${prefijo}-descripcion`}
            required
            rows={3}
            maxLength={MAX_DESCRIPCION}
            placeholder="Describe el corte: cómo queda, para quién es ideal, mantenimiento..."
            value={valor.descripcion}
            onChange={(e) => setValor({ ...valor, descripcion: e.target.value })}
            className={CLASE_INPUT}
          />
        </Campo>
      </div>
    </div>
  );
}

export default function PanelEstilos() {
  const [estilos, setEstilos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [mensaje, setMensaje] = useState('');
  const [nuevo, setNuevo] = useState(ESTILO_VACIO);
  const [creando, setCreando] = useState(false);
  const [editando, setEditando] = useState(null); // { id, nombre, descripcion, foto_url }
  const [guardando, setGuardando] = useState(false);
  const [eliminandoId, setEliminandoId] = useState(null); // confirmación pendiente
  const [procesando, setProcesando] = useState(false);

  const cargar = useCallback(async () => {
    try {
      setEstilos(await api.estilos());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const limpiarAvisos = () => {
    setError('');
    setMensaje('');
  };

  const crear = async (e) => {
    e.preventDefault();
    limpiarAvisos();
    setCreando(true);
    try {
      const creado = await api.adminCrearEstilo(aPayload(nuevo));
      setNuevo(ESTILO_VACIO);
      setMensaje(`Estilo ${creado.nombre} agregado. Los clientes ya pueden elegirlo al reservar.`);
      await cargar();
    } catch (err) {
      setError(err.message);
    } finally {
      setCreando(false);
    }
  };

  const guardar = async (e) => {
    e.preventDefault();
    limpiarAvisos();
    setGuardando(true);
    try {
      await api.adminActualizarEstilo(editando.id, aPayload(editando));
      setEditando(null);
      setMensaje('Estilo actualizado.');
      await cargar();
    } catch (err) {
      setError(err.message);
      if (err.status === 404) {
        setEditando(null); // otro administrador lo eliminó
        await cargar();
      }
    } finally {
      setGuardando(false);
    }
  };

  const eliminar = async (estilo) => {
    limpiarAvisos();
    setProcesando(true);
    try {
      await api.adminEliminarEstilo(estilo.id);
      setEliminandoId(null);
      setMensaje(`El estilo ${estilo.nombre} ya no se ofrece a los clientes. Las citas que lo eligieron lo conservan.`);
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
        <h3 className="font-bold text-sm text-slate-300 uppercase tracking-wider mb-1">Agregar estilo</h3>
        <p className="text-xs text-slate-500 mb-4">
          Si hay al menos un estilo activo, el cliente debe elegir uno al reservar. Sin estilos, la reserva continúa sin
          este paso.
        </p>
        <CamposEstilo valor={nuevo} setValor={setNuevo} prefijo="est-nuevo" />
        <div className="mt-4 flex justify-end">
          <button type="submit" disabled={creando} className={CLASE_BOTON_PRIMARIO}>
            <Plus className="w-4 h-4" /> {creando ? 'Agregando...' : 'Agregar estilo'}
          </button>
        </div>
      </form>

      <Alerta tipo="error">{error}</Alerta>
      <Alerta tipo="exito">{mensaje}</Alerta>

      {loading ? (
        <div className="py-12 text-center text-slate-400 text-sm">Cargando estilos...</div>
      ) : estilos.length === 0 ? (
        <div className="py-12 text-center text-slate-500 text-sm">
          No hay estilos en el catálogo. Los clientes reservan sin elegir estilo.
        </div>
      ) : (
        <div className="space-y-3">
          {estilos.map((estilo) => (
            <div key={estilo.id} className="p-4 rounded-2xl bg-slate-900 border border-slate-800">
              {editando?.id === estilo.id ? (
                <form onSubmit={guardar} className="space-y-4">
                  <CamposEstilo valor={editando} setValor={setEditando} prefijo={`est-${estilo.id}`} />
                  <div className="flex justify-end gap-2">
                    <button type="button" onClick={() => setEditando(null)} className={CLASE_BOTON_SECUNDARIO}>
                      Cancelar
                    </button>
                    <button type="submit" disabled={guardando} className={CLASE_BOTON_PRIMARIO}>
                      {guardando ? 'Guardando...' : 'Guardar cambios'}
                    </button>
                  </div>
                </form>
              ) : (
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-start gap-3 min-w-0">
                    <MiniaturaEstilo fotoUrl={estilo.foto_url} nombre={estilo.nombre} />
                    <div className="min-w-0">
                      <h4 className="font-bold text-white">{estilo.nombre}</h4>
                      <p className="text-xs text-slate-400 mt-0.5 line-clamp-2 break-words">{estilo.descripcion}</p>
                    </div>
                  </div>

                  {eliminandoId === estilo.id ? (
                    <ConfirmarEliminacion
                      texto="El estilo dejará de ofrecerse a los clientes. Las citas que ya lo eligieron lo conservan. ¿Continuar?"
                      procesando={procesando}
                      textoConfirmar="Sí, eliminar"
                      onCancelar={() => setEliminandoId(null)}
                      onConfirmar={() => eliminar(estilo)}
                    />
                  ) : (
                    <div className="flex gap-2 flex-shrink-0">
                      <button
                        type="button"
                        onClick={() => {
                          limpiarAvisos();
                          setEditando({
                            id: estilo.id,
                            nombre: estilo.nombre,
                            descripcion: estilo.descripcion || '',
                            foto_url: estilo.foto_url || '',
                          });
                        }}
                        className={CLASE_BOTON_EDITAR}
                      >
                        <Pencil className="w-3.5 h-3.5" /> Editar
                      </button>
                      <button type="button" onClick={() => setEliminandoId(estilo.id)} className={CLASE_BOTON_ELIMINAR}>
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
