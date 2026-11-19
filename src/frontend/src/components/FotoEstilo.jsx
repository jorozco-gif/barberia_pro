import React, { useEffect, useState } from 'react';
import { Sparkles } from 'lucide-react';

// Foto de un estilo (v1.2). La foto es opcional y es una URL externa: si falta o no carga,
// se muestra un recuadro con un ícono en su lugar.
export default function FotoEstilo({ fotoUrl, alt = '', className = 'w-8 h-8 rounded-lg', iconoClassName = 'w-4 h-4' }) {
  const [fallo, setFallo] = useState(false);
  useEffect(() => setFallo(false), [fotoUrl]);

  if (fotoUrl && !fallo) {
    return <img src={fotoUrl} alt={alt} onError={() => setFallo(true)} className={`${className} object-cover`} />;
  }
  return (
    <span
      className={`${className} bg-slate-800 flex items-center justify-center flex-shrink-0`}
      title={fotoUrl ? 'No se pudo cargar la imagen' : undefined}
    >
      <Sparkles className={`${iconoClassName} text-amber-400`} aria-hidden="true" />
    </span>
  );
}
