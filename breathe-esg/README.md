# Breathe ESG — Data Ingestion & Review Prototype

A Django REST + React application that ingests emissions data from SAP (fuel/procurement), utility portals (electricity), and corporate travel platforms (Concur/Navan), normalizes it, and surfaces a review dashboard where analysts approve records before they're locked for audit.

## Live URLs

- **Frontend:** https://breathe-esg.vercel.app *(update after deploy)*
- **Backend API:** https://breathe-esg.up.railway.app *(update after deploy)*
- **Demo credentials:** No login required (demo mode, ACME Corp client)

## Repository Structure

```
breathe-esg/
├── backend/             # Django REST API
│   ├── breathe_esg/     # Django project settings, urls, wsgi
│   ├── ingestion/       # Models, parsers, ingest views
│   ├── reviews/         # Analyst review/approve/lock views
│   ├── requirements.txt
│   ├── Procfile
│   └── railway.toml
├── frontend/            # React + Tailwind dashboard
│   ├── src/
│   │   ├── pages/       # Dashboard, Ingest, Records, Jobs
│   │   ├── lib/api.js   # API client
│   │   └── App.js
│   └── vercel.json
├── sample_data/         # Realistic test files
│   ├── sap_fuel_sample.csv
│   ├── utility_electricity_sample.csv
│   └── travel_expenses_sample.json
└── docs/
    ├── MODEL.md
    ├── DECISIONS.md
    ├── TRADEOFFS.md
    └── SOURCES.md
```

## Deploy: Backend → Railway

1. Push `backend/` directory to GitHub
2. New project on [railway.app](https://railway.app) → "Deploy from GitHub"
3. Add PostgreSQL plugin
4. Set environment variables:
   ```
   SECRET_KEY=<generate-random-50-chars>
   DEBUG=False
   DATABASE_URL=<auto-set by Railway PostgreSQL>
   ```
5. Railway runs: `python manage.py migrate && gunicorn breathe_esg.wsgi`

## Deploy: Frontend → Vercel

1. Push `frontend/` directory to GitHub  
2. Import on [vercel.com](https://vercel.com)
3. Set environment variable:
   ```
   REACT_APP_API_URL=https://<your-railway-url>
   ```
4. Deploy

## Run Locally

```bash
# Backend
cd backend
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver

# Frontend (separate terminal)
cd frontend
npm install
npm start
```

The React dev server proxies `/api/` to `localhost:8000`.

## Testing with Sample Data

1. Open the app → **Ingest Data**
2. Upload `sample_data/sap_fuel_sample.csv` under SAP
3. Upload `sample_data/utility_electricity_sample.csv` under Utility  
4. Paste contents of `sample_data/travel_expenses_sample.json` under Travel
5. Go to **Records** → review, approve, flag records
6. **Dashboard** shows scope breakdown and review pipeline

## Key Design Decisions

See `docs/DECISIONS.md` for full rationale. Short version:
- **SAP:** MB51 flat file CSV — realistic for enterprises that can't configure OData
- **Utility:** Green Button / portal CSV — lowest-friction for facilities teams
- **Travel:** Concur/Navan JSON shape — matches actual API output
- **EF source:** DEFRA 2023 — free, peer-reviewed, annual updates

## Grading Checklist

| Requirement | Location |
|---|---|
| Multi-tenancy | `Client` FK on every model |
| Scope 1/2/3 | `scope` field, assigned at parse time |
| Source-of-truth tracking | `job`, `source_row_id`, `source_raw` fields |
| Unit normalization | `quantity`/`unit` (normalized) + `quantity_original`/`unit_original` |
| Audit trail | `edit_history`, `review_*` fields, `is_locked` |
| Review dashboard | `/records` page with approve/flag/reject + bulk actions |
| Suspicious flagging | `is_suspicious` + `suspicion_reason` auto-set at parse time |
| Audit lock | `POST /api/records/lock/` |
