"""Build example JSON payloads for dynamic-entity POST requests.

Functions
- build_example_payloads(entity_definition, count=5): returns a list of dict payloads

This is a conservative builder: for reference types it inserts example UUIDs, for strings it inserts the example if present or a placeholder, for integers it inserts the example or 0.
"""
import uuid
import copy


def _example_for_prop(prop_def):
    ptype = prop_def.get("type", "string")
    example = prop_def.get("example")
    if example is not None:
        # return a deep copy to avoid accidental mutation
        return copy.deepcopy(example)
    # handle reference types like 'reference:Parcel' or 'reference:ogcr3_project'
    if isinstance(ptype, str) and ptype.startswith("reference:"):
        # return a stable example UUID
        return str(uuid.uuid4())
    if ptype in ("integer", "number"):
        return 0
    if ptype == "string":
        return "example_string"
    if ptype == "array":
        # if items specified, try to create one example item
        items = prop_def.get("items") or {}
        item_example = _example_for_prop(items) if isinstance(items, dict) else None
        return [item_example] if item_example is not None else []
    # default
    return None


def build_example_payloads(entity_definition, count=5):
    """Given an entity definition dict (the wrapper that contains 'hasPersonalEntity' and a single entity),
    return `count` example payload dicts for creating instances of that entity.

    entity_definition: dict
      e.g. {"hasPersonalEntity": False, "project": {"properties": {...}, "required": [...]}}

    Returns: list of dict
    """
    # find the entity wrapper key (skip control keys)
    keys = [k for k in entity_definition.keys() if k not in ("hasPersonalEntity",)]
    if not keys:
        raise ValueError("No entity found in definition")
    entity_key = keys[0]
    entity_body = entity_definition[entity_key]
    props = entity_body.get("properties", {})
    required = entity_body.get("required", [])

    examples = []
    for i in range(count):
        payload = {}
        for prop_name, prop_def in props.items():
            val = _example_for_prop(prop_def)
            # make small variations across examples
            if isinstance(val, str) and val == "example_string":
                payload[prop_name] = f"{val}_{i+1}"
            elif isinstance(val, str):
                # if example looks like a date, don't suffix
                payload[prop_name] = val
            else:
                payload[prop_name] = val
        # ensure all required fields exist (if builder produced None for some), fill with placeholders
        for r in required:
            if r not in payload or payload[r] is None:
                if r.endswith("_id"):
                    payload[r] = str(uuid.uuid4())
                elif r.endswith("_date") or r.endswith("_start_date") or r.endswith("_end_date"):
                    payload[r] = "2024-01-01"
                elif r.endswith("_years") or r.endswith("_commitment"):
                    payload[r] = 1
                else:
                    payload[r] = "REQUIRED"
        examples.append(payload)
    return examples
