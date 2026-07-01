"""Small helper to create system dynamic entities on OBP Management API.

Functions:
- create_system_dynamic_entity(entity_definition, token=None, base_url=None)
- create_dynamic_entity_from_parsed(name, parsed_fields, token=None, base_url=None, has_personal=False)

This module intentionally mirrors the minimal behavior needed by `parse_minimum_fields.py` and
is self-contained so `parse_minimum_fields.py` can remain focused on parsing logic.
"""
import requests
import logging
import json
import re
from obp_client import token as DEFAULT_TOKEN, obp_host as DEFAULT_HOST

logger = logging.getLogger(__name__)


def list_system_dynamic_entities(token=None, base_url=None):
    """Return the management endpoint JSON for existing system dynamic entities."""
    token = token or DEFAULT_TOKEN
    base_url = base_url or DEFAULT_HOST
    url = f"{base_url}/obp/v5.1.0/management/system-dynamic-entities"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"DirectLogin token={token}"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()


def create_system_dynamic_entity(entity_definition, token=None, base_url=None):
    """POST the given entity_definition to the OBP management endpoint.

    Returns the response JSON on success; raises requests.exceptions.RequestException on failure.
    """
    token = token or DEFAULT_TOKEN
    base_url = base_url or DEFAULT_HOST
    url = f"{base_url}/obp/v5.1.0/management/system-dynamic-entities"

    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"DirectLogin token={token}"

    logger.debug("Creating system dynamic entity: %s", json.dumps(entity_definition, indent=2))

    resp = requests.post(url, headers=headers, json=entity_definition)
    resp.raise_for_status()
    return resp.json()


def update_system_dynamic_entity(dynamic_entity_id, entity_definition, token=None, base_url=None):
    """PUT the given entity_definition to update an existing system dynamic entity.

    Returns the response JSON on success; raises requests.exceptions.RequestException on failure.
    """
    token = token or DEFAULT_TOKEN
    base_url = base_url or DEFAULT_HOST
    url = f"{base_url}/obp/v5.1.0/management/system-dynamic-entities/{dynamic_entity_id}"

    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"DirectLogin token={token}"

    logger.debug("Updating system dynamic entity %s: %s", dynamic_entity_id, json.dumps(entity_definition, indent=2))

    resp = requests.put(url, headers=headers, json=entity_definition)
    resp.raise_for_status()
    return resp.json()


def get_dynamic_entity_id_by_name(name, token=None, base_url=None):
    """Return dynamicEntityId for a system dynamic entity matching `name` or None if not found."""
    token = token or DEFAULT_TOKEN
    base_url = base_url or DEFAULT_HOST
    try:
        existing = list_system_dynamic_entities(token=token, base_url=base_url)
        for e in existing.get("dynamic_entities", []):
            keys = [k for k in e.keys() if k not in ("hasPersonalEntity", "dynamicEntityId", "userId")]
            if name in keys:
                return e.get("dynamicEntityId")
    except Exception:
        return None
    return None


