import React, { useEffect, useState, useCallback } from 'react';
import { apiFetch, apiPost } from '../lib/api';
import { AlertTriangle, CheckCircle2, XCircle, Flag, Lock, ChevronLeft, ChevronRight, Filter } from 'lucide-react';

const ANALYST = 'analyst@demo.com';

function Badge({ status }) {
  const map = {
    pending: 'badge-pending',
    approved: 'badge-approved',
    flagged: 'badge-flagged',
    rejected: 'badge-rejected',
  };
  return <span className={`badge ${map[status] || 'badge-pending'}`}>{status}</span>;
}

function ScopeBadge({ scope }) {
  return <span className={`badge badge-scope${scope}`}>S{scope}</span>;
}

function ReviewActions({ record, onUpdated }) {
  const [loading, setLoading] = useState(false);

  async function doAction(action) {
    if (record.is_locked) return;
    setLoading(true);
    try {
      await apiPost(`/records/${record.id}/review/`, { action, analyst: ANALYST });
      onUpdated(record.id, action);
    } finally {
      setLoading(false);
    }
  }

  if (record.is_locked) return <span className="text-xs text-slate-600 flex items-center gap-1"><Lock size={11} /> Locked</span>;

  return (
    <div className="flex items-center gap-1">
      <button title="Approve" onClick={() => doAction('approved')} disabled={loading}
        className="p-1.5 rounded hover:bg-forest-900/40 text-slate-500 hover:text-forest-400 transition-colors">
        <CheckCircle2 size={15} />
      </button>
      <button title="Flag" onClick={() => doAction('flagged')} disabled={loading}
        className="p-1.5 rounded hover:bg-orange-900/40 text-slate-500 hover:text-orange-400 transition-colors">
        <Flag size={15} />
      </button>
      <button title="Reject" onClick={() => doAction('rejected')} disabled={loading}
        className="p-1.5 rounded hover:bg-red-900/40 text-slate-500 hover:text-red-400 transition-colors">
        <XCircle size={15} />
      </button>
    </div>
  );
}

