import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import { LayoutDashboard, Users, Calendar, Stethoscope, MessageSquare } from 'lucide-react';
import Dashboard from './pages/Dashboard';

export default function App() {
  return (
    <Router>
      <div className="flex min-h-screen bg-slate-50">
        {/* Sidebar */}
        <aside className="w-64 bg-slate-900 text-slate-300 flex flex-col">
          <div className="p-6 border-b border-slate-800 flex items-center gap-2">
            <div className="p-2 bg-blue-600 rounded-lg text-white font-bold">HA</div>
            <div>
              <div className="text-white font-semibold leading-tight">HealthAI</div>
              <div className="text-xs text-slate-500">Clinic WhatsApp Hub</div>
            </div>
          </div>
          <nav className="flex-1 p-4 space-y-1">
            <Link
              to="/"
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium bg-blue-600 text-white"
            >
              <LayoutDashboard className="w-4 h-4" />
              Dashboard Overview
            </Link>
            <a
              href="#appointments"
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium hover:bg-slate-800 transition"
            >
              <Calendar className="w-4 h-4" />
              Appointments
            </a>
            <a
              href="#doctors"
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium hover:bg-slate-800 transition"
            >
              <Stethoscope className="w-4 h-4" />
              Doctors & Schedules
            </a>
            <a
              href="#patients"
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium hover:bg-slate-800 transition"
            >
              <Users className="w-4 h-4" />
              Patients
            </a>
          </nav>
          <div className="p-4 border-t border-slate-800 text-xs text-slate-500 text-center">
            HealthAI Assistant v1.0
          </div>
        </aside>

        {/* Content */}
        <main className="flex-1">
          <Routes>
            <Route path="/" element={<Dashboard />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}
