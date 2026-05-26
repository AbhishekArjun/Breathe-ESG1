import React, { useEffect, useState } from 'react';
import { apiFetch } from '../lib/api';
import { CheckCircle2, AlertCircle, Clock, Loader } from 'lucide-react';

const STATUS_ICONS = {
  done: <CheckCircle2 size={14} className="text-forest-400" />,
  failed: <AlertCircle size={14} className="text-red-400" />,
  pending: <Clock size={14} className="text-amber-400" />,
  processing: <Loader size={14} className="text-blue-400 animate-spin" />,
};

const SOURCE_LABELS = {
  sap: { label: 'SAP Fuel', badge: 'badge-scope1' },
  utility: { label: 'Utility', badge: 'badge-scope2' },
  travel: { label: 'Travel', badge: 'badge-scope3' },
};

export default function Jobs() {
  const [jobs, setJobs] = useState([]);

  useEffect(() => {
    apiFetch('/jobs/').then(setJobs).catch(console.error);
  }, []);

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-white">Ingest Jobs</h1>
        <p className="text-sm text-slate-500 mt-1">History of all data ingestion runs</p>
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-slate-700 text-slate-500">
              <th className="px-5 py-3 text-left font-medium">Source</th>
              <th className="px-5 py-3 text-left font-medium">File</th>
              <th className="px-5 py-3 text-left font-medium">Ingested</th>
              <th className="px-5 py-3 text-left font-medium">By</th>
              <th className="px-5 py-3 text-center font-medium">Rows OK</th>
              <th className="px-5 py-3 text-center font-medium">Failed</th>
              <th className="px-5 py-3 text-center font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {jobs.length === 0 && (
              <tr><td colSpan={7} className="text-center py-16 text-slate-600">No jobs yet</td></tr>
            )}
            {jobs.map(j => {
              const src = SOURCE_LABELS[j.source_type] || { label: j.source_type, badge: '' };
              return (
                <tr key={j.id} className="border-b border-slate-800/50 hover:bg-slate-800/20">
                  <td className="px-5 py-3">
                    <span className={`badge ${src.badge}`}>{src.label}</span>
                  </td>
                  <td className="px-5 py-3 text-slate-400 font-mono max-w-[200px] truncate">{j.file_name || 'api-payload'}</td>
                  <td className="px-5 py-3 text-slate-400">{new Date(j.ingested_at).toLocaleString()}</td>
                  <td className="px-5 py-3 text-slate-500">{j.ingested_by}</td>
                  <td className="px-5 py-3 text-center font-mono text-forest-400">{j.rows_ok}</td>
                  <td className="px-5 py-3 text-center font-mono text-red-400">{j.rows_failed}</td>
                  <td className="px-5 py-3 text-center">
                    <span className="flex items-center justify-center gap-1">
                      {STATUS_ICONS[j.status]}
                      <span className="text-slate-400 capitalize">{j.status}</span>
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
