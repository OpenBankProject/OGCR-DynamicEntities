"""Where the OGCR dynamic entities live on OBP: at system level, or under one bank (aka Space).

`OBP_ENTITY_SPACE_ID` in `.env` is the bank id that owns this deployment's
entities. Unset, it defaults to `ogcr`, the same default as OGCR-App and
OGCR-chain-cache. Set it to the empty string for system level. Every script builds its
dynamic-entity URLs and Role grants from here, so they can never disagree.

    | Level | Definitions (management)                        | Records                                            | Roles granted at |
    |-------|-------------------------------------------------|----------------------------------------------------|------------------|
    | System| /obp/<v>/management/system-dynamic-entities     | /obp/dynamic-entity/[public/]ENTITY                | SYS              |
    | Bank  | /obp/<v>/management/banks/ID/dynamic-entities   | /obp/dynamic-entity/banks/ID/[public/]ENTITY       | ID               |

The space is all-or-nothing: every entity lives at the same level (see
SPACE_LEVEL_VERSIONING_PLAN.md). It is deliberately NOT called OBP_BANK_ID, so
it cannot be confused with a user's selected CURRENT_BANK_ID.

No side effects on import (no login), so offline scripts can use it too.
"""
import os

from dotenv import load_dotenv

load_dotenv()

DEFAULT_SPACE_ID = "ogcr"

# Unset -> the default bank; set but empty -> system level.
SPACE_ID = os.getenv("OBP_ENTITY_SPACE_ID", DEFAULT_SPACE_ID).strip()

# The bank id at which entity Roles are granted: the space's bank id, or the literal
# SYS for system level entities (not the empty string).
ROLE_BANK_ID = SPACE_ID or "SYS"


def describe():
	"""Human readable name of where the entities live, for log messages."""
	return f"bank '{SPACE_ID}'" if SPACE_ID else "system level"


def management_path(version):
	"""Path of the dynamic entity definitions collection, e.g. for version 'v6.0.0'."""
	if SPACE_ID:
		return f"/obp/{version}/management/banks/{SPACE_ID}/dynamic-entities"
	return f"/obp/{version}/management/system-dynamic-entities"


def record_path(entity_name, public=False):
	"""Path of an entity's records. The space comes first; `public` always sits
	immediately before the entity name (the other order returns 404)."""
	path = "/obp/dynamic-entity"
	if SPACE_ID:
		path += f"/banks/{SPACE_ID}"
	if public:
		path += "/public"
	return f"{path}/{entity_name}"
