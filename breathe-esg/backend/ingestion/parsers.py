"""
Parsers for each source type.
Each parser receives raw data and returns a list of normalized dicts
ready to be saved as EmissionRecord instances.
"""
import csv
import io
import json
import math
from datetime import date, datetime
from decimal import Decimal


# ─────────────────────────────────────────────────────────────────────────────
# Unit conversion helpers
# ─────────────────────────────────────────────────────────────────────────────

FUEL_TO_LITRES = {
    'L': Decimal('1'),
    'LITRE': Decimal('1'),
    'LITRES': Decimal('1'),
    'LITER': Decimal('1'),
    'LITERS': Decimal('1'),
    'GAL': Decimal('3.78541'),
    'GALLON': Decimal('3.78541'),
    'GALLONS': Decimal('3.78541'),
    'M3': Decimal('1000'),
    'KG': Decimal('1.2'),       # diesel approx density
}

SAP_DATE_FORMATS = ['%Y%m%d', '%d.%m.%Y', '%d/%m/%Y', '%Y-%m-%d', '%m/%d/%Y']

# DEFRA 2023 emission factors (kgCO2e per unit)
EF = {
    'diesel_L': Decimal('2.6913'),
    'petrol_L': Decimal('2.1568'),
    'natural_gas_m3': Decimal('2.0230'),
    'electricity_kWh': Decimal('0.2072'),   # UK grid average; real impl uses location
    'flight_km_economy': Decimal('0.1556'),
    'flight_km_business': Decimal('0.4296'),
    'hotel_night': Decimal('31.30'),
    'car_km': Decimal('0.1700'),
    'taxi_km': Decimal('0.2089'),
    'rail_km': Decimal('0.0353'),
}


def parse_sap_date(val: str) -> date:
    val = str(val).strip()
    for fmt in SAP_DATE_FORMATS:
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {val!r}")


# ─────────────────────────────────────────────────────────────────────────────
# SAP Flat File Parser
# ─────────────────────────────────────────────────────────────────────────────

# Column mapping handles German and English SAP headers
SAP_COLUMN_MAP = {
    # German → canonical
    'Buchungsdatum': 'posting_date',
    'Werk': 'plant',
    'Material': 'material',
    'Materialbezeichnung': 'material_desc',
    'Menge': 'quantity',
    'Mengeneinheit': 'unit',
    'Bewegungsart': 'movement_type',
    'Kostenstelle': 'cost_center',
    # English variants
    'Posting Date': 'posting_date',
    'Posting_Date': 'posting_date',
    'Plant': 'plant',
    'Material Number': 'material',
    'Material_Number': 'material',
    'Material Description': 'material_desc',
    'Material_Description': 'material_desc',
    'Quantity': 'quantity',
    'Unit': 'unit',
    'UoM': 'unit',
    'Movement Type': 'movement_type',
    'Movement_Type': 'movement_type',
    'Cost Center': 'cost_center',
    'Cost_Center': 'cost_center',
}

FUEL_MATERIALS = {
    'DIESEL': 'diesel',
    'PETROL': 'petrol',
    'BENZIN': 'petrol',     # German
    'GAS': 'natural_gas',
    'ERDGAS': 'natural_gas',
    'FUEL OIL': 'fuel_oil',
    'HEIZÖL': 'fuel_oil',
}


def classify_material(desc: str) -> str | None:
    desc_upper = (desc or '').upper()
    for keyword, fuel_type in FUEL_MATERIALS.items():
        if keyword in desc_upper:
            return fuel_type
    return None


