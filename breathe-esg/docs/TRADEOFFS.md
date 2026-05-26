# TRADEOFFS.md — Three Things Deliberately Not Built

---

## 1. Calendar-month proration of utility billing periods

**What it is:** Utility bills cover irregular periods (e.g. Jan 7 – Feb 6, 31 days). GHG reporting is done monthly and annually. To report "January electricity consumption," you need to prorate: (25 days of this bill ÷ 31 days total) × consumption = January allocation, plus the remainder carries into February.

**Why I didn't build it:** Proration sounds simple but is genuinely hard to get right. Edge cases include: bills covering more than two months (rural meters sometimes billed quarterly), overlapping bills from meter replacements, estimated reads that get corrected in the next bill, and partial-year onboarding where historical periods are missing. Getting proration wrong silently produces incorrect GHG totals — worse than not prorating at all, because the error is invisible.

The data model is ready for it: `period_start`, `period_end`, and `activity_date` are all stored. The proration logic belongs in a separate, tested calculation layer, not in the ingestion parser.

**What a real deployment needs:** A `PeriodAllocation` model that takes each `EmissionRecord` with a billing period and produces month-aligned child records. This should be a separate pass run after ingestion, with its own review step.

---

## 2. Location-aware emission factors

**What it is:** The emission factor for electricity varies dramatically by geography. UK grid: 0.207 kgCO2e/kWh. India (CEA 2023): 0.716 kgCO2e/kWh. Texas (ERCOT): 0.386. Norwegian hydro grid: ~0.011. Using the wrong factor produces errors of 3–5× in Scope 2 calculations.

**Why I didn't build it:** Building a correct, maintained emission factor library requires: (a) a `EmissionFactorLibrary` table keyed by (fuel_type, region, year, source), (b) a region inference layer that maps a site/meter/airport to the right factor, (c) a process for annual updates when DEFRA, CEA, or EPA publish new numbers. This is a significant feature, not a parser.

I used DEFRA 2023 UK factors uniformly and flagged this clearly in DECISIONS.md and SOURCES.md. The `emission_factor_source` field on every record makes the assumption explicit and auditable.

**What a real deployment needs:** A factor library table, a region-to-factor resolver, and a recalculation job that updates `co2e_kg` when factors are updated (with version history so old calculations are preserved).

---

## 3. Authentication and role-based access

**What it is:** In a real deployment: analysts log in, have client-specific permissions, can only see their client's data, and an audit log tracks who approved what. Admins can onboard clients and manage users.

**Why I didn't build it:** The assignment asks for a prototype that demonstrates ingestion and review. Adding Django auth, JWT tokens, permission classes, and a user management UI would double the build time while adding zero value to the parts being evaluated (data model, parsing, review workflow). The `reviewed_by` and `ingested_by` fields accept an email string — the hook for a real auth system is already there.

**What a real deployment needs:** Django's built-in auth + DRF token authentication, a `ClientMembership` table linking users to clients with roles (analyst, admin, auditor), and permission classes on every view that filter by `request.user`'s client memberships. The audit trail fields (`reviewed_by`, `locked_at`, `edit_history`) are already structured to record user identity once auth is wired up.
