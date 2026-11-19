"""Plantillas de los correos de BarberShop Pro: una sola presentación para todos los mensajes.

Cada mensaje se describe con un `ContenidoCorreo` (título, saludo, párrafos, tabla de datos, botón y
avisos) y se convierte en dos versiones: HTML (a_html) y texto plano (a_texto), para los clientes de
correo que no muestran HTML. Así ambas versiones dicen siempre lo mismo.

El HTML usa tablas y estilos en línea porque es lo que soportan de forma fiable Gmail, Outlook y los
clientes móviles; el ancho se adapta a pantallas pequeñas. No carga imágenes ni recursos externos (el
proyecto no tiene logotipo): el nombre del negocio se muestra como texto con los colores de la interfaz.
Todo texto que viene de la base de datos (nombres, servicios) se escapa antes de entrar al HTML.
Este módulo no envía nada: de eso se encarga notificaciones.py.
"""
import html
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

NOMBRE_NEGOCIO = "BarberShop Pro"

# Colores de la interfaz (src/frontend/tailwind.config.js: brand.gold y brand.dark) y grises de apoyo
_ORO = "#D4AF37"
_OSCURO = "#0F172A"
_FONDO = "#F1F5F9"
_TARJETA = "#F8FAFC"
_BORDE = "#E2E8F0"
_TEXTO = "#334155"
_TEXTO_SUAVE = "#64748B"
_PIE = "#475569"
_FUENTE = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"


@dataclass
class ContenidoCorreo:
    asunto: str
    titulo: str
    saludo: str
    parrafos: List[str]
    datos: List[Tuple[str, str]] = field(default_factory=list)  # filas (etiqueta, valor); el valor puede tener "\n"
    titulo_datos: str = ""
    boton: Optional[Tuple[str, str]] = None  # (texto, dirección)
    avisos: List[str] = field(default_factory=list)
    resumen: str = ""  # texto de vista previa que algunos clientes muestran junto al asunto


# ==========================================
# Texto plano
# ==========================================
def a_texto(c: ContenidoCorreo) -> str:
    lineas = [NOMBRE_NEGOCIO.upper(), "=" * len(NOMBRE_NEGOCIO), "", c.titulo, "", c.saludo, ""]
    for parrafo in c.parrafos:
        lineas += [parrafo, ""]
    if c.datos:
        if c.titulo_datos:
            lineas += [c.titulo_datos.upper(), "-" * len(c.titulo_datos)]
        for etiqueta, valor in c.datos:
            primera, *resto = valor.split("\n")
            lineas.append(f"{etiqueta}: {primera}")
            lineas += [f"    {linea}" for linea in resto]
        lineas.append("")
    if c.boton:
        lineas += [f"{c.boton[0]}:", c.boton[1], ""]
    for aviso in c.avisos:
        lineas += [aviso, ""]
    lineas += [
        "Hasta pronto,",
        f"El equipo de {NOMBRE_NEGOCIO}",
        "",
        "--",
        f"Este es un mensaje automático de {NOMBRE_NEGOCIO}. Lo recibes porque tienes una cuenta en el sistema.",
    ]
    return "\n".join(lineas) + "\n"


# ==========================================
# HTML
# ==========================================
def _e(texto: str) -> str:
    return html.escape(str(texto), quote=True)


def _con_saltos(texto: str) -> str:
    return "<br>".join(_e(linea) for linea in texto.split("\n"))


def _fila_dato(etiqueta: str, valor: str) -> str:
    return (
        f'<tr><td class="etiqueta" valign="top" style="padding:7px 12px 7px 0;width:38%;font-size:13px;'
        f'color:{_TEXTO_SUAVE};">{_e(etiqueta)}</td>'
        f'<td class="valor" valign="top" style="padding:7px 0;font-size:15px;font-weight:600;color:{_OSCURO};">'
        f"{_con_saltos(valor)}</td></tr>"
    )


def _bloque_datos(c: ContenidoCorreo) -> str:
    if not c.datos:
        return ""
    titulo = ""
    if c.titulo_datos:
        titulo = (
            f'<p style="margin:0 0 6px 0;font-size:12px;font-weight:700;letter-spacing:1px;'
            f'text-transform:uppercase;color:{_TEXTO_SUAVE};">{_e(c.titulo_datos)}</p>'
        )
    filas = "".join(_fila_dato(etiqueta, valor) for etiqueta, valor in c.datos)
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="margin:20px 0;background:{_TARJETA};border:1px solid {_BORDE};border-left:4px solid {_ORO};'
        f'border-radius:8px;"><tr><td style="padding:16px 18px;">{titulo}'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">{filas}</table>'
        f"</td></tr></table>"
    )