def parse_sap_csv(file_content: str) -> tuple[list[dict], list[dict]]:
    """
    Returns (records, errors).
    Handles: semicolon or comma delimiters, German/English headers,
    multiple date formats, unit normalization.
    """
    records = []
    errors = []

    # Detect delimiter
    sample = file_content[:2000]
    delimiter = ';' if sample.count(';') > sample.count(',') else ','

    reader = csv.DictReader(io.StringIO(file_content), delimiter=delimiter)
    raw_headers = reader.fieldnames or []

    # Build header → canonical map
    header_map = {}
    for h in raw_headers:
        h_stripped = h.strip()
        if h_stripped in SAP_COLUMN_MAP:
            header_map[h] = SAP_COLUMN_MAP[h_stripped]

    for i, row in enumerate(reader):
        row_num = i + 2  # 1-based, header is row 1
        try:
            # Remap headers
            canonical = {header_map.get(k, k.strip()): (v or '').strip() for k, v in row.items()}

            qty_raw = canonical.get('quantity', '').replace(',', '.')
            unit_raw = canonical.get('unit', 'L').upper()
            material_desc = canonical.get('material_desc', '')
            posting_date_raw = canonical.get('posting_date', '')
            plant = canonical.get('plant', '')
            movement_type = canonical.get('movement_type', '261')  # 261 = goods issue

            # Skip non-goods-issue movements (purchases, transfers)
            if movement_type and movement_type not in ('261', '201', '551'):
                continue

            fuel_type = classify_material(material_desc)
            if not fuel_type:
                errors.append({'row': row_num, 'reason': f'Unrecognized material: {material_desc!r}', 'raw': dict(row)})
                continue

            qty = Decimal(qty_raw)
            posting_date = parse_sap_date(posting_date_raw)

            # Normalize to litres
            unit_factor = FUEL_TO_LITRES.get(unit_raw, Decimal('1'))
            qty_litres = qty * unit_factor

            # Emission factor
            ef_key = f'{fuel_type}_L' if fuel_type != 'natural_gas' else 'natural_gas_m3'
            ef_val = EF.get(ef_key)
            co2e = qty_litres * ef_val if ef_val else None

            records.append({
                'scope': 1,
                'category': 'fuel',
                'activity_date': posting_date,
                'description': material_desc,
                'location': plant,
                'quantity': qty_litres,
                'unit': 'L',
                'quantity_original': qty,
                'unit_original': unit_raw,
                'emission_factor': ef_val,
                'emission_factor_source': 'DEFRA 2023',
                'co2e_kg': co2e,
                'source_raw': dict(row),
                'source_row_id': str(row_num),
                'is_suspicious': qty_litres > Decimal('50000'),
                'suspicion_reason': 'Quantity exceeds 50,000 L — possible unit mismatch' if qty_litres > Decimal('50000') else '',
            })
        except Exception as e:
            errors.append({'row': row_num, 'reason': str(e), 'raw': dict(row)})

    return records, errors


# ─────────────────────────────────────────────────────────────────────────────
# Utility (Green Button / Portal CSV) Parser
# ─────────────────────────────────────────────────────────────────────────────

ELEC_UNIT_TO_KWH = {
    'KWH': Decimal('1'),
    'MWH': Decimal('1000'),
    'GWH': Decimal('1000000'),
    'KVAR': Decimal('1'),   # reactive power, flag it
}