def build_entity_definition_from_parsed(name, parsed_fields, has_personal=False, has_community=False, entity_description=None):
    """Build and return a dynamic-entity payload dict from parsed_fields without making API calls.

    parsed_fields: dict mapping field_name or "field_name (optional)" -> {'value':<type>, 'example':<example>, 'description':<desc>} or scalar
    """
    properties = {}
    required = []
    for raw_key, example in parsed_fields.items():
        key = raw_key
        optional = False
        if key.endswith(" (optional)"):
            key = key[:-11]
            optional = True

        example_value = None
        if isinstance(example, dict):
            example_value = example.get("example") if example.get("example") is not None else example.get("value")
        else:
            example_value = example

        declared_type = None
        if isinstance(example, dict):
            declared_type = example.get("value")

        if isinstance(example_value, str):
            s = example_value.strip()
            if len(s) >= 2 and ((s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'"))):
                s = s[1:-1].strip()
            if re.fullmatch(r"-?\d+", s):
                try:
                    example_value = int(s)
                except Exception:
                    pass
            elif re.fullmatch(r"-?\d+\.\d+", s):
                try:
                    example_value = float(s)
                except Exception:
                    pass
            elif s.lower() in ("true", "false"):
                example_value = s.lower() == "true"
            else:
                try:
                    parsed = json.loads(s)
                    example_value = parsed
                except Exception:
                    example_value = s

        ALLOWED_TYPES = {
            "number",
            "integer",
            "boolean",
            "string",
            "DATE_WITH_DAY",
            "json",
            "reference:parcel",
            "reference:activity_verification",
            "reference:operator",
            "reference:land_manager",
            "reference:parcel_owner_verification",
            "reference:activity",
            "reference:activity_plan",
            "reference:monitoring_plan",
            "reference:certification_scheme",
            "reference:certification_body_auditors",
            "reference:activity_parcel_verification",
            "reference:audit_report",
            "reference:certificate_of_compliance",
            "reference:parcel_monitoring_period_verification",
            "reference:activity_monitoring_period_verification",
            "reference:Bank",
            "reference:Consumer",
            "reference:Customer",
            "reference:MethodRouting",
            "reference:DynamicEntity",
            "reference:TransactionRequest",
            "reference:ProductAttribute",
            "reference:AccountAttribute",
            "reference:TransactionAttribute",
            "reference:CustomerAttribute",
            "reference:AccountApplication",
            "reference:CardAttribute",
            "reference:Counterparty",
            "reference:Branch:bankId&branchId",
            "reference:Atm:bankId&atmId",
            "reference:BankAccount:bankId&accountId",
            "reference:Product:bankId&productCode",
            "reference:PhysicalCard:bankId&cardId",
            "reference:Transaction:bankId&accountId&transactionId",
            "reference:Counterparty:bankId&accountId&counterpartyId",
        }

        prop_type = "string"
        if isinstance(declared_type, str) and declared_type in ALLOWED_TYPES:
            prop_type = declared_type
        else:
            prop_type = "string"

        # For numeric types, drop any non-numeric example (e.g. when the field
        # has no example in the sheet, the declared type string like "integer"
        # leaks in as the value). This forces the per-type default below and
        # avoids OBP-09007 "example's type should be integer" validation errors.
        if prop_type in ("integer", "number") and not isinstance(example_value, (int, float)):
            example_value = None

        if prop_type == "string" and example_value is not None:
            try:
                example_value = str(example_value)
            except Exception:
                example_value = ""

        prop_def = {"type": prop_type}
        if example_value is not None and example_value != "":
            prop_def["example"] = example_value
        else:
            if prop_type == "integer":
                prop_def["example"] = 1
            elif prop_type in ("number",):
                prop_def["example"] = 1.0
            elif prop_type == "array":
                prop_def["example"] = []
            else:
                prop_def["example"] = "string"

        if isinstance(example, dict) and example.get("description"):
            try:
                prop_def["description"] = str(example.get("description"))
            except Exception:
                prop_def["description"] = ""

        properties[key] = prop_def
        if not optional:
            required.append(key)

    entity_def_description = entity_description if entity_description is not None else f"Parsed entity {name}"
    entity_definition = {
        "hasPersonalEntity": bool(has_personal),
        "hasCommunityAccess": bool(has_community),
        name: {
            "description": entity_def_description,
            "required": required,
            "properties": properties,
        }
    }
    return entity_definition


def create_dynamic_entity_from_parsed(name, parsed_fields, token=None, base_url=None, has_personal=False, has_community=False, entity_description=None):
    """Create a dynamic entity using parsed fields by building the payload and POSTing it."""
    entity_definition = build_entity_definition_from_parsed(name, parsed_fields, has_personal=has_personal, has_community=has_community, entity_description=entity_description)

    # If entity with same name already exists, return existing id instead of creating
    try:
        existing = list_system_dynamic_entities(token=token, base_url=base_url)
        for e in existing.get("dynamic_entities", []):
            keys = [k for k in e.keys() if k not in ("hasPersonalEntity", "dynamicEntityId", "userId")]
            if name in keys:
                return {"dynamicEntityId": e.get("dynamicEntityId"), "existing": True}
    except Exception:
        # listing failed - continue and attempt create
        pass

    return create_system_dynamic_entity(entity_definition, token=token, base_url=base_url)
