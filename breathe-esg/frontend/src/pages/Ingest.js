import React, { useState } from 'react';
import { apiUpload, apiPost } from '../lib/api';
import { Upload, CheckCircle2, AlertCircle, ChevronDown, ChevronUp } from 'lucide-react';

function UploadZone({ label, sub, accept, onUpload, loading }) {
  const [drag, setDrag] = useState(false);
  const [file, setFile] = useState(null);

  const handleFile = (f) => {
    setFile(f);
    onUpload(f);
  };

  return (
    <label
      className={`block border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors duration-150 ${
        drag ? 'border-forest-500 bg-forest-900/10' : 'border-slate-600 hover:border-slate-500'
      }`}
      onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files[0]; if (f) handleFile(f); }}
    >
      <input type="file" accept={accept} className="hidden"
        onChange={(e) => { if (e.target.files[0]) handleFile(e.target.files[0]); }} />
      <Upload size={24} className={`mx-auto mb-3 ${file ? 'text-forest-400' : 'text-slate-500'}`} />
      {file ? (
        <p className="text-sm font-medium text-forest-400">{file.name}</p>
      ) : (
        <>
          <p className="text-sm font-medium text-slate-300">{label}</p>
          <p className="text-xs text-slate-500 mt-1">{sub}</p>
        </>
      )}
      {loading && <p className="text-xs text-amber-400 mt-2 animate-pulse">Processing…</p>}
    </label>
  );
}