def parse_utility_csv(file_content: str) -> tuple[list[dict], list[dict]]:
    """
    Handles Green Button CSV and generic utility portal exports.
    Expected columns: meter_id, billing_period_start, billing_period_end,
                      consumption, unit, tariff, site_name
    Billing periods don't align with calendar months — we store both period dates.
    """
    records = []
    errors = []

    reader = csv.DictReader(io.StringIO(file_content))
    for i, row in enumerate(reader):
        row_num = i + 2
        try:
            raw = {k.strip(): (v or '').strip() for k, v in row.items()}

            start_raw = raw.get('billing_period_start') or raw.get('period_start') or raw.get('start_date', '')
            end_raw = raw.get('billing_period_end') or raw.get('period_end') or raw.get('end_date', '')
            consumption_raw = raw.get('consumption') or raw.get('kwh') or raw.get('usage', '0')
            unit_raw = (raw.get('unit') or raw.get('uom') or 'kWh').upper().replace(' ', '')
            meter_id = raw.get('meter_id') or raw.get('meter') or ''
            site = raw.get('site_name') or raw.get('site') or raw.get('location') or ''
            tariff = raw.get('tariff') or raw.get('rate') or ''

            consumption = Decimal(consumption_raw.replace(',', ''))
            period_start = datetime.strptime(start_raw, '%Y-%m-%d').date() if start_raw else None
            period_end = datetime.strptime(end_raw, '%Y-%m-%d').date() if end_raw else None
            activity_date = period_end or period_start or date.today()

            kwh_factor = ELEC_UNIT_TO_KWH.get(unit_raw, Decimal('1'))
            consumption_kwh = consumption * kwh_factor

            ef = EF['electricity_kWh']
            co2e = consumption_kwh * ef

            is_suspicious = False
            suspicion_reason = ''
            if consumption_kwh > Decimal('500000'):
                is_suspicious = True
                suspicion_reason = 'Consumption >500 MWh in one period — verify meter or unit'
            if period_start and period_end:
                days = (period_end - period_start).days
                if days < 15 or days > 95:
                    is_suspicious = True
                    suspicion_reason += f' Billing period {days} days (unusual).'

            records.append({
                'scope': 2,
                'category': 'electricity',
                'activity_date': activity_date,
                'period_start': period_start,
                'period_end': period_end,
                'description': f'Meter {meter_id} — {tariff}',
                'location': site or meter_id,
                'quantity': consumption_kwh,
                'unit': 'kWh',
                'quantity_original': consumption,
                'unit_original': unit_raw,
                'emission_factor': ef,
                'emission_factor_source': 'DEFRA 2023 UK grid average',
                'co2e_kg': co2e,
                'source_raw': raw,
                'source_row_id': str(row_num),
                'is_suspicious': is_suspicious,
                'suspicion_reason': suspicion_reason.strip(),
            })
        except Exception as e:
            errors.append({'row': row_num, 'reason': str(e), 'raw': dict(row)})

    return records, errors


# ─────────────────────────────────────────────────────────────────────────────
# Travel JSON Parser (Concur / Navan shape)
# ─────────────────────────────────────────────────────────────────────────────

AIRPORT_COORDS = {
    'LHR': (51.4700, -0.4543), 'JFK': (40.6413, -73.7781),
    'DEL': (28.5562, 77.1000), 'BOM': (19.0896, 72.8656),
    'DXB': (25.2532, 55.3657), 'SIN': (1.3644, 103.9915),
    'CDG': (49.0097, 2.5479),  'FRA': (50.0379, 8.5622),
    'ORD': (41.9742, -87.9073),'LAX': (33.9425, -118.4081),
    'BLR': (13.1986, 77.7066), 'HYD': (17.2403, 78.4294),
    'MAA': (12.9941, 80.1709), 'CCU': (22.6547, 88.4467),
    'AMD': (23.0772, 72.6347), 'PNQ': (18.5822, 73.9197),
}


def haversine_km(lat1, lon1, lat2, lon2) -> Decimal:
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return Decimal(str(round(2 * R * math.asin(math.sqrt(a)), 2)))


def flight_distance_km(origin: str, dest: str) -> Decimal | None:
    c1 = AIRPORT_COORDS.get(origin.upper())
    c2 = AIRPORT_COORDS.get(dest.upper())
    if c1 and c2:
        return haversine_km(*c1, *c2)
    return None


