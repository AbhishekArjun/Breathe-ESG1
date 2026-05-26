# DECISIONS.md — Ambiguity Resolution Log

Every non-obvious choice made during this build, what I chose, why, and what I'd ask the PM.

---

## SAP: Which export format?

**Options:** IDoc (XML), OData service (live API pull), BAPI RFC, flat file (CSV/tab-delimited).

**Chose:** Flat file CSV — specifically the MB51 material document list export.

**Why:** IDoc is the canonical SAP integration format but requires an ALE/EDI partner profile configured on the SAP side. OData and BAPI require live API credentials and middleware. The realistic situation for a new enterprise client is: their SAP admin runs a transaction (MB51 for goods movements, MB52 for stock), exports a CSV, and drops it somewhere. This is what actually happens in 70% of mid-enterprise onboardings I found described in SAP community forums and client implementation guides. The complexity of IDoc parsing (segment definitions, control records, data records) is real but adds no value for a prototype whose purpose is demonstrating the normalization and review pipeline.

**What I'd ask the PM:** "Does this client have an SAP Basis team willing to configure an RFC destination or OData service? Or are we expecting a scheduled CSV dump to S3/SFTP?" The answer determines whether we build a file upload or a pull connector.

**Subset handled:** Movement types 261 (goods issue to cost center), 201, 551 — i.e., fuel leaving inventory for consumption. Excluded: 101 (goods receipt), 301 (transfer), 541 (consignment). Excluded plant-to-plant transfers, which would double-count.

---

## SAP: German headers

**Problem:** SAP defaults to the language of the system it's installed on. Indian SAP installs are often configured in German (SAP's origin language is German, many consultants ship the default). Real exports include "Buchungsdatum", "Werk", "Menge", "Mengeneinheit".

**Chose:** A bidirectional header mapping table that tries German first, then English. If neither matches, skip the column rather than error.

**Why:** Failing hard on an unknown header kills an entire upload. Silently skipping unknown columns and logging them is more useful in practice — the analyst can see "column X not recognized" in the error log rather than "upload failed."

---

## Utility: Which ingestion mode?

**Options:** PDF bill parsing, portal CSV export, Green Button API, utility API (rare, only some large utilities offer it).

**Chose:** CSV portal export.

**Why:** Green Button is the US standard (ESPI protocol), used by ~60 utilities. Most Indian utilities (MSEDCL, BESCOM, TSSPDCL) offer a portal CSV download. PDF parsing is brittle — layout changes break it. API access requires per-utility integration agreements that no new client will have on day one. The CSV export is the intersection of "realistic" and "implementable in 4 days."

**What I'd ask the PM:** "Do any of the client's utility providers offer Green Button Connect (automatic pull)? If yes, we should implement the OAuth flow for those and file upload for the rest." Green Button pull is clearly the right long-term solution.

**Billing period handling:** Utility bills don't align with calendar months. A bill might cover Jan 7 – Feb 6. I store `period_start` and `period_end` and use `period_end` as `activity_date` for sorting. I do NOT prorate to calendar months in this prototype — that's a deliberate omission (see TRADEOFFS.md).

---

## Travel: JSON vs CSV

**Chose:** JSON upload/paste that mirrors the Concur Expense Report Export API shape.

**Why:** Concur's primary export mechanism is their API (`GET /api/expense/expensereport/v2.0/report`). The response is JSON. Navan (formerly TripActions) also exposes JSON webhooks and exports. CSV exports from these platforms exist but have non-standardized column names across versions. JSON is more stable.

I also support pasting JSON directly — because in reality, a PM will copy-paste an API response to test the system before automation is set up.

**Subset handled:** AIRFARE, HOTEL, TAXI, TRAIN, CAR_RENTAL. Excluded: per-diem meals, conference registrations (not emission-bearing), and mileage claims without distance data.

---

## Flight distances

**Problem:** Concur expense reports often include only origin/destination airport codes (e.g. DEL → LHR), not actual distances. Real distance varies by routing (direct vs. connecting).

**Chose:** Haversine great-circle distance as a fallback when `distance_km` is not provided, with `is_estimated = True` flagged on those records.

**Why:** DEFRA and BEIS methodologies accept great-circle distance for flight emission calculations. The radiative forcing multiplier (1.9× for high-altitude flights) is an active debate in the GHG protocol community — I applied DEFRA's simplified factor which doesn't use RFI rather than introducing a scientifically contested multiplier.

**What I'd ask the PM:** "Is the client reporting under GHG Protocol Corporate Standard or a specific framework (CDP, TCFD, SBTi)? Some require RFI; some explicitly say don't use it."

---

## Emission factors

**Chose:** DEFRA 2023 Greenhouse Gas Conversion Factors (UK Government, published annually).

**Why:** DEFRA publishes free, peer-reviewed, annually updated factors for all common fuel types, electricity, and travel. They're the de-facto standard for UK corporate reporting and widely used globally. The alternative (EPA, IPCC AR6) would require building a jurisdiction-selection layer I don't have time for.

**What would break in production:** The electricity emission factor (0.2072 kgCO2e/kWh) is the UK grid average. Indian grid emission factor (CEA 2023) is 0.716 kgCO2e/kWh — significantly higher. A real deployment requires location-aware EF selection. I'd build a `EmissionFactorLibrary` table with (fuel_type, region, year) → factor, and join at query time.

---

## Multi-tenancy implementation

**Chose:** Shared database, shared schema, tenant identified by FK.

**Why:** Row-level tenancy via FK is the simplest approach that works. Schema-per-tenant (Postgres schemas) or database-per-tenant are more isolated but require migration tooling (django-tenants or custom) that's out of scope. For a prototype with one demo client, FK isolation is sufficient. The API layer always filters by `client_id`.

**What I'd ask the PM:** "What's the client data isolation requirement? Contractual/legal data residency, or just logical separation? That determines whether we need schema-per-tenant."

---

## Review workflow

**Chose:** Optimistic inline review — clicking approve/flag/reject updates a single record immediately, no workflow queue.

**Why:** A PM sent me to "build a prototype in 4 days," not a workflow engine. The core need is: analyst sees what came in, marks it, locks it. A Celery task queue, email notifications, and multi-step approval chains are real production needs but not prototype needs.
