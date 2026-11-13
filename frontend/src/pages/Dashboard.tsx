import React, { useState, useEffect } from 'react';
import { 
  Calendar, Users, UserCheck, MessageSquare, 
  Activity, CheckCircle2, XCircle, Clock 
} from 'lucide-react';
import api from '../services/api';

export default function Dashboard() {
  const [stats, setStats] = useState<any>(null);
  const [appointments, setAppointments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [statsRes, apptsRes] = await Promise.all([
        api.get('/admin/dashboard-stats'),
        api.get('/appointments/?limit=10')
      ]);
      setStats(statsRes.data);
      setAppointments(apptsRes.data);
    } catch (err) {
      console.error('Failed to load dashboard data', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="p-8 text-center text-slate-500">Loading clinic operations...</div>;
  }

  const metrics = stats?.metrics || {};

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Clinic Dashboard Overview</h1>
          <p className="text-sm text-slate-500">Live WhatsApp booking telemetry and operations</p>
        </div>
        <div className="flex items-center gap-3 bg-emerald-50 text-emerald-700 px-3 py-1.5 rounded-full text-xs font-semibold">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          AI Agent Active
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex items-center gap-4">
          <div className="p-3 bg-blue-50 text-blue-600 rounded-lg">
            <Calendar className="w-6 h-6" />
          </div>
          <div>
            <div className="text-xs text-slate-500 font-medium">Total Appointments</div>
            <div className="text-2xl font-bold text-slate-900">{metrics.total_appointments || 0}</div>
          </div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex items-center gap-4">
          <div className="p-3 bg-emerald-50 text-emerald-600 rounded-lg">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <div>
            <div className="text-xs text-slate-500 font-medium">Confirmed</div>
            <div className="text-2xl font-bold text-emerald-600">{metrics.confirmed_appointments || 0}</div>
          </div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex items-center gap-4">
          <div className="p-3 bg-indigo-50 text-indigo-600 rounded-lg">
            <UserCheck className="w-6 h-6" />
          </div>
          <div>
            <div className="text-xs text-slate-500 font-medium">Active Doctors</div>
            <div className="text-2xl font-bold text-slate-900">{metrics.active_doctors || 0}</div>
          </div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex items-center gap-4">
          <div className="p-3 bg-purple-50 text-purple-600 rounded-lg">
            <MessageSquare className="w-6 h-6" />
          </div>
          <div>
            <div className="text-xs text-slate-500 font-medium">Conversations</div>
            <div className="text-2xl font-bold text-slate-900">{metrics.conversations_handled || 0}</div>
          </div>
        </div>
      </div>

      {/* Recent Appointments Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 flex justify-between items-center">
          <h2 className="font-semibold text-slate-800">Recent Appointments</h2>
          <span className="text-xs text-slate-400">Auto-synced with Google Calendar</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate-500 font-medium border-b border-slate-200">
              <tr>
                <th className="py-3 px-6">Appointment ID</th>
                <th className="py-3 px-6">Date & Time</th>
                <th className="py-3 px-6">Status</th>
                <th className="py-3 px-6">Google Calendar Sync</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {appointments.length === 0 ? (
                <tr>
                  <td colSpan={4} className="py-8 text-center text-slate-400">
                    No appointments booked yet. Try sending a message via WhatsApp!
                  </td>
                </tr>
              ) : (
                appointments.map((appt) => (
                  <tr key={appt.id} className="hover:bg-slate-50">
                    <td className="py-3 px-6 font-mono text-xs text-slate-600">
                      #{appt.id.substring(0, 8)}
                    </td>
                    <td className="py-3 px-6 text-slate-800 font-medium">
                      {new Date(appt.start_time).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}
                    </td>
                    <td className="py-3 px-6">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        appt.status === 'CONFIRMED' 
                          ? 'bg-emerald-100 text-emerald-800' 
                          : 'bg-rose-100 text-rose-800'
                      }`}>
                        {appt.status}
                      </span>
                    </td>
                    <td className="py-3 px-6 text-xs text-slate-500">
                      {appt.google_calendar_event_id ? (
                        <span className="text-emerald-600 flex items-center gap-1">
                          <CheckCircle2 className="w-3.5 h-3.5" /> Synced ({appt.google_calendar_event_id.slice(0, 10)}...)
                        </span>
                      ) : (
                        <span className="text-slate-400">Pending</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