def parse_travel_json(payload: list | dict) -> tuple[list[dict], list[dict]]:
    """
    Concur/Navan expense report shape:
    [{
      "report_id": "RPT-001",
      "expense_date": "2024-03-15",
      "expense_type": "AIRFARE" | "HOTEL" | "CAR_RENTAL" | "TAXI" | "TRAIN",
      "traveler": "Jane Smith",
      "origin": "LHR",          # flights
      "destination": "JFK",
      "cabin_class": "economy" | "business" | "first",
      "distance_km": 5541,      # optional, we compute if missing
      "nights": 2,              # hotels
      "amount_usd": 450.00,
      "vendor": "Marriott",
    }]
    """
    records = []
    errors = []

    if isinstance(payload, dict):
        # Handle wrapped: {"expenses": [...]}
        payload = payload.get('expenses') or payload.get('data') or payload.get('items') or [payload]

    for i, item in enumerate(payload):
        try:
            exp_type = (item.get('expense_type') or '').upper()
            exp_date = datetime.strptime(item['expense_date'], '%Y-%m-%d').date()
            report_id = str(item.get('report_id', i + 1))

            if exp_type in ('AIRFARE', 'AIR', 'FLIGHT'):
                origin = (item.get('origin') or '').upper().strip()
                dest = (item.get('destination') or '').upper().strip()
                cabin = (item.get('cabin_class') or 'economy').lower()

                dist = None
                if item.get('distance_km'):
                    dist = Decimal(str(item['distance_km']))
                else:
                    dist = flight_distance_km(origin, dest)

                if not dist:
                    errors.append({'row': i+1, 'reason': f'Unknown airport codes {origin}/{dest}, no distance', 'raw': item})
                    continue

                ef_key = 'flight_km_business' if cabin in ('business', 'first') else 'flight_km_economy'
                ef = EF[ef_key]
                co2e = dist * ef

                records.append({
                    'scope': 3,
                    'category': 'flight',
                    'activity_date': exp_date,
                    'description': f'{origin}→{dest} ({cabin})',
                    'location': f'{origin}/{dest}',
                    'quantity': dist,
                    'unit': 'km',
                    'quantity_original': Decimal(str(item.get('distance_km', 0))),
                    'unit_original': 'km',
                    'emission_factor': ef,
                    'emission_factor_source': 'DEFRA 2023',
                    'co2e_kg': co2e,
                    'source_raw': item,
                    'source_row_id': report_id,
                    'is_estimated': not bool(item.get('distance_km')),
                    'is_suspicious': dist > Decimal('20000'),
                    'suspicion_reason': 'Distance >20,000 km — check routing' if dist > Decimal('20000') else '',
                })

            elif exp_type in ('HOTEL', 'ACCOMMODATION', 'LODGING'):
                nights = Decimal(str(item.get('nights', 1)))
                ef = EF['hotel_night']
                co2e = nights * ef
                vendor = item.get('vendor', 'Unknown')
                records.append({
                    'scope': 3,
                    'category': 'hotel',
                    'activity_date': exp_date,
                    'description': f'{vendor} — {nights} night(s)',
                    'location': item.get('city') or item.get('destination') or '',
                    'quantity': nights,
                    'unit': 'night',
                    'quantity_original': nights,
                    'unit_original': 'night',
                    'emission_factor': ef,
                    'emission_factor_source': 'DEFRA 2023',
                    'co2e_kg': co2e,
                    'source_raw': item,
                    'source_row_id': report_id,
                    'is_estimated': False,
                    'is_suspicious': nights > 30,
                    'suspicion_reason': 'Stay >30 nights — verify' if nights > 30 else '',
                })

            elif exp_type in ('CAR_RENTAL', 'TAXI', 'RIDESHARE', 'TRAIN', 'RAIL', 'GROUND'):
                dist = Decimal(str(item.get('distance_km', 50)))  # default 50km if missing
                ef_key = 'rail_km' if exp_type in ('TRAIN', 'RAIL') else ('taxi_km' if exp_type in ('TAXI', 'RIDESHARE') else 'car_km')
                ef = EF[ef_key]
                co2e = dist * ef
                records.append({
                    'scope': 3,
                    'category': 'ground_transport',
                    'activity_date': exp_date,
                    'description': f'{exp_type.replace("_", " ").title()}',
                    'location': item.get('city') or '',
                    'quantity': dist,
                    'unit': 'km',
                    'quantity_original': dist,
                    'unit_original': 'km',
                    'emission_factor': ef,
                    'emission_factor_source': 'DEFRA 2023',
                    'co2e_kg': co2e,
                    'source_raw': item,
                    'source_row_id': report_id,
                    'is_estimated': not bool(item.get('distance_km')),
                    'is_suspicious': False,
                    'suspicion_reason': '',
                })
            else:
                errors.append({'row': i+1, 'reason': f'Unknown expense_type: {exp_type!r}', 'raw': item})

        except Exception as e:
            errors.append({'row': i+1, 'reason': str(e), 'raw': item})

    return records, errors
