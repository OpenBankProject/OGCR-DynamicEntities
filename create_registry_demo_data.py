"""Create demo records for the registry endpoint (/registry/activities).

`create_example_data.py` writes one example row per entity, so the registry shows
a single activity. This adds 4 operators and 10 activities, plus the
activity_verification and certificate_of_compliance rows the registry joins,
chosen so every case the endpoint renders appears at least once:

  * verified, pending, failed and no verification at all (verified/unverified)
  * a current certificate, an expired one, a suspended one and none
  * one activity with two certificates, so "latest by issue_date" is exercised
  * several countries, operators and activity types

Required fields this script does not set keep their spreadsheet example, the
same as `create_example_data.py`. Optional fields are only sent when set here.
References to parcel, certification_scheme and certification_body use the
first existing row, so run `create_example_data.py` first.

Rows already present are skipped (operators, activities and certificates by id;
verifications by activity_id + status_code), so it is safe to re-run.

Usage:
    python3 create_registry_demo_data.py [path/to/min_field_matrix.xlsx] [--token TOKEN] [--activities N]

--activities N (default 10) generates activities 11..N on top of the 10 written
out below, with verifications and certificates in a repeating pattern.
"""

import argparse
import logging
import sys

import requests

from obp_client import token as default_token, obp_host, session
from obp_space import record_path
from parse_minimum_fields import parse_xlsx_entities
from create_example_data import clean_key, coerce_value, create_object, DEFAULT_SPREADSHEET

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

OPERATORS = [
    {"operator_id": "op_REG01", "legal_name": "Northfield Carbon GmbH", "country_id": "DE"},
    {"operator_id": "op_REG02", "legal_name": "Terre Vive SAS", "country_id": "FR"},
    {"operator_id": "op_REG03", "legal_name": "Basalt Removal ehf", "country_id": "IS"},
    {"operator_id": "op_REG04", "legal_name": "Nordic Timber Storage Oy", "country_id": "FI"},
]

CARBON_FARMING = "CARBON_FARMING"
PERMANENT = "PERMANENT_CARBON_REMOVAL"
PRODUCTS = "CARBON_STORAGE_IN_PRODUCTS"


def _activity(activity_id, name, activity_type, operator_id, country_id, city, start, end, summary, internal_note):
    # internal_note is hidden from public access (column R), so the registry shows it to
    # logged in callers with the activity read Role only.
    return {
        "activity_id": activity_id,
        "name": name,
        "summary": summary,
        "activity_type": activity_type,
        "operator_id": operator_id,
        "country_id": country_id,
        "city": city,
        "start_date": start,
        "end_date": end,
        "monitoring_period_start_date": start,
        "monitoring_period_end_date": end,
        "internal_note": internal_note,
    }


ACTIVITIES = [
    _activity("a_REG01", "Brandenburg Cover Crops", CARBON_FARMING, "op_REG01", "DE", "Seelow",
              "2025-01-01", "2029-12-31", "Winter cover crops on arable parcels.",
              "Check the 2027 soil samples before certifying."),
    _activity("a_REG02", "Jutland Peatland Rewetting", CARBON_FARMING, "op_REG01", "DK", "Viborg",
              "2023-01-01", "2032-12-31", "Rewetting of drained peat soils.",
              "Water table logger on parcel 4 failed in March; data gap to be explained."),
    _activity("a_REG03", "Loire Valley Agroforestry", CARBON_FARMING, "op_REG02", "FR", "Angers",
              "2026-03-01", "2035-02-28", "Tree rows planted between cereal strips.",
              "Verification pending: planting records for the north field are missing."),
    _activity("a_REG04", "Hellisheidi Direct Air Capture", PERMANENT, "op_REG03", "IS", "Hellisheidi",
              "2024-06-01", "2034-05-31", "Captured CO2 mineralised in basalt.",
              "Injection volumes reconciled with the storage operator's report."),
    _activity("a_REG05", "Bavarian Biochar", PERMANENT, "op_REG03", "DE", "Landshut",
              "2025-09-01", "2030-08-31", "Biochar from forestry residues applied to soil.",
              "Verification failed: feedstock origin could not be traced."),
    _activity("a_REG06", "Tuscany Precision Fertilization", CARBON_FARMING, "op_REG02", "IT", "Siena",
              "2026-01-01", "2030-12-31", "Variable-rate nitrogen on vineyards and olive groves.",
              "No verification requested yet."),
    _activity("a_REG07", "Tampere Timber Frame Housing", PRODUCTS, "op_REG04", "FI", "Tampere",
              "2021-01-01", "2025-12-31", "Carbon stored in cross-laminated timber buildings.",
              "Certificate expired; renewal application not received."),
    _activity("a_REG08", "Gelderland Hedgerow Restoration", CARBON_FARMING, "op_REG01", "NL", "Arnhem",
              "2024-04-01", "2029-03-31", "Restored hedgerows and field margins.",
              "Certificate suspended after a complaint about hedge removal; under review."),
    _activity("a_REG09", "Castilla No-Till Barley", CARBON_FARMING, "op_REG02", "ES", "Valladolid",
              "2026-10-01", "2031-09-30", "No-till barley rotation.",
              "Operator asked to move the start date; not yet agreed."),
    _activity("a_REG10", "Poznan Hemp Insulation", PRODUCTS, "op_REG04", "PL", "Poznan",
              "2025-05-01", "2035-04-30", "Hemp-lime insulation panels for retrofits.",
              "Verification pending: product life-cycle assessment under review."),
]

