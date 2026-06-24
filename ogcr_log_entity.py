"""Audit-log dynamic entity for OGCR data creation.

This module defines a single system dynamic entity named after this application
(`<prefix>ogcr_dynamicentities_log`, where `<prefix>` is the optional
`OBP_ENTITY_PREFIX`) and the helpers needed to (a) make sure it exists on OBP and
(b) write one log record to it per event while dummy data is being created. It is
consumed by `create_dummy_data.py`, which records:
  - `entity_created`  one record per successfully created object;
  - `entity_failed`   one record per object that failed to POST.

Each record carries a json `references` field listing every `reference:<x>` field
on the entity and how it resolved — `resolved` when a real created id was used, or
`fallback` when the spreadsheet example value was used instead (the reference
target was a static OBP entity or one we don't create here; see build_payload).

Logging is best-effort: every helper here swallows its own errors and never
raises, so recording the audit trail can never break the creation flow it
observes.
"""
import datetime
import logging
import os

import requests
from dotenv import load_dotenv

from obp_client import obp_host
from obp_dynamic_api import (
    create_system_dynamic_entity,
    get_dynamic_entity_id_by_name,
)

logger = logging.getLogger(__name__)

# Apply the same entity-name prefix convention as dynamic_entities.py: the
# optional OBP_ENTITY_PREFIX, lowercased and given a trailing underscore.
load_dotenv()
_PREFIX = os.getenv("OBP_ENTITY_PREFIX", "").lower()
if _PREFIX and not _PREFIX.endswith("_"):
    _PREFIX = _PREFIX + "_"

# Name the log entity after this application (lowercase, underscores only).
APP_NAME = "ogcr_dynamicentities"
LOG_ENTITY_NAME = f"{_PREFIX}{APP_NAME}_log"

# Event types written to the log entity's `event_type` field.
EVENT_CREATED = "entity_created"
EVENT_FAILED = "entity_failed"

# Example value for the `references` json field, documenting its shape.
_REFERENCES_EXAMPLE = [
    {
        "field": "operator_id",
        "target": "operator",
        "resolution": "resolved",
        "value": "a8770fca-3d1d-47af-b6d0-7a6c3f124388",
    },
    {
        "field": "bank_account_id",
        "target": "BankAccount",
        "resolution": "fallback",
        "value": "sample-account-id",
    },
]


def _string_prop(example, description):
    return {"type": "string", "example": example, "description": description}


def build_log_entity_definition():
    """Return the system-dynamic-entity definition for the creation log."""
    return {
        "hasPersonalEntity": False,
        "hasCommunityAccess": False,
        LOG_ENTITY_NAME: {
            "description": (
                "Audit log of OGCR dynamic-entity data creation: one record per "
                "created object or failed create, capturing how each of its "
                "reference fields resolved."
            ),
            "required": ["event_type", "entity_name"],
            "properties": {
                "event_type": _string_prop(
                    EVENT_CREATED,
                    f"One of {EVENT_CREATED}, {EVENT_FAILED}.",
                ),
                "entity_name": _string_prop(
                    "operator", "Name of the dynamic entity the event concerns."
                ),
                "entity_id": _string_prop(
                    "a8770fca-3d1d-47af-b6d0-7a6c3f124388",
                    "Id of the created object, when known.",
                ),
                "status": _string_prop("success", "success or error."),
                "message": _string_prop(
                    "Created operator", "Human-readable detail or error text."
                ),
                "references": {
                    "type": "json",
                    "example": _REFERENCES_EXAMPLE,
                    "description": (
                        "List of every reference:<x> field on this entity and how "
                        "it resolved. Each item has `field`, `target`, `resolution` "
                        "(resolved = a real created id was used; fallback = the "
                        "spreadsheet example value was used) and the `value` posted."
                    ),
                },
                "timestamp": _string_prop(
                    "2026-06-24T12:00:00Z",
                    "UTC ISO-8601 time the event was recorded.",
                ),
            },
        },
    }


def ensure_log_entity(token=None, base_url=None):
    """Make sure the log entity exists, creating it if needed.

    Returns the dynamicEntityId (or the entity name as a truthy sentinel) when
    the entity is available for posting, else None. Never raises.
    """
    try:
        existing = get_dynamic_entity_id_by_name(
            LOG_ENTITY_NAME, token=token, base_url=base_url
        )
        if existing:
            logger.info(f"Log entity '{LOG_ENTITY_NAME}' already exists (id: {existing})")
            return existing
        resp = create_system_dynamic_entity(
            build_log_entity_definition(), token=token, base_url=base_url
        )
        ent_id = resp.get("dynamicEntityId") if isinstance(resp, dict) else None
        logger.info(f"Created log entity '{LOG_ENTITY_NAME}' (id: {ent_id})")
        return ent_id or LOG_ENTITY_NAME
    except Exception as e:
        detail = getattr(getattr(e, "response", None), "text", None) or str(e)
        logger.error(f"Could not ensure log entity '{LOG_ENTITY_NAME}': {detail}")
        return None


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log_event(
    event_type,
    entity_name,
    entity_id="",
    references=None,
    status="",
    message="",
    token=None,
    base_url=None,
):
    """POST a single record to the log dynamic entity.

    `references` is a list of `{field, target, resolution, value}` dicts (one per
    reference field on the entity); it is stored in the json `references` field.

    Best-effort: any failure is warned about and swallowed (returns None) so
    logging never breaks the data-creation flow.
    """
    base_url = base_url or obp_host
    record = {
        "event_type": event_type,
        "entity_name": entity_name,
        "entity_id": str(entity_id or ""),
        "status": status or "",
        "message": message or "",
        "references": references if references is not None else [],
        "timestamp": _now_iso(),
    }
    url = f"{base_url}/obp/dynamic-entity/{LOG_ENTITY_NAME}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"DirectLogin token={token}"
    try:
        resp = requests.post(url, headers=headers, json=record)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        detail = getattr(getattr(e, "response", None), "text", None) or str(e)
        logger.warning(
            f"Failed to write {event_type} log record for {entity_name}: {detail}"
        )
        return None
