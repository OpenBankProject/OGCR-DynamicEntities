"""Grant the logged in user the Roles for the OGCR dynamic entities.

Grants the entity DEFINITION Roles, plus the RECORD Roles for every
`Entity: <name>` in the parsed entities file (produced by
`parse_minimum_fields.py --save`), all at the bank id of the entities' space
(OBP_ENTITY_SPACE_ID, or SYS for system level; see obp_space.py). An entity's record Roles
only exist on OBP once the entity does, so entities not on OBP yet are skipped.

Usage:
    python3 create_entitlements.py [path/to/entities_output.txt]
"""

import sys

import requests

from dynamic_entities import add_entitlement_to_user
from delete_ogcr_entities import DEFAULT_INPUT, parse_entity_names
from get_and_delete_dynamic_entities import get_all_system_dynamic_entities
from obp_client import token, obp_host
from obp_space import ROLE_BANK_ID, describe

entities_file = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_INPUT
entity_names = parse_entity_names(entities_file)
print(f"Read {len(entity_names)} entities from {entities_file}")

# Grant the Roles to whoever is logged in.
response = requests.get(f"{obp_host}/obp/v6.0.0/users/current",
	headers={"Authorization": f"DirectLogin token={token}"})
response.raise_for_status()
user_id = response.json()["user_id"]
print(f"Granting Roles for the entities at {describe()} to user_id {user_id}, at bank id {ROLE_BANK_ID}")
# The Roles that gate an entity's DEFINITION. The dynamic entity management endpoints require these
# (they replaced the old CanXSystemLevelDynamicEntity names) and, like the Record Roles below, they
# are granted at the bank id of the space.
meta_role_names = [
	"CanCreateDynamicEntityDefinition",
	"CanDeleteDynamicEntityDefinition",
	"CanGetDynamicEntityDefinitions",
	"CanUpdateDynamicEntityDefinition"
	]
# The Roles that gate an entity's RECORDS. They were renamed on 2026-09-24: the "_System" variant is
# gone, because the Role no longer says which space it applies to -- the bank id of the grant does.
# For system level entities that bank id is the literal SYS, not the empty string.
role_names = [
	"CanCreateDynamicEntityRecord_",
	"CanDeleteDynamicEntityRecord_",
	"CanGetDynamicEntityRecord_",
	"CanUpdateDynamicEntityRecord_"
	]
for m in meta_role_names:
	add_entitlement_to_user(
		token=token,
		user_id=user_id,
		role_name=m,
		bank_id=ROLE_BANK_ID)

existing = get_all_system_dynamic_entities(token=token)  # raises if OBP cannot list them
existing_names = {e.get("entity_name") for e in existing.get("dynamic_entities", [])}
skipped = [name for name in entity_names if name not in existing_names]
for name in skipped:
	print(f"skipping {name}: entity not at {describe()} on OBP yet")

for name in entity_names:
	if name in skipped:
		continue
	for r in role_names:
		print(r + name)
		add_entitlement_to_user(
			token=token,
			user_id=user_id,
			role_name=r + name,
			bank_id=ROLE_BANK_ID)

if skipped:
	print(f"Skipped {len(skipped)} of {len(entity_names)} entities not on OBP yet; "
		"create them, then run this again")
