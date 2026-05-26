import React from 'react';
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Ingest from './pages/Ingest';
import Records from './pages/Records';
import Jobs from './pages/Jobs';
import { Leaf, Upload, Table2, Activity, ClipboardCheck } from 'lucide-react';
import './index.css';

function NavItem({ to, icon: Icon, label }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors duration-150 ${
          isActive
            ? 'bg-forest-700/30 text-forest-300 border border-forest-700/50'
            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
        }`
      }
    >
      <Icon size={16} />
      {label}
    </NavLink>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen overflow-hidden" style={{ backgroundColor: '#0a1628' }}>
        {/* Sidebar */}
        <aside className="w-56 flex-shrink-0 flex flex-col border-r border-slate-800 bg-slate-900/50">
          <div className="px-5 py-5 border-b border-slate-800">
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-forest-600 flex items-center justify-center">
                <Leaf size={14} className="text-white" />
              </div>
              <div>
                <div className="text-sm font-semibold text-white leading-none">Breathe ESG</div>
                <div className="text-xs text-slate-500 mt-0.5">Data Review</div>
              </div>
            </div>
          </div>

          <nav className="flex-1 px-3 py-4 space-y-1">
            <NavItem to="/" icon={Activity} label="Dashboard" />
            <NavItem to="/ingest" icon={Upload} label="Ingest Data" />
            <NavItem to="/records" icon={Table2} label="Records" />
            <NavItem to="/jobs" icon={ClipboardCheck} label="Ingest Jobs" />
          </nav>

          <div className="px-4 py-4 border-t border-slate-800">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-full bg-slate-700 flex items-center justify-center text-xs font-medium text-slate-300">
                A
              </div>
              <div>
                <div className="text-xs font-medium text-slate-300">Analyst</div>
                <div className="text-xs text-slate-500">ACME Corp</div>
              </div>
            </div>
          </div>
        </aside>

        {/* Main content */}
        <main className="flex-1 overflow-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/ingest" element={<Ingest />} />
            <Route path="/records" element={<Records />} />
            <Route path="/jobs" element={<Jobs />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
