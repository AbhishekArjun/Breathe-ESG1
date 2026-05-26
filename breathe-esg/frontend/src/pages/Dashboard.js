import React, { useEffect, useState } from 'react';
import { apiFetch } from '../lib/api';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts';
import { AlertTriangle, CheckCircle2, Clock, XCircle, Zap, TrendingUp } from 'lucide-react';

const SCOPE_COLORS = ['#3b82f6', '#a855f7', '#14b8a6'];

function StatCard({ label, value, sub, icon: Icon, color = 'slate' }) {
  const colors = {
    amber: 'text-amber-400 bg-amber-900/20 border-amber-800/30',
    green: 'text-forest-400 bg-forest-900/20 border-forest-800/30',
    orange: 'text-orange-400 bg-orange-900/20 border-orange-800/30',
    red: 'text-red-400 bg-red-900/20 border-red-800/30',
    slate: 'text-slate-400 bg-slate-800/50 border-slate-700/30',
    blue: 'text-blue-400 bg-blue-900/20 border-blue-800/30',
  };
  return (
    <div className={`card p-5 border ${colors[color]}`}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">{label}</p>
          <p className="text-2xl font-semibold mt-1 text-white">{value}</p>
          {sub && <p className="text-xs text-slate-500 mt-0.5">{sub}</p>}
        </div>
        <div className={`p-2 rounded-lg ${colors[color]}`}>
          <Icon size={18} />
        </div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch('/stats/').then(setStats).catch(console.error).finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="flex items-center justify-center h-full text-slate-500">
      Loading dashboard…
    </div>
  );

  const scopeData = stats ? [
    { name: 'Scope 1 (Fuel)', value: stats.scope1_co2e / 1000 },
    { name: 'Scope 2 (Electricity)', value: stats.scope2_co2e / 1000 },
    { name: 'Scope 3 (Travel)', value: stats.scope3_co2e / 1000 },
  ].filter(d => d.value > 0) : [];

  const totalTonnes = stats ? (stats.total_co2e_kg / 1000).toFixed(1) : '0';

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-xl font-semibold text-white">Emissions Dashboard</h1>
        <p className="text-sm text-slate-500 mt-1">ACME Corp · Current ingestion cycle</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label="Pending Review" value={stats?.pending ?? '—'} icon={Clock} color="amber" />
        <StatCard label="Approved" value={stats?.approved ?? '—'} icon={CheckCircle2} color="green" />
        <StatCard label="Flagged" value={stats?.flagged ?? '—'} icon={AlertTriangle} color="orange" />
        <StatCard label="Suspicious" value={stats?.suspicious ?? '—'} sub="auto-detected" icon={XCircle} color="red" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Scope breakdown */}
        <div className="card p-6">
          <h2 className="text-sm font-semibold text-slate-300 mb-1">Total Emissions by Scope</h2>
          <p className="text-xs text-slate-500 mb-4">Tonnes CO₂e · DEFRA 2023 factors</p>
          <div className="text-3xl font-semibold text-white mb-6">{totalTonnes} <span className="text-sm font-normal text-slate-400">tCO₂e</span></div>
          {scopeData.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie data={scopeData} cx="50%" cy="50%" innerRadius={50} outerRadius={80}
                  paddingAngle={3} dataKey="value">
                  {scopeData.map((_, i) => <Cell key={i} fill={SCOPE_COLORS[i]} />)}
                </Pie>
                <Tooltip
                  contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
                  labelStyle={{ color: '#94a3b8' }}
                  formatter={(v) => [`${v.toFixed(1)} tCO₂e`]}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-40 flex items-center justify-center text-slate-600 text-sm">
              No emission data yet — upload a file
            </div>
          )}
          <div className="space-y-2 mt-2">
            {scopeData.map((d, i) => (
              <div key={d.name} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: SCOPE_COLORS[i] }} />
                  <span className="text-slate-400">{d.name}</span>
                </div>
                <span className="text-slate-300 font-mono">{d.value.toFixed(1)} t</span>
              </div>
            ))}
          </div>
        </div>

        {/* Review status */}
        <div className="card p-6">
          <h2 className="text-sm font-semibold text-slate-300 mb-1">Review Pipeline</h2>
          <p className="text-xs text-slate-500 mb-6">Record lifecycle status</p>
          <div className="space-y-3">
            {[
              { label: 'Pending', count: stats?.pending, color: 'bg-amber-500', max: stats?.total_records },
              { label: 'Approved', count: stats?.approved, color: 'bg-forest-500', max: stats?.total_records },
              { label: 'Flagged', count: stats?.flagged, color: 'bg-orange-500', max: stats?.total_records },
              { label: 'Rejected', count: stats?.rejected, color: 'bg-red-500', max: stats?.total_records },
            ].map(({ label, count, color, max }) => {
              const pct = max ? Math.round((count / max) * 100) : 0;
              return (
                <div key={label}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-slate-400">{label}</span>
                    <span className="text-slate-300">{count} <span className="text-slate-600">({pct}%)</span></span>
                  </div>
                  <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
                    <div className={`h-full ${color} rounded-full transition-all duration-500`} style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
          <div className="mt-6 pt-4 border-t border-slate-700">
            <div className="flex justify-between text-xs text-slate-500">
              <span>Total records</span>
              <span className="text-slate-300 font-mono">{stats?.total_records}</span>
            </div>
            <div className="flex justify-between text-xs text-slate-500 mt-1">
              <span>Ingest jobs</span>
              <span className="text-slate-300 font-mono">{stats?.jobs}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Quick actions */}
      <div className="card p-5 border-dashed border-slate-600">
        <p className="text-xs text-slate-500">
          <strong className="text-slate-400">Workflow:</strong> Upload data via Ingest → Records appear as{' '}
          <span className="text-amber-400">Pending</span> → Analyst reviews and approves/flags →{' '}
          Lock approved rows for auditor export.
        </p>
      </div>
    </div>
  );
}
