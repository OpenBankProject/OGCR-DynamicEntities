"""Create one dummy object per OGCR dynamic entity, driven by the spreadsheet.

Field values are taken from the spreadsheet `example` column (option 2), while
foreign-key fields are overwritten with the real id of the referenced object so
the dummy data is referentially consistent (option 1).

How it works:
  1. Parse the spreadsheet (`parse_xlsx_entities`) to get each entity's fields,
     declared types and example values.
  2. Pre-compute a canonical id for every entity that owns a `<entity>_id` field
     (taken from that field's example). Because all *_id fields are plain
     strings (OBP does not enforce referential integrity here), these ids can be
     assigned up front and reused as foreign keys regardless of creation order.
  3. For each entity, build a payload from the example values, then override:
       - its own `<entity>_id`        -> the canonical id for this entity
       - any `<other_entity>_id` field -> the canonical id of that other entity
       - `compliance_certificate_id`   -> certificate_of_compliance's id (alias)
  4. POST one object per entity.

Usage:
    python3 create_dummy_data.py [path/to/min_field_matrix.xlsx] [--token TOKEN]
"""

import argparse
import json
import logging
import re

import requests

from obp_client import token as default_token, obp_host
from parse_minimum_fields import parse_xlsx_entities
from ogcr_log_entity import (
    ensure_log_entity,
    log_event,
    LOG_ENTITY_NAME,
    EVENT_CREATED,
    EVENT_FAILED,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

BASE_URL = obp_host
DEFAULT_SPREADSHEET = "min_field_matrix.xlsx"

# Types OBP treats as non-string; anything else falls back to string.
NON_STRING_TYPES = {"integer", "number", "boolean", "json", "DATE_WITH_DAY"}
# Case-insensitive lookup so a sheet value of "Integer" maps to "integer".
_TYPE_BY_LOWER = {t.lower(): t for t in NON_STRING_TYPES}
# Per-type default value used when the sheet has no example (mirrors the
# entity-definition builder's defaults so data matches the created schema).
_TYPE_DEFAULT_VALUE = {
    "integer": 1,
    "number": 1.0,
    "boolean": True,
    "json": {},
    "DATE_WITH_DAY": "2020-01-01",
}

# Foreign-key field names that do not follow the `<entity>_id` convention.
FK_ALIASES = {
    "compliance_certificate_id": "certificate_of_compliance",
}

# Nice-to-have creation order (parents first). Any entity not listed is appended
# in spreadsheet order. Order is cosmetic only - ids are pre-computed.
PREFERRED_ORDER = [
    "operator",
    "land_manager",
    "parcel",
    "certification_scheme",
    "certification_body",
    "monitoring_plan",
    "activity",
    "activity_plan",
    "certificate_of_compliance",
    "parcel_owner_verification",
    "activity_verification",
    "activity_parcel_verification",
    "parcel_monitoring_period_verification",
    "activity_monitoring_period_verification",
    "audit_report",
]


def print_separator(char="=", length=80):
    logger.info(char * length)


def clean_key(raw_key):
    """Strip the ' (optional)' suffix used to mark optional fields."""
    return raw_key[:-len(" (optional)")] if raw_key.endswith(" (optional)") else raw_key


def coerce_value(field_meta):
    """Turn a parsed field's example/type into a POST-ready value.

    Mirrors the coercion used when building the entity definition so the value
    matches the schema property type OBP created.
    """
    declared = field_meta.get("value") if isinstance(field_meta, dict) else None
    example = field_meta.get("example") if isinstance(field_meta, dict) else field_meta

    # Match the declared type case-insensitively ("Integer" -> "integer").
    prop_type = _TYPE_BY_LOWER.get(declared.strip().lower(), "string") if isinstance(declared, str) else "string"

    # No example in the sheet: return a schema-appropriate default rather than
    # leaking the declared type string (e.g. "Integer") as the value.
    if example is None:
        return _TYPE_DEFAULT_VALUE.get(prop_type, "sample")

    # Normalise the raw example to a stripped string for parsing.
    s = example
    if isinstance(s, str):
        s = s.strip()
        if len(s) >= 2 and ((s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'"))):
            s = s[1:-1].strip()

    if prop_type == "integer":
        try:
            return int(str(s))
        except Exception:
            m = re.search(r"-?\d+", str(s))
            return int(m.group()) if m else 1
    if prop_type == "number":
        try:
            return float(str(s))
        except Exception:
            return 1.0
    if prop_type == "boolean":
        return str(s).strip().lower() == "true"
    if prop_type == "json":
        if isinstance(s, (dict, list)):
            return s
        try:
            return json.loads(s)
        except Exception:
            return {}
    # DATE_WITH_DAY and string
    text = str(s) if s not in (None, "") else "sample"
    return text


def fk_target(entity_name, clean_field, entity_names):
    """Return the entity a `<x>_id` field references, or None if not a FK."""
    if not clean_field.endswith("_id"):
        return None
    base = clean_field[:-len("_id")]
    if base == entity_name:
        return None  # this entity's own primary id, not a foreign key
    if base in entity_names:
        return base
    return FK_ALIASES.get(clean_field)


def reference_target(declared_type):
    """Return the target entity of an OBP `reference:<entity>` typed field, else None.

    Handles both our dynamic entities (`reference:operator`) and OBP static
    entities (`reference:BankAccount:bankId&accountId`); the caller decides
    whether the returned name is one we actually create.
    """
    if isinstance(declared_type, str) and declared_type.startswith("reference:"):
        return declared_type.split(":", 2)[1]
    return None


def build_canonical_ids(entities):
    """Canonical id per entity that owns a `<entity>_id` field."""
    canonical = {}
    for ename, wrap in entities.items():
        fields = wrap.get("fields", {})
        for raw_key, meta in fields.items():
            if clean_key(raw_key) == f"{ename}_id":
                canonical[ename] = coerce_value(meta)
                break
    return canonical


def build_payload(entity_name, wrap, canonical, entity_names, real_ids):
    """Build a POST payload, resolving foreign keys to real ids.

    `real_ids` maps an already-created entity -> the id OBP actually stored for
    it. It is pre-seeded from `canonical` and upgraded to each create response's
    id as objects are created (parents first), so an OBP-typed `reference:<x>`
    field always points at a real, existing record of `<x>`.

    Returns `(payload, references)`, where `references` is a list of
    `{field, target, resolution, value}` dicts describing every `reference:<x>`
    field on the entity and how it resolved — `resolved` when a real created id
    was used, or `fallback` when the spreadsheet example value was used instead.
    The caller records this list in the log entity.
    """
    payload = {}
    references = []
    for raw_key, meta in wrap.get("fields", {}).items():
        cf = clean_key(raw_key)
        declared = meta.get("value") if isinstance(meta, dict) else None

        # This entity's own primary id.
        if cf == f"{entity_name}_id":
            payload[cf] = canonical.get(entity_name, coerce_value(meta))
            continue

        # OBP `reference:<entity>` foreign key -> the real id of that entity.
        ref = reference_target(declared)
        if ref is not None:
            if real_ids.get(ref) is not None:
                value = real_ids[ref]
                resolution = "resolved"
            else:
                # Reference to a static OBP entity (Bank, BankAccount, ...) or an
                # entity we don't create here: fall back to the example value.
                value = coerce_value(meta)
                resolution = "fallback"
                logger.warning(
                    f"{entity_name}.{cf}: reference target '{ref}' is not a created "
                    f"dynamic entity; using the spreadsheet example value"
                )
            payload[cf] = value
            references.append(
                {"field": cf, "target": ref, "resolution": resolution, "value": str(value)}
            )
            continue

        # Plain-string `<entity>_id` foreign key (not declared as a reference type).
        target = fk_target(entity_name, cf, entity_names)
        if target and target in canonical:
            payload[cf] = canonical[target]
            continue

        payload[cf] = coerce_value(meta)
    return payload, references


def create_object(entity_name, data, token=None):
    url = f"{BASE_URL}/obp/dynamic-entity/{entity_name}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"DirectLogin token={token}"
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()


def main():
    parser = argparse.ArgumentParser(description="Create dummy objects for the OGCR dynamic entities from the spreadsheet.")
    parser.add_argument("file", nargs="?", default=DEFAULT_SPREADSHEET, help=f"Spreadsheet path (default: {DEFAULT_SPREADSHEET}).")
    parser.add_argument("--token", default=default_token, help="DirectLogin token (overrides obp_client.py).")
    parser.add_argument("--no-log", action="store_true", help=f"Do not record creation/errors/fallbacks in the {LOG_ENTITY_NAME} dynamic entity.")
    args = parser.parse_args()

    logger.info("Starting Dummy Data Creation Script")
    print_separator()

    entities = parse_xlsx_entities(args.file)
    if not entities:
        logger.error(f"No entities parsed from {args.file}")
        return

    # Ensure the audit-log dynamic entity exists; if unavailable, carry on
    # without logging rather than failing the data creation.
    log_enabled = False
    if not args.no_log:
        log_enabled = ensure_log_entity(token=args.token) is not None
        if not log_enabled:
            logger.warning(f"Audit logging disabled: {LOG_ENTITY_NAME} is unavailable")
    entity_names = set(entities.keys())
    canonical = build_canonical_ids(entities)
    logger.info(f"Parsed {len(entities)} entities; {len(canonical)} have their own id field")

    # Order: preferred first, then any remaining in spreadsheet order.
    ordered = [n for n in PREFERRED_ORDER if n in entities]
    ordered += [n for n in entities if n not in ordered]

    # Real ids of created objects, used to resolve `reference:` foreign keys.
    # Seeded from canonical (OBP preserves supplied `<entity>_id` values) and
    # upgraded to the id OBP actually returns after each successful create.
    real_ids = dict(canonical)

    print_separator("-")
    created = 0
    failed = 0
    for idx, ename in enumerate(ordered, 1):
        wrap = entities[ename]
        payload, references = build_payload(ename, wrap, canonical, entity_names, real_ids)

        try:
            resp = create_object(ename, payload, token=args.token)
            obj = resp.get(ename, resp)
            obj_id = obj.get(f"{ename}_id", "<auto>")
            if obj.get(f"{ename}_id") is not None:
                real_ids[ename] = obj[f"{ename}_id"]
            logger.info(f"  ✓ [{idx}/{len(ordered)}] Created {ename} (id: {obj_id})")
            created += 1
            if log_enabled:
                log_event(
                    EVENT_CREATED,
                    ename,
                    entity_id=obj_id,
                    status="success",
                    message=f"Created {ename}",
                    references=references,
                    token=args.token,
                )
        except requests.exceptions.HTTPError as e:
            detail = e.response.text if getattr(e, "response", None) is not None else str(e)
            logger.error(f"  ✗ [{idx}/{len(ordered)}] Failed {ename}: {detail}")
            failed += 1
            if log_enabled:
                log_event(
                    EVENT_FAILED, ename, status="error", message=detail,
                    references=references, token=args.token,
                )
        except Exception as e:
            logger.error(f"  ✗ [{idx}/{len(ordered)}] Failed {ename}: {e}")
            failed += 1
            if log_enabled:
                log_event(
                    EVENT_FAILED, ename, status="error", message=str(e),
                    references=references, token=args.token,
                )

    print_separator("-")
    logger.info(f"Dummy Data Summary: {created} created, {failed} failed")
    print_separator("=")


if __name__ == "__main__":
    main()
