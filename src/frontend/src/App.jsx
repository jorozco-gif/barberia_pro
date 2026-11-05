import React, { useEffect, useState } from 'react';
import { AuthProvider, useAuth } from './AuthContext';
import { pestanaInicial, puedeVerPestana } from './roles';
import Navbar from './components/Navbar';
import AuthPage, { ResetPasswordPage } from './components/AuthPage';
import BookingWizard from './components/BookingWizard';
import BarberAgenda from './components/BarberAgenda';
import SearchBooking from './components/SearchBooking';
import AdminPanel from './components/AdminPanel';
import SuccessModal from './components/SuccessModal';

// El enlace de recuperación que envía el backend apunta a {FRONTEND_URL}/restablecer?token=...
// Devuelve el token (posiblemente vacío) si la URL actual es esa ruta, o null en cualquier otro caso.
function leerTokenDeRestablecimiento() {
  if (window.location.pathname.replace(/\/+$/, '') !== '/restablecer') return null;
  return new URLSearchParams(window.location.search).get('token') || '';
}

function AppContent() {
  const { usuario, rol, descartarSesionLocal } = useAuth();
  const [activeTab, setActiveTab] = useState(null);
  const [resultado, setResultado] = useState(null); // { tipo: 'agendada' | 'reprogramada' | 'cancelada', cita }
  const [tokenReset, setTokenReset] = useState(leerTokenDeRestablecimiento);

  // Al cerrarse la sesión (manualmente o por expiración) se descarta el estado de la sesión anterior.
  useEffect(() => {
    if (!usuario) {
      setActiveTab(null);
      setResultado(null);
    }
  }, [usuario]);

  // Solo se muestran las vistas permitidas para el rol (el backend sigue siendo quien autoriza cada petición).
  const pestana = usuario ? (puedeVerPestana(rol, activeTab) ? activeTab : pestanaInicial(rol)) : null;

  const irAPestana = (id) => {
    setTokenReset(null);
    setActiveTab(id);
  };

  const terminarRestablecimiento = (restablecida) => {
    window.history.replaceState({}, '', '/');
    if (restablecida) descartarSesionLocal(); // el backend cierra las sesiones de la cuenta al cambiar la contraseña
    setTokenReset(null);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      <Navbar activeTab={pestana} setActiveTab={irAPestana} />

      <main className="flex-1 pb-16">
        {tokenReset !== null ? (
          <ResetPasswordPage token={tokenReset} onTerminar={terminarRestablecimiento} />
        ) : !usuario ? (
          <AuthPage />
        ) : (
          <>
            {pestana === 'booking' && (
              <BookingWizard
                onBookingSuccess={(cita) => setResultado({ tipo: 'agendada', cita })}
                onVerMisCitas={() => setActiveTab('search')}
              />
            )}

            {pestana === 'agenda' && <BarberAgenda />}

            {pestana === 'search' && (
              <SearchBooking onOperacionExitosa={(tipo, cita) => setResultado({ tipo, cita })} />
            )}

            {pestana === 'admin' && <AdminPanel />}

            {!pestana && (
              <p className="max-w-md mx-auto px-4 py-16 text-center text-slate-400 text-sm">
                Tu cuenta no tiene opciones disponibles en esta aplicación.
              </p>
            )}
          </>
        )}
      </main>

      {/* Modal de resultado: cita agendada, reprogramada o cancelada */}
      {usuario && resultado && (
        <SuccessModal cita={resultado.cita} tipo={resultado.tipo} onClose={() => setResultado(null)} />
      )}

      {/* Footer */}
      <footer className="border-t border-slate-900 bg-slate-950 py-6 text-center text-xs text-slate-500">
        <div className="max-w-6xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>💈 BarberShop Pro — Ingeniería de Software II (Cotecnova 2026-2)</span>
          <span>Docente: Felipe Gutiérrez Isaza</span>
        </div>
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
