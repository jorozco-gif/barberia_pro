import React, { useState } from 'react';
import Navbar from './components/Navbar';
import BookingWizard from './components/BookingWizard';
import BarberAgenda from './components/BarberAgenda';
import SearchBooking from './components/SearchBooking';
import SuccessModal from './components/SuccessModal';

export default function App() {
  const [activeTab, setActiveTab] = useState('booking');
  const [confirmedCita, setConfirmedCita] = useState(null);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      <Navbar activeTab={activeTab} setActiveTab={setActiveTab} />

      <main className="flex-1 pb-16">
        {activeTab === 'booking' && (
          <BookingWizard onBookingSuccess={(cita) => setConfirmedCita(cita)} />
        )}

        {activeTab === 'agenda' && (
          <BarberAgenda />
        )}

        {activeTab === 'search' && (
          <SearchBooking />
        )}
      </main>

      {/* Modal de Éxito al Confirmar Cita */}
      {confirmedCita && (
        <SuccessModal
          cita={confirmedCita}
          onClose={() => setConfirmedCita(null)}
        />
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
