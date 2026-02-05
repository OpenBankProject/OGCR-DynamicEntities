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


def create_dynamic_entity_from_parsed(name, parsed_fields, token=None, base_url=None, has_personal=False):
    """Build a minimal dynamic-entity payload from parsed_fields and call the create API.

    parsed_fields: dict mapping field_name or "field_name (optional)" -> example_value
    """
    # Normalize field names and determine required fields
    properties = {}
    required = []
    for raw_key, example in parsed_fields.items():
        key = raw_key
        optional = False
        if key.endswith(" (optional)"):
            key = key[:-11]
            optional = True
        # Support parsed_fields values that are either a scalar example or a dict
        # containing {'value': <col D value>, 'example': <col H value>}.
        example_value = None
        # If example is a dict, prefer its 'example' entry, fall back to 'value'
        if isinstance(example, dict):
            example_value = example.get("example") if example.get("example") is not None else example.get("value")
        else:
            example_value = example

        # Coerce string example values to appropriate Python types so OBP validation matches
        if isinstance(example_value, str):
            s = example_value.strip()
            # remove surrounding quotes if present
            if len(s) >= 2 and ((s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'"))):
                s = s[1:-1].strip()
            # integer
            if re.fullmatch(r"-?\d+", s):
                try:
                    example_value = int(s)
                except Exception:
                    pass
            # float
            elif re.fullmatch(r"-?\d+\.\d+", s):
                try:
                    example_value = float(s)
                except Exception:
                    pass
            # boolean
            elif s.lower() in ("true", "false"):
                example_value = s.lower() == "true"
            else:
                # try JSON for arrays/objects
                try:
                    parsed = json.loads(s)
                    example_value = parsed
                except Exception:
                    example_value = s

        # minimal typing: decide JSON schema type from coerced example_value
        prop_type = "string"
        try:
            if isinstance(example_value, int):
                prop_type = "integer"
            elif isinstance(example_value, float):
                prop_type = "number"
            elif isinstance(example_value, list):
                prop_type = "array"
            elif isinstance(example_value, dict):
                prop_type = "object"
            elif isinstance(example_value, bool):
                prop_type = "boolean"
            else:
                prop_type = "string"
        except Exception:
            prop_type = "string"

        # Ensure an example exists for each property (OBP requires example for some validations)
        prop_def = {"type": prop_type}
        if example_value is not None and example_value != "":
            prop_def["example"] = example_value
        else:
            # provide a reasonable default example based on type
            if prop_type == "integer":
                prop_def["example"] = 1
            elif prop_type in ("number",):
                prop_def["example"] = 1.0
            elif prop_type == "array":
                prop_def["example"] = []
            else:
                prop_def["example"] = "string"
        properties[key] = prop_def
        if not optional:
            required.append(key)

    entity_definition = {
        "hasPersonalEntity": bool(has_personal),
        name: {
            "description": f"Parsed entity {name}",
            "required": required,
            "properties": properties,
        }
    }
    # If entity with same name already exists, return existing id instead of creating
    try:
        existing = list_system_dynamic_entities(token=token, base_url=base_url)
        for e in existing.get("dynamic_entities", []):
            # find the wrapper key (skip control keys)
            keys = [k for k in e.keys() if k not in ("hasPersonalEntity", "dynamicEntityId", "userId")]
            if name in keys:
                return {"dynamicEntityId": e.get("dynamicEntityId"), "existing": True}
    except Exception:
        # listing failed - continue and attempt create
        pass

    # Call the API to create
    return create_system_dynamic_entity(entity_definition, token=token, base_url=base_url)