# (activity_id, status_code). Activities not listed have no verification.
VERIFICATIONS = [
    ("a_REG01", "verified"),
    ("a_REG02", "verified"),
    ("a_REG03", "pending"),
    ("a_REG04", "verified"),
    ("a_REG05", "failed"),
    ("a_REG07", "verified"),
    ("a_REG08", "verified"),
    ("a_REG10", "pending"),
]

# (certificate_of_compliance_id, activity_id, issue_date, expiry_date, certification_status).
# a_REG02 has two, so the registry must pick the later issue_date (coc_REG02B).
CERTIFICATES = [
    ("coc_REG01", "a_REG01", "2025-06-01", "2030-06-01", "certified"),
    ("coc_REG02A", "a_REG02", "2023-03-01", "2025-03-01", "expired"),
    ("coc_REG02B", "a_REG02", "2025-04-15", "2030-04-15", "certified"),
    ("coc_REG04", "a_REG04", "2024-12-01", "2029-12-01", "certified"),
    ("coc_REG07", "a_REG07", "2021-06-01", "2024-06-01", "expired"),
    ("coc_REG08", "a_REG08", "2024-09-01", "2029-09-01", "suspended"),
]

# Places for generated activities: (country_id, city).
PLACES = [
    ("DE", "Leipzig"), ("FR", "Rennes"), ("NL", "Zwolle"), ("DK", "Aarhus"),
    ("IT", "Bologna"), ("ES", "Zaragoza"), ("PL", "Lublin"), ("FI", "Oulu"),
    ("SE", "Uppsala"), ("AT", "Graz"), ("IE", "Galway"), ("PT", "Evora"),
    ("BE", "Ghent"), ("CZ", "Brno"), ("EE", "Tartu"), ("IS", "Akureyri"),
]

# Practices for generated activity names, with the activity type they belong to.
PRACTICES = [
    ("Cover Cropping", CARBON_FARMING), ("No Till", CARBON_FARMING),
    ("Agroforestry", CARBON_FARMING), ("Peatland Rewetting", CARBON_FARMING),
    ("Hedgerow Restoration", CARBON_FARMING), ("Afforestation", CARBON_FARMING),
    ("Biochar", PERMANENT), ("Enhanced Rock Weathering", PERMANENT),
    ("Direct Air Capture", PERMANENT), ("Timber Construction", PRODUCTS),
    ("Hemp Insulation", PRODUCTS),
]


def generated(total):
    """Activities 11..`total`, with their verifications and certificates.

    Deterministic, so a re-run (or a larger `total`) skips what is stored. The
    index picks place, practice, operator and dates, and the cycles below give
    the registry a spread of verification and certificate states.
    """
    activities, verifications, certificates = [], [], []
    for n in range(len(ACTIVITIES) + 1, total + 1):
        activity_id = f"a_REG{n:02d}"
        country_id, city = PLACES[n % len(PLACES)]
        practice, activity_type = PRACTICES[n % len(PRACTICES)]
        operator_id = OPERATORS[n % len(OPERATORS)]["operator_id"]
        start_year = 2021 + n % 7
        years = 5 if n % 2 else 10
        activities.append(_activity(
            activity_id, f"{city} {practice}", activity_type, operator_id, country_id, city,
            f"{start_year}-01-01", f"{start_year + years - 1}-12-31", "",
            f"Generated activity {n}; review before certifying.",
        ))
        status = ["verified", "verified", "pending", "failed", None][n % 5]
        if status:
            verifications.append((activity_id, status))
        if status == "verified":
            issued = start_year + 1
            # Every third verified activity's certificate has expired.
            expired = n % 3 == 0
            expires = issued + (2 if expired else 5)
            certificates.append((
                f"coc_REG{n:02d}", activity_id, f"{issued}-03-01", f"{expires}-03-01",
                "expired" if expired else "certified",
            ))
    return activities, verifications, certificates


def headers(token):
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"DirectLogin token={token}"
    return h


def list_rows(entity_name, token):
    """Every stored row of `entity_name`; exits if the table cannot be read."""
    url = f"{obp_host}{record_path(entity_name)}"
    try:
        response = session.get(url, headers=headers(token))
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Could not list {entity_name}: {e}")
        sys.exit(1)
    return [r for r in response.json().get(f"{entity_name}_list", []) if isinstance(r, dict)]


