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

# Non-reference primitive types OBP accepts for a dynamic-entity property.
SCALAR_ALLOWED_TYPES = {
    "number",
    "integer",
    "boolean",
    "string",
    "DATE_WITH_DAY",
    "json",
}

# OBP built-in reference targets (system entities). These are always valid
# regardless of which dynamic entities exist. Dynamic-entity reference targets
# (e.g. reference:parcel) are validated against the live instance instead of a
# hardcoded list, because OBP only accepts reference:X once X has been created.
BUILTIN_REFERENCE_TYPES = {
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
    _raise_for_status_with_body(resp)
    return resp.json()


def _raise_for_status_with_body(resp):
    """Like resp.raise_for_status(), but include the OBP response body in the
    error message so callers see e.g. OBP-09007 validation details instead of a
    bare '400 Client Error'."""
    if resp.status_code >= 400:
        raise requests.exceptions.HTTPError(
            f"{resp.status_code} for {resp.url}: {resp.text}", response=resp
        )


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
    _raise_for_status_with_body(resp)
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


def get_existing_entity_names(token=None, base_url=None):
    """Return the set of dynamic-entity names that currently exist on OBP.

    Used to validate reference:<name> types against the live instance, since OBP
    only accepts a reference whose target entity has already been created.
    """
    names = set()
    try:
        existing = list_system_dynamic_entities(token=token, base_url=base_url)
        for e in existing.get("dynamic_entities", []):
            for k in e.keys():
                if k not in ("hasPersonalEntity", "hasCommunityAccess", "dynamicEntityId", "userId"):
                    names.add(k)
    except Exception:
        pass
    return names


def build_entity_definition_from_parsed(name, parsed_fields, has_personal=False, has_community=False, entity_description=None,
                                        allowed_reference_types=None, downgrade_references=False):
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

        # 'value' holds the declared type (from the sheet), 'example' the example.
        # Do NOT fall back to the type string as the example: that leaks e.g.
        # "integer" or "DATE_WITH_DAY" into the example and trips OBP-09007.
        # When there is no example, leave example_value None so the per-type
        # default below is used instead.
        example_value = None
        declared_type = None
        is_indexed = False
        if isinstance(example, dict):
            example_value = example.get("example")
            declared_type = example.get("value")
            is_indexed = bool(example.get("indexed"))
        else:
            example_value = example

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

        # Decide the property type. Scalar types pass through (case-insensitively,
        # so a sheet value of "Integer" maps to "integer"). A reference:X type is
        # kept only when it is a built-in reference OR X exists on the live OBP
        # instance (allowed_reference_types); otherwise it is downgraded to a
        # plain string so creation never fails on an unknown/forward reference.
        # downgrade_references forces every reference to string (used by pass 1
        # of the two-pass create, before all target entities exist).
        prop_type = "string"
        if isinstance(declared_type, str):
            dt = declared_type.strip()
            scalar_by_lower = {t.lower(): t for t in SCALAR_ALLOWED_TYPES}
            if dt in SCALAR_ALLOWED_TYPES:
                prop_type = dt
            elif dt.lower() in scalar_by_lower:
                prop_type = scalar_by_lower[dt.lower()]
            elif dt.startswith("reference:"):
                if downgrade_references:
                    prop_type = "string"
                elif dt in BUILTIN_REFERENCE_TYPES:
                    prop_type = dt
                elif allowed_reference_types is not None and dt in allowed_reference_types:
                    prop_type = dt
                else:
                    prop_type = "string"

        # An 'integer' field whose example parsed to a float: a value like 85.0
        # is integer-valued, so coerce the example to int; a value like 0.52 is
        # genuinely fractional, so the field is really a decimal -> promote to
        # 'number' (the sheet's declared type was wrong).
        if prop_type == "integer" and isinstance(example_value, float):
            if example_value.is_integer():
                example_value = int(example_value)
            else:
                logger.warning(
                    "%s.%s: declared integer but example %r is fractional; using number",
                    name, key, example_value,
                )
                prop_type = "number"

        # A numeric field with a non-numeric example (e.g. an alphanumeric token
        # id mistyped as integer): drop the bad example so the per-type default
        # is used, rather than failing the whole entity. Booleans count as int.
        if prop_type in ("integer", "number") and not isinstance(example_value, (int, float)):
            if example_value not in (None, ""):
                logger.warning(
                    "%s.%s: declared %s but example %r is not numeric; using default",
                    name, key, prop_type, example_value,
                )
            example_value = None

        # String and reference examples must be JSON strings. Stringify any
        # non-string example (e.g. a JSON object like {"id":...,"version":...}
        # that landed on a reference field) so OBP accepts it.
        if (prop_type == "string" or prop_type.startswith("reference:")) and example_value is not None and not isinstance(example_value, str):
            try:
                example_value = json.dumps(example_value)
            except Exception:
                example_value = str(example_value)

        prop_def = {"type": prop_type}
        # "Field Is Indexed" (column K in min_field_matrix.xlsx) is required for a
        # field to be usable in OBP's ?obp_exists[Entity]/?obp_not_exists[Entity] and
        # nested filter[...] queries. The sheet is the source of truth for this, not
        # a type-based guess — a reference field without it can't be a join edge, and
        # a scalar field without it can't be filtered inside a join predicate.
        if is_indexed:
            prop_def["indexed"] = True
        if example_value is not None and example_value != "":
            prop_def["example"] = example_value
        else:
            if prop_type == "integer":
                prop_def["example"] = 1
            elif prop_type == "number":
                prop_def["example"] = 1.0
            elif prop_type == "boolean":
                prop_def["example"] = True
            elif prop_type == "DATE_WITH_DAY":
                prop_def["example"] = "2020-01-01"
            elif prop_type == "json":
                prop_def["example"] = {}
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


def create_dynamic_entity_from_parsed(name, parsed_fields, token=None, base_url=None, has_personal=False, has_community=False, entity_description=None,
                                      allowed_reference_types=None, downgrade_references=False):
    """Create a dynamic entity using parsed fields by building the payload and POSTing it."""
    entity_definition = build_entity_definition_from_parsed(
        name, parsed_fields, has_personal=has_personal, has_community=has_community, entity_description=entity_description,
        allowed_reference_types=allowed_reference_types, downgrade_references=downgrade_references)

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
