# SOURCES.md — Data Source Research

For each source: what I researched, what I learned, what the sample data looks like and why, and what would break in a real deployment.

---

## Source 1: SAP — Fuel & Procurement

### What I researched

SAP's primary mechanisms for extracting goods movement data:
- **Transaction MB51** — material document list. Exports goods movements by material, plant, and movement type. The standard analyst export is a delimited text file via "List → Export → Local File."
- **Transaction MB52** — warehouse stocks, but this is stock-on-hand, not consumption. Less relevant for emissions.
- **IDoc MATMAS/MBGMCR** — SAP's native EDI format. Used for system-to-system integration, not ad-hoc exports.
- **OData service /SCMTMS/SRA012** and similar — available in S/4HANA, requires Gateway configuration.
- **BAPI BAPI_GOODSMVT_GETDETAIL** — programmatic access, requires RFC connection.

I also reviewed the SAP Help documentation for movement types (261 = goods issue to cost center, 201 = goods issue to order, 551 = scrapping) and the MB51 field list.

### What I learned

1. **Column headers depend on the system language.** A German-language SAP system exports "Buchungsdatum" (posting date), "Menge" (quantity), "Mengeneinheit" (unit of measure), "Werk" (plant). English systems export "Posting Date", "Quantity", "UoM", "Plant". The same company can have inconsistent language settings across systems acquired through M&A.

2. **The delimiter is usually semicolon, not comma.** MB51 exports use `;` by default in European locales.

3. **Plant codes are opaque.** "WERK_MUM" means nothing without a plant master lookup table. In production, you'd need a `PlantMaster` table to resolve codes to addresses and business units.

4. **Not all movement types are consumption.** A naive parser ingesting all movements would double-count: goods issues (261) AND goods receipts (101) for the same material. You must filter to consumption movements only.

5. **Date formats vary.** YYYYMMDD is the SAP internal format. Exports may reformat to DD.MM.YYYY or MM/DD/YYYY depending on locale settings.

### What the sample data looks like and why

`sample_data/sap_fuel_sample.csv` uses:
- **German headers** to reflect the most common mis-configuration we'd encounter
- **Semicolon delimiter** (authentic SAP export default)
- **YYYYMMDD dates** (SAP internal format, appears in exports when date formatting is off)
- **Plant codes** WERK_MUM, WERK_DEL, WERK_HYD (Mumbai, Delhi, Hyderabad — realistic Indian enterprise)
- **Materials**: diesel, petrol (Benzin in German), natural gas (Erdgas), fuel oil (Heizöl), lubricating oil (Schmieröl)
- **One intentional outlier**: row with 75,000L diesel in a single goods issue — flags as suspicious (>50,000L threshold)
- **One lubricating oil row**: this should be rejected (Schmieröl is not a combustion fuel)

### What would break in a real deployment

1. **Plant-to-location resolution.** "WERK_MUM" needs to map to an address for location-based Scope 2 (if electricity is also tracked here). Without the plant master, reporting by facility is impossible.
2. **Material master lookup.** Classifying materials by combustion type requires a material master. A material code of "100-DIES-001" is meaningless without the description. Our parser relies on the description column — if it's blank or abbreviated differently, classification fails.
3. **Split deliveries.** A large fuel purchase may be split across multiple goods receipts/issues that net to the real consumption figure. Without understanding the procurement flow, you'll over- or under-count.
4. **Negative quantities.** Returns and reversals produce negative quantity rows that must be handled (subtract from consumption, not treated as separate records).

---

## Source 2: Utility — Electricity

### What I researched

- **Green Button standard** (NAESB REQ.21) — US standard for customer energy data. Utilities expose an ESPI (Energy Service Provider Interface) API. Customer authorizes access via OAuth. Data is XML (ATOM feed) or CSV.
- **Green Button Download My Data** — the simpler version: customer downloads a CSV or XML file from the utility portal. No API involved.
- **Indian utility portals** — MSEDCL (Maharashtra), BESCOM (Bangalore), TSSPDCL (Telangana) all offer portal logins where a facilities manager can download billing history as CSV. The format varies by utility with no standard.
- **BEIS/DEFRA guidance** on Scope 2 reporting requirements.

### What I learned

1. **Billing periods never align with calendar months.** A meter is read on the day the technician visits. Billing cycles drift. A "January bill" might cover Dec 28 – Jan 27. This is universal, not an edge case.
2. **Units are inconsistent.** Residential meters report in kWh. Large industrial consumers get MWh. Some older meters report in units of 10 kWh. The unit column must be treated as untrusted.
3. **Tariff structure affects the data.** HT (High Tension) industrial consumers pay differently and may have demand charges separate from consumption charges. The consumption figure is what matters for GHG; the tariff structure is metadata.
4. **Multi-meter sites are common.** A single campus might have 5 meters. They all need to be summed for total site consumption, but kept separate for anomaly detection (if one meter suddenly drops to zero, it may have been disconnected, not reduced consumption).