def first_id(entity_name, token):
    """Id of the first stored row, for references this script does not vary."""
    ids = sorted(r[f"{entity_name}_id"] for r in list_rows(entity_name, token) if r.get(f"{entity_name}_id"))
    if not ids:
        logger.error(f"No {entity_name} rows found; run create_example_data.py first")
        sys.exit(1)
    return ids[0]


def build(entity_name, entities, values):
    """Required fields from the spreadsheet examples, overridden by `values`.

    Fields in `values` the sheet does not define are dropped with a warning.
    """
    fields = entities[entity_name]["fields"]
    sheet_fields = {clean_key(k) for k in fields}
    payload = {
        clean_key(k): coerce_value(meta)
        for k, meta in fields.items()
        if not k.endswith(" (optional)")
    }
    for field, value in values.items():
        if field in sheet_fields:
            payload[field] = value
        else:
            logger.warning(f"  ! {entity_name}: sheet has no field {field}; skipping it")
    return payload


def main():
    parser = argparse.ArgumentParser(description="Create demo operators, activities, verifications and certificates for the registry endpoint.")
    parser.add_argument("file", nargs="?", default=DEFAULT_SPREADSHEET, help=f"Spreadsheet path (default: {DEFAULT_SPREADSHEET}).")
    parser.add_argument("--token", default=default_token, help="DirectLogin token (overrides obp_client.py).")
    parser.add_argument("--activities", type=int, default=len(ACTIVITIES), metavar="N",
                        help=f"Total registry activities (default {len(ACTIVITIES)}). Above {len(ACTIVITIES)}, the rest are generated, with verifications and certificates.")
    args = parser.parse_args()
    if args.activities < len(ACTIVITIES):
        parser.error(f"--activities must be at least {len(ACTIVITIES)}")

    extra_activities, extra_verifications, extra_certificates = generated(args.activities)
    activities = ACTIVITIES + extra_activities
    verifications = VERIFICATIONS + extra_verifications
    certificates = CERTIFICATES + extra_certificates

    entities = parse_xlsx_entities(args.file)
    needed = ["operator", "activity", "activity_verification", "certificate_of_compliance"]
    missing = [n for n in needed if n not in entities]
    if missing:
        logger.error(f"Not in {args.file}: {', '.join(missing)}")
        sys.exit(1)

    countries = {r.get("country_id") for r in list_rows("country", args.token)}
    used = {r["country_id"] for r in OPERATORS + activities}
    if used - countries:
        logger.error(f"Countries not stored: {', '.join(sorted(used - countries))}; run create_example_data.py first")
        sys.exit(1)

    parcel_id = first_id("parcel", args.token)
    scheme_id = first_id("certification_scheme", args.token)
    body_id = first_id("certification_body", args.token)
    activity_country = {a["activity_id"]: a["country_id"] for a in activities}

    stored_operators = {r.get("operator_id") for r in list_rows("operator", args.token)}
    stored_activities = {r.get("activity_id") for r in list_rows("activity", args.token)}
    stored_certificates = {r.get("certificate_of_compliance_id") for r in list_rows("certificate_of_compliance", args.token)}
    stored_verifications = {(r.get("activity_id"), r.get("status_code")) for r in list_rows("activity_verification", args.token)}

    # (entity, key, already stored?, values), parents first so references resolve.
    plan = []
    for o in OPERATORS:
        plan.append(("operator", o["operator_id"], o["operator_id"] in stored_operators, o))
    for a in activities:
        values = {k: v for k, v in a.items() if v != ""}
        plan.append(("activity", a["activity_id"], a["activity_id"] in stored_activities, values))
    for activity_id, status in verifications:
        plan.append((
            "activity_verification", f"{activity_id}/{status}", (activity_id, status) in stored_verifications,
            {"activity_id": activity_id, "parcel_id": parcel_id, "status_code": status, "status_message": ""},
        ))
    for cert_id, activity_id, issued, expires, status in certificates:
        plan.append((
            "certificate_of_compliance", cert_id, cert_id in stored_certificates,
            {
                "certificate_of_compliance_id": cert_id,
                "activity_id": activity_id,
                "certification_scheme_id": scheme_id,
                "certification_body_id": body_id,
                "country_id": activity_country[activity_id],
                "issue_date": issued,
                "expiry_date": expires,
                "certification_status": status,
            },
        ))

    created = skipped = failed = 0
    for entity_name, key, present, values in plan:
        if present:
            skipped += 1
            continue
        try:
            create_object(entity_name, build(entity_name, entities, values), token=args.token)
            logger.info(f"  ✓ Created {entity_name} {key}")
            created += 1
        except requests.exceptions.HTTPError as e:
            detail = e.response.text if e.response is not None else str(e)
            logger.error(f"  ✗ Failed {entity_name} {key}: {detail}")
            failed += 1

    logger.info(f"Registry Demo Data Summary: {created} created, {skipped} already present, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
