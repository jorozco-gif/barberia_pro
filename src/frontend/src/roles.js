// Roles y pestañas visibles por rol. Los valores de rol son exactamente los del backend (models.py).
// Es solo organización de la interfaz: el control de acceso real lo aplica el backend (RNF-03, 403).

export const ROLES = {
  CLIENTE: 'cliente',
  BARBERO: 'barbero',
  ADMIN: 'administrador',
};

export const ETIQUETA_ROL = {
  [ROLES.CLIENTE]: 'Cliente',
  [ROLES.BARBERO]: 'Barbero',
  [ROLES.ADMIN]: 'Administrador',
};

// Identificadores de pestaña (se conservan los de la versión 1.0: booking, agenda, search) + admin.
const PESTANAS_POR_ROL = {
  [ROLES.CLIENTE]: ['booking', 'search'],
  [ROLES.BARBERO]: ['agenda'],
  [ROLES.ADMIN]: ['search', 'admin'],
};

export function pestanasDeRol(rol) {
  return PESTANAS_POR_ROL[rol] || [];
}

export function pestanaInicial(rol) {
  return pestanasDeRol(rol)[0] || null;
}

export function puedeVerPestana(rol, pestana) {
  return pestanasDeRol(rol).includes(pestana);
}