### What the sample data looks like and why

`sample_data/utility_electricity_sample.csv` uses:
- **Non-calendar billing periods** (e.g. Jan 7 – Feb 6) — the central realistic complexity
- **Mixed units** (kWh and MWh) — tests unit normalization
- **Multiple meters per site** — MTR-MUM-001 and MTR-MUM-002 are both at Mumbai HQ
- **One suspicious row**: MTR-MUM-004 reports 680,000 kWh over 3 days — flags as suspicious
- **Meter MTR-MUM-003** reports in MWh (1,250 MWh for a manufacturing unit) — realistic for large industrial

### What would break in a real deployment

1. **PDF bills.** Many Indian utilities still send PDF bills by email or only offer portal login without CSV export. Parsing tabular data from PDFs requires layout-specific rules that break on format updates.
2. **Location-specific emission factors.** The Indian grid factor (CEA 2023: 0.716 kgCO2e/kWh) is ~3.5× the UK factor I used. A deployment serving Indian clients must use the correct regional factor.
3. **Reactive power and power factor.** Industrial bills include reactive power charges (kVAR). These are not consumption; including them inflates the electricity figure. Our parser skips KVAR rows, but a more complex bill format might merge them.
4. **Estimated reads.** Utilities sometimes estimate a bill when they can't access the meter, then correct it the next period. Without a flag distinguishing "actual" vs "estimated" reads, you can't tell if a spike is real or a catch-up correction.

---

## Source 3: Corporate Travel — Concur / Navan

### What I researched

- **Concur Expense API** (SAP Concur): `GET /api/expense/expensereport/v2.0/report` returns expense report JSON. Fields include `ExpenseTypeCode`, `TransactionDate`, `VendorDescription`, `IsPersonal`, `HasAttendees`.
- **Navan (TripActions) API**: webhook events and REST API for booking data. JSON shape similar to Concur.
- **DEFRA 2023 guidance** on business travel emission calculations.
- **GHG Protocol Scope 3 Standard**, Category 6 (Business Travel).
- **ICAO Carbon Calculator** methodology for flight distance and emission factors.

### What I learned

1. **Distance is usually not in the expense report.** Concur records the amount paid, not the distance flown. Airport codes (origin/destination) may be present if the traveler booked through the platform's integrated booking tool, but not always.
2. **Cabin class changes the emission factor by 2.5–3×.** Economy: ~0.156 kgCO2e/km. Business: ~0.430 kgCO2e/km. First: ~0.570 kgCO2e/km. If cabin class is missing, you must default to economy (conservative, and GHG protocol says use best available data).
3. **Hotel nights are the simplest to calculate.** DEFRA publishes a per-night average factor (~31.3 kgCO2e/night). It's a crude average; a CDP submission would need property-specific data.
4. **Ground transport categories matter.** Taxi/rideshare (internal combustion): ~0.209 kgCO2e/km. Train: ~0.035 kgCO2e/km. Car rental: ~0.170 kgCO2e/km. The expense_type distinguishes them.
5. **Radiative forcing (RFI):** High-altitude aviation produces non-CO2 warming effects. DEFRA 2023 does not include RFI in their simplified methodology (they note it as contested). I followed DEFRA's approach.

### What the sample data looks like and why

`sample_data/travel_expenses_sample.json` includes:
- **Indian corporate travel patterns** (DEL→LHR, BOM→SIN, HYD→JFK, BLR→CDG) — realistic for a company with international sales/tech operations
- **Mixed cabin classes** — business for senior travel (Priya Sharma), economy for technical (Rahul Mehta)
- **Hotel stays** with real vendor names — not "Hotel A"
- **Ground transport** — Grab taxi in Singapore (realistic for business travel there), Paris taxi, Amtrak (New York trip)
- **One record without distance_km** (the final Paris taxi entry) — tests the default distance assumption and `is_estimated` flag
- **Multiple expense types in one report** — realistic (flights + hotels + ground in RPT-2024-0312)

### What would break in a real deployment

1. **Personal vs. business expenses.** Concur has an `IsPersonal` flag. Personal expenses on a corporate card must be excluded. Our parser trusts the data; a real deployment would filter on this flag.
2. **Multi-leg journeys.** A DEL→DXB→LHR flight appears as one expense row. Our haversine calculation computes DEL→LHR direct. The real footprint (two shorter hops at lower altitude) is different, though in practice the error is small.
3. **Airport code coverage.** Our lookup table has ~20 airports. Real deployments need IATA's full database (~10,000 airports). Unknown codes currently produce errors rather than estimates.
4. **Currency.** Amounts are in USD in our sample. Real Concur exports may use transaction currency or reimbursement currency. We don't use the amount for GHG calculation (only for cost reporting), but the field is there.
5. **Expense policy violations.** Some rows in a real Concur export are flagged as policy violations or pending approval. Pre-approved-only ingestion requires filtering on report status, which varies by company's Concur configuration.