def _bloque_boton(boton: Optional[Tuple[str, str]]) -> str:
    if not boton:
        return ""
    texto, direccion = boton
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:24px 0 8px 0;">'
        f'<tr><td class="boton" style="border-radius:8px;background:{_ORO};">'
        f'<a href="{_e(direccion)}" style="display:inline-block;padding:14px 28px;font-size:16px;'
        f'font-weight:700;color:{_OSCURO};text-decoration:none;border-radius:8px;">{_e(texto)}</a>'
        f"</td></tr></table>"
        f'<p style="margin:0 0 16px 0;font-size:12px;line-height:1.5;color:{_TEXTO_SUAVE};">'
        f"Si el botón no funciona, copia y pega esta dirección en tu navegador:<br>"
        f'<a href="{_e(direccion)}" style="color:{_TEXTO_SUAVE};word-break:break-all;">{_e(direccion)}</a></p>'
    )


def a_html(c: ContenidoCorreo) -> str:
    resumen = c.resumen or (c.parrafos[0] if c.parrafos else c.titulo)
    parrafos = "".join(
        f'<p style="margin:0 0 14px 0;font-size:15px;line-height:1.6;color:{_TEXTO};">{_con_saltos(p)}</p>'
        for p in c.parrafos
    )
    avisos = "".join(
        f'<p style="margin:0 0 10px 0;font-size:13px;line-height:1.6;color:{_TEXTO_SUAVE};">{_con_saltos(a)}</p>'
        for a in c.avisos
    )
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<meta name="supported-color-schemes" content="light">
<title>{_e(c.asunto)}</title>
<style>
  @media only screen and (max-width: 620px) {{
    .contenedor {{ width: 100% !important; }}
    .relleno {{ padding: 22px 18px !important; }}
    .etiqueta {{ display: block !important; width: 100% !important; padding: 8px 0 0 0 !important; }}
    .valor {{ display: block !important; width: 100% !important; padding: 0 0 6px 0 !important; }}
  }}
</style>
</head>
<body style="margin:0;padding:0;background:{_FONDO};font-family:{_FUENTE};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:{_FONDO};font-size:1px;line-height:1px;">{_e(resumen)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{_FONDO};">
<tr><td align="center" style="padding:24px 12px;">
  <table role="presentation" class="contenedor" width="600" cellpadding="0" cellspacing="0" border="0" style="width:600px;max-width:100%;background:#FFFFFF;border-radius:12px;overflow:hidden;">
    <tr><td align="center" style="background:{_OSCURO};padding:26px 20px;border-bottom:4px solid {_ORO};">
      <span style="font-family:{_FUENTE};font-size:24px;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:{_ORO};">{_e(NOMBRE_NEGOCIO)}</span>
    </td></tr>
    <tr><td class="relleno" style="padding:32px 36px;font-family:{_FUENTE};">
      <h1 style="margin:0 0 18px 0;font-size:22px;line-height:1.3;color:{_OSCURO};">{_e(c.titulo)}</h1>
      <p style="margin:0 0 14px 0;font-size:15px;line-height:1.6;color:{_TEXTO};">{_e(c.saludo)}</p>
      {parrafos}
      {_bloque_datos(c)}
      {_bloque_boton(c.boton)}
      {avisos}
      <p style="margin:22px 0 0 0;font-size:15px;line-height:1.6;color:{_TEXTO};">Hasta pronto,<br><strong>El equipo de {_e(NOMBRE_NEGOCIO)}</strong></p>
    </td></tr>
  </table>
  <table role="presentation" class="contenedor" width="600" cellpadding="0" cellspacing="0" border="0" style="width:600px;max-width:100%;">
    <tr><td align="center" style="padding:16px 18px;font-family:{_FUENTE};font-size:12px;line-height:1.6;color:{_PIE};">
      Este es un mensaje automático de {_e(NOMBRE_NEGOCIO)}. Lo recibes porque tienes una cuenta en el sistema.
    </td></tr>
  </table>
</td></tr>
</table>
</body>
</html>
"""
