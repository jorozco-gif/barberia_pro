import React from 'react';
import { Scissors, Calendar, Search, ShieldCheck } from 'lucide-react';

export default function Navbar({ activeTab, setActiveTab }) {
  return (
    <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-40">
      <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
        <div className="flex items-center gap-3 cursor-pointer" onClick={() => setActiveTab('booking')}>
          <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400">
            <Scissors className="w-5 h-5 rotate-45" />
          </div>
          <div>
            <h1 className="font-bold text-lg tracking-tight text-white flex items-center gap-2">
              BarberShop <span className="text-amber-400 text-sm font-semibold uppercase px-1.5 py-0.5 rounded bg-amber-400/10 border border-amber-400/20">Pro</span>
            </h1>
            <p className="text-xs text-slate-400">Sistema de Agendamiento</p>
          </div>
        </div>

        <nav className="flex items-center gap-1 sm:gap-2">
          <button
            onClick={() => setActiveTab('booking')}
            className={`px-3 py-2 rounded-lg text-xs sm:text-sm font-medium transition flex items-center gap-2 ${
              activeTab === 'booking'
                ? 'bg-amber-500 text-slate-950 font-semibold shadow-lg shadow-amber-500/20'
                : 'text-slate-300 hover:bg-slate-800'
            }`}
          >
            <Scissors className="w-4 h-4" />
            <span className="hidden sm:inline">Agendar Cita</span>
          </button>

          <button
            onClick={() => setActiveTab('agenda')}
            className={`px-3 py-2 rounded-lg text-xs sm:text-sm font-medium transition flex items-center gap-2 ${
              activeTab === 'agenda'
                ? 'bg-amber-500 text-slate-950 font-semibold shadow-lg shadow-amber-500/20'
                : 'text-slate-300 hover:bg-slate-800'
            }`}
          >
            <Calendar className="w-4 h-4" />
            <span className="hidden sm:inline">Agenda del Barbero</span>
          </button>

          <button
            onClick={() => setActiveTab('search')}
            className={`px-3 py-2 rounded-lg text-xs sm:text-sm font-medium transition flex items-center gap-2 ${
              activeTab === 'search'
                ? 'bg-amber-500 text-slate-950 font-semibold shadow-lg shadow-amber-500/20'
                : 'text-slate-300 hover:bg-slate-800'
            }`}
          >
            <Search className="w-4 h-4" />
            <span className="hidden sm:inline">Consultar Reserva</span>
          </button>
        </nav>
      </div>
    </header>
  );
}
