# MODEL.md — Data Model

## Overview

Three Django models carry the entire data lifecycle: `Client`, `IngestionJob`, and `EmissionRecord`. Every design decision below was made to satisfy the five stated requirements: multi-tenancy, Scope 1/2/3 classification, source-of-truth tracking, unit normalization, and audit trail.

---

## Model: `Client`

```
Client
├── id          UUID PK
├── name        str
├── slug        str (unique)
└── created_at  datetime
```

Every other model has a FK to `Client`. This is the tenancy boundary. Queries are always scoped by `client_id` first. A future multi-org setup would add role-based access on top of this; the FK structure doesn't change.

---

## Model: `IngestionJob`

```
IngestionJob
├── id            UUID PK
├── client        FK → Client
├── source_type   enum: sap | utility | travel
├── status        enum: pending | processing | done | failed
├── file_name     str
├── file_path     FileField (uploaded raw file, immutable)
├── raw_payload   JSONField (for travel JSON paste, kept verbatim)
├── rows_total    int
├── rows_ok       int
├── rows_failed   int
├── error_log     JSONField  [{row, reason, raw}]
├── ingested_at   datetime
└── ingested_by   str (analyst email)
```

**Why this exists:** every `EmissionRecord` needs a parent `IngestionJob`. This answers "where did this number come from?" at the batch level — which upload, when, by whom, from which source system. Without it, a single emission record floating in a table is unauditable.

The `error_log` stores rows that failed parsing with their raw content, so an analyst can see exactly what was rejected and why — not just a count.

---

## Model: `EmissionRecord`

The core normalized row. Every SAP goods issue, utility bill line, and travel expense becomes one `EmissionRecord`.

### Multi-tenancy

```python
client = FK(Client)
```

All queries are scoped to `client`. Index on `(client, scope, activity_date)`. No row is ever visible across tenant boundaries in the API layer.

### Scope 1/2/3 classification

```python
scope = IntegerField(choices=[1, 2, 3])
category = CharField(choices=[fuel, electricity, flight, hotel, ground_transport])
```

Scope is assigned at parse time, not at query time, because the source determines it unambiguously:
- SAP fuel/goods-issue → **Scope 1** (direct combustion, your fleet or plant)
- Utility electricity consumption → **Scope 2** (purchased electricity)
- Corporate travel (flights, hotels, ground) → **Scope 3 Category 6** (business travel)

`category` is a sub-classification within scope for reporting granularity (e.g. splitting Scope 3 by flight vs. hotel vs. ground).

### Source-of-truth tracking

```python
job             = FK(IngestionJob)     # which batch produced this row
source_row_id   = str                  # original PK or row number in source file
source_raw      = JSONField            # verbatim row as received, never mutated
```

`source_raw` is immutable. It stores the exact JSON or CSV row that produced this record. If an auditor questions a figure, you can always show the original source data alongside the normalized result. `source_row_id` links back to a specific row number or SAP document number.

### Unit normalization

Every quantity is stored twice:

```python
quantity          # normalized value in SI base unit
unit              # normalized unit: L (fuel), kWh (electricity), km (distance), night (hotel)
quantity_original # raw value from source
unit_original     # raw unit string from source ("GAL", "MWH", "M3", etc.)
```

Conversion happens at parse time. The original is kept for traceability. Unit conversion factors are:
- Fuel: gallons → litres (× 3.785), m³ → litres (× 1000)
- Electricity: MWh → kWh (× 1000), GWh → kWh (× 1,000,000)
- Distance: computed via haversine if only airport codes given

Storing the original prevents the "telephone game" problem: if someone queries the normalized value and questions it, you haven't thrown away the source.

### Audit trail

```python
# Emission factor applied
emission_factor        # factor used (e.g. 2.6913 kgCO2e/L for diesel)
emission_factor_source # "DEFRA 2023"
co2e_kg                # computed result

# Data quality
is_estimated       # True if value was imputed (e.g. haversine distance, not provided)
is_suspicious      # True if statistical outlier or validation failure
suspicion_reason   # human-readable explanation

# Review lifecycle
review_status   # pending → approved | flagged | rejected
reviewed_by     # analyst email
reviewed_at     # datetime
review_note     # analyst comment

# Edit tracking
is_edited       # True if any field was changed post-ingestion
edit_history    # [{field, old, new, by, at}] — append-only log

# Audit lock
is_locked       # True when row is sent to auditor
locked_at       # datetime
```

`is_locked` is the one-way ratchet. Once set, the API rejects any further review or edit. The pre-lock state (all fields + full edit_history) is what the auditor sees.

---

## Indexes

```python
Index(fields=['client', 'scope', 'activity_date'])  # primary reporting query
Index(fields=['client', 'review_status'])            # analyst dashboard filter
Index(fields=['job'])                                # job detail view
```

---

## What this model deliberately does NOT do

1. **Separate EF lookup table** — emission factors are stored inline per-record. A dedicated `EmissionFactor` table (by fuel type × year × region) would be more correct for a production system, but would add a join to every query and a migration every DEFRA update cycle. For a prototype, inline is the right tradeoff. The `emission_factor_source` field makes it clear which version was applied.

2. **Soft delete** — records are hard-deleted if rejected. In production you'd want soft delete + archival so rejected rows are preserved for the audit trail.

3. **Period aggregation** — utility billing periods (`period_start`, `period_end`) are stored but not yet prorated to calendar months. Real GHG reporting requires month-aligned figures. The fields are there; the proration logic is not.