export default function Records() {
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({ scope: '', category: '', review_status: '', suspicious: '' });
  const [selected, setSelected] = useState(new Set());
  const [locking, setLocking] = useState(false);

  const load = useCallback(() => {
    const params = new URLSearchParams({ page });
    Object.entries(filters).forEach(([k, v]) => { if (v) params.set(k, v); });
    apiFetch(`/records/?${params}`).then(setData).catch(console.error);
  }, [page, filters]);

  useEffect(() => { load(); }, [load]);

  function updateRecord(id, newStatus) {
    setData(d => ({
      ...d,
      results: d.results.map(r => r.id === id ? { ...r, review_status: newStatus } : r)
    }));
  }

  async function bulkAction(action) {
    if (!selected.size) return;
    await apiPost('/records/bulk-review/', { ids: [...selected], action, analyst: ANALYST });
    setSelected(new Set());
    load();
  }

  async function lockAll() {
    setLocking(true);
    await apiPost('/records/lock/', { analyst: ANALYST });
    setLocking(false);
    load();
  }

  const toggleSelect = (id) => {
    setSelected(s => {
      const n = new Set(s);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });
  };

  const records = data?.results || [];
  const fmtNum = (n) => parseFloat(n).toLocaleString(undefined, { maximumFractionDigits: 2 });

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-white">Records</h1>
          <p className="text-sm text-slate-500 mt-0.5">{data?.count ?? '…'} total rows</p>
        </div>
        <div className="flex items-center gap-2">
          {selected.size > 0 && (
            <>
              <span className="text-xs text-slate-400">{selected.size} selected</span>
              <button className="btn-ghost text-xs" onClick={() => bulkAction('approved')}>Approve all</button>
              <button className="btn-ghost text-xs" onClick={() => bulkAction('flagged')}>Flag all</button>
            </>
          )}
          <button className="btn-primary flex items-center gap-2 text-xs" onClick={lockAll} disabled={locking}>
            <Lock size={13} /> {locking ? 'Locking…' : 'Lock Approved'}
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="card p-4 mb-4 flex items-center gap-3 flex-wrap">
        <Filter size={14} className="text-slate-500" />
        {[
          { key: 'scope', label: 'Scope', opts: [['', 'All'], ['1', 'S1'], ['2', 'S2'], ['3', 'S3']] },
          { key: 'category', label: 'Category', opts: [['', 'All'], ['fuel', 'Fuel'], ['electricity', 'Electricity'], ['flight', 'Flight'], ['hotel', 'Hotel'], ['ground_transport', 'Ground']] },
          { key: 'review_status', label: 'Status', opts: [['', 'All'], ['pending', 'Pending'], ['approved', 'Approved'], ['flagged', 'Flagged'], ['rejected', 'Rejected']] },
          { key: 'suspicious', label: 'Suspicious', opts: [['', 'All'], ['true', 'Only suspicious']] },
        ].map(({ key, label, opts }) => (
          <select key={key}
            className="bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-300 px-3 py-1.5 focus:outline-none focus:border-forest-600"
            value={filters[key]}
            onChange={e => { setFilters(f => ({ ...f, [key]: e.target.value })); setPage(1); }}>
            {opts.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        ))}
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-slate-700 text-slate-500">
                <th className="px-4 py-3 text-left w-8">
                  <input type="checkbox" className="rounded" onChange={e => {
                    if (e.target.checked) setSelected(new Set(records.map(r => r.id)));
                    else setSelected(new Set());
                  }} />
                </th>
                <th className="px-4 py-3 text-left font-medium">Date</th>
                <th className="px-4 py-3 text-left font-medium">Scope / Category</th>
                <th className="px-4 py-3 text-left font-medium">Description</th>
                <th className="px-4 py-3 text-left font-medium">Location</th>
                <th className="px-4 py-3 text-right font-medium">Quantity</th>
                <th className="px-4 py-3 text-right font-medium">CO₂e (kg)</th>
                <th className="px-4 py-3 text-center font-medium">Flags</th>
                <th className="px-4 py-3 text-center font-medium">Status</th>
                <th className="px-4 py-3 text-center font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {records.length === 0 && (
                <tr><td colSpan={10} className="text-center py-16 text-slate-600">
                  No records found — upload data to get started
                </td></tr>
              )}
              {records.map(r => (
                <tr key={r.id}
                  className={`border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors ${r.is_suspicious ? 'bg-red-950/10' : ''}`}>
                  <td className="px-4 py-3">
                    <input type="checkbox" checked={selected.has(r.id)}
                      onChange={() => toggleSelect(r.id)} className="rounded" />
                  </td>
                  <td className="px-4 py-3 font-mono text-slate-400">{r.activity_date}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1.5">
                      <ScopeBadge scope={r.scope} />
                      <span className="text-slate-400 capitalize">{r.category?.replace('_', ' ')}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-slate-300 max-w-[200px] truncate" title={r.description}>
                    {r.description || '—'}
                  </td>
                  <td className="px-4 py-3 text-slate-400 max-w-[120px] truncate">{r.location || '—'}</td>
                  <td className="px-4 py-3 text-right font-mono text-slate-300">
                    {fmtNum(r.quantity)} <span className="text-slate-600">{r.unit}</span>
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-slate-300">
                    {r.co2e_kg ? fmtNum(r.co2e_kg) : '—'}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <div className="flex items-center justify-center gap-1">
                      {r.is_suspicious && (
                        <span title={r.suspicion_reason} className="text-red-400 cursor-help">
                          <AlertTriangle size={13} />
                        </span>
                      )}
                      {r.is_estimated && (
                        <span title="Estimated/interpolated value" className="text-amber-500">~</span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-center"><Badge status={r.review_status} /></td>
                  <td className="px-4 py-3">
                    <ReviewActions record={r} onUpdated={updateRecord} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {data && data.pages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-700">
            <span className="text-xs text-slate-500">Page {data.page} of {data.pages}</span>
            <div className="flex gap-2">
              <button className="btn-ghost text-xs flex items-center gap-1"
                onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>
                <ChevronLeft size={13} /> Prev
              </button>
              <button className="btn-ghost text-xs flex items-center gap-1"
                onClick={() => setPage(p => Math.min(data.pages, p + 1))} disabled={page === data.pages}>
                Next <ChevronRight size={13} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