function JobResult({ job }) {
  const [open, setOpen] = useState(false);
  const ok = job.status === 'done';

  return (
    <div className={`rounded-xl border p-4 ${ok ? 'border-forest-700/50 bg-forest-900/10' : 'border-red-700/50 bg-red-900/10'}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {ok ? <CheckCircle2 size={18} className="text-forest-400" /> : <AlertCircle size={18} className="text-red-400" />}
          <div>
            <p className="text-sm font-medium text-white">{job.file_name}</p>
            <p className="text-xs text-slate-500">{job.rows_ok} rows OK · {job.rows_failed} failed</p>
          </div>
        </div>
        {job.rows_failed > 0 && (
          <button onClick={() => setOpen(o => !o)} className="text-xs text-slate-400 hover:text-slate-200 flex items-center gap-1">
            Errors {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        )}
      </div>
      {open && job.error_log?.length > 0 && (
        <div className="mt-3 space-y-1 max-h-40 overflow-auto">
          {job.error_log.map((e, i) => (
            <div key={i} className="text-xs text-red-300 bg-red-900/20 rounded px-2 py-1 font-mono">
              Row {e.row}: {e.reason}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const TRAVEL_PLACEHOLDER = JSON.stringify([
  {
    "report_id": "RPT-001",
    "expense_date": "2024-03-15",
    "expense_type": "AIRFARE",
    "traveler": "Jane Smith",
    "origin": "LHR",
    "destination": "JFK",
    "cabin_class": "economy"
  },
  {
    "report_id": "RPT-002",
    "expense_date": "2024-03-16",
    "expense_type": "HOTEL",
    "traveler": "Jane Smith",
    "vendor": "Marriott Times Square",
    "nights": 3
  }
], null, 2);

export default function Ingest() {
  const [sapResult, setSapResult] = useState(null);
  const [utilResult, setUtilResult] = useState(null);
  const [travelResult, setTravelResult] = useState(null);
  const [travelJson, setTravelJson] = useState('');
  const [loading, setLoading] = useState({});

  async function uploadFile(endpoint, file, key) {
    setLoading(l => ({ ...l, [key]: true }));
    try {
      const fd = new FormData();
      fd.append('file', file);
      const job = await apiUpload(endpoint, fd);
      return job;
    } finally {
      setLoading(l => ({ ...l, [key]: false }));
    }
  }

  async function submitTravel() {
    setLoading(l => ({ ...l, travel: true }));
    try {
      const payload = JSON.parse(travelJson);
      const job = await apiPost('/ingest/travel/', payload);
      setTravelResult(job);
    } catch (e) {
      alert('JSON parse error: ' + e.message);
    } finally {
      setLoading(l => ({ ...l, travel: false }));
    }
  }

  return (
    <div className="p-8 max-w-3xl">
      <div className="mb-8">
        <h1 className="text-xl font-semibold text-white">Ingest Data</h1>
        <p className="text-sm text-slate-500 mt-1">Upload files from SAP, utility portals, or travel platforms</p>
      </div>

      <div className="space-y-8">
        {/* SAP */}
        <div className="card p-6">
          <div className="mb-4">
            <div className="flex items-center gap-2 mb-1">
              <span className="badge badge-scope1">Scope 1</span>
              <h2 className="text-sm font-semibold text-white">SAP Flat File — Fuel & Procurement</h2>
            </div>
            <p className="text-xs text-slate-500">
              Movement type 261/201/551 CSV export. Handles German/English headers, semicolon or comma delimiters, 
              multiple date formats (YYYYMMDD, DD.MM.YYYY). Upload your MB52/MB51 export.
            </p>
          </div>
          <UploadZone
            label="Drop SAP CSV here"
            sub="Accepts .csv with German or English headers"
            accept=".csv,.txt"
            loading={loading.sap}
            onUpload={async (f) => {
              const job = await uploadFile('/ingest/sap/', f, 'sap');
              setSapResult(job);
            }}
          />
          {sapResult && <div className="mt-3"><JobResult job={sapResult} /></div>}
        </div>

        {/* Utility */}
        <div className="card p-6">
          <div className="mb-4">
            <div className="flex items-center gap-2 mb-1">
              <span className="badge badge-scope2">Scope 2</span>
              <h2 className="text-sm font-semibold text-white">Utility Portal CSV — Electricity</h2>
            </div>
            <p className="text-xs text-slate-500">
              Green Button CSV or generic utility portal export. Handles kWh/MWh units, non-calendar billing periods, 
              and multi-meter facilities. Columns: meter_id, billing_period_start, billing_period_end, consumption, unit, site_name.
            </p>
          </div>
          <UploadZone
            label="Drop utility CSV here"
            sub="Green Button or portal export format"
            accept=".csv"
            loading={loading.utility}
            onUpload={async (f) => {
              const job = await uploadFile('/ingest/utility/', f, 'utility');
              setUtilResult(job);
            }}
          />
          {utilResult && <div className="mt-3"><JobResult job={utilResult} /></div>}
        </div>

        {/* Travel */}
        <div className="card p-6">
          <div className="mb-4">
            <div className="flex items-center gap-2 mb-1">
              <span className="badge badge-scope3">Scope 3</span>
              <h2 className="text-sm font-semibold text-white">Travel Platform JSON — Concur / Navan</h2>
            </div>
            <p className="text-xs text-slate-500">
              Paste a JSON array of expense report entries (Concur expense export or Navan API shape). 
              Flight distances are computed via haversine if not supplied. Handles flights, hotels, ground transport.
            </p>
          </div>
          <textarea
            className="w-full h-48 bg-slate-900 border border-slate-600 rounded-lg px-4 py-3 text-xs font-mono 
                       text-slate-300 focus:outline-none focus:border-forest-600 resize-none"
            placeholder={TRAVEL_PLACEHOLDER}
            value={travelJson}
            onChange={e => setTravelJson(e.target.value)}
          />
          <div className="mt-3 flex items-center gap-3">
            <button className="btn-primary" onClick={submitTravel} disabled={!travelJson.trim() || loading.travel}>
              {loading.travel ? 'Processing…' : 'Submit Travel Data'}
            </button>
            <button className="text-xs text-slate-500 hover:text-slate-300"
              onClick={() => setTravelJson(TRAVEL_PLACEHOLDER)}>
              Load sample
            </button>
          </div>
          {travelResult && <div className="mt-3"><JobResult job={travelResult} /></div>}
        </div>
      </div>
    </div>
  );
}
