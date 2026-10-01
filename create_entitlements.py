"""Grant the logged in user the Roles for the OGCR dynamic entities.

Grants the entity DEFINITION Roles, the Roles for managing the Role Groups
and adding users to them (see role_groups.py), plus the RECORD Roles for every
`Entity: <name>` in the parsed entities file (produced by
`parse_minimum_fields.py --save`), all at the bank id of the entities' space
(OBP_ENTITY_SPACE_ID, or SYS for system level; see obp_space.py). An entity's record Roles
only exist on OBP once the entity does, so entities not on OBP yet are skipped.

Roles the user already holds (at the same bank id) are not requested again; only
the missing ones are granted. Exits 1 if any grant failed.

Usage:
    python3 create_entitlements.py [path/to/entities_output.txt]
"""

import sys

from dynamic_entities import add_entitlement_to_user
from delete_dynamic_entities import DEFAULT_INPUT, parse_entity_names
from get_and_delete_dynamic_entities import get_all_system_dynamic_entities
from obp_client import token, obp_host, session
from obp_space import ROLE_BANK_ID, describe
from role_groups import GROUP_ADMIN_ROLES

entities_file = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_INPUT
entity_names = parse_entity_names(entities_file)
print(f"Read {len(entity_names)} entities from {entities_file}")

# Grant the Roles to whoever is logged in.
response = session.get(f"{obp_host}/obp/v6.0.0/users/current",
	headers={"Authorization": f"DirectLogin token={token}"})
response.raise_for_status()
user_id = response.json()["user_id"]
held = {(e.get("role_name"), e.get("bank_id", ""))
	for e in response.json().get("entitlements", {}).get("list", [])}
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
# Every (role_name, bank_id) wanted, in order: definition Roles, group Roles, then record Roles.
wanted = [(m, ROLE_BANK_ID) for m in meta_role_names]
# The Roles create_role_groups.py and add_users_to_groups.py need (steps 4 and 5 of
# recreate_dynamic_entities.sh). Some are system level, so each carries its own bank id.
wanted += GROUP_ADMIN_ROLES

existing = get_all_system_dynamic_entities(token=token)  # raises if OBP cannot list them
existing_names = {e.get("entity_name") for e in existing.get("dynamic_entities", [])}
skipped = [name for name in entity_names if name not in existing_names]
for name in skipped:
	print(f"skipping {name}: entity not at {describe()} on OBP yet")
wanted += [(r + name, ROLE_BANK_ID) for name in entity_names if name not in skipped for r in role_names]

missing = [(r, b) for r, b in wanted if (r, b) not in held]
print(f"{len(wanted) - len(missing)} of {len(wanted)} Roles already held; granting {len(missing)}")
failed = []
for role_name, bank_id in missing:
	where = f" @ {bank_id}" if bank_id else ""
	try:
		result = add_entitlement_to_user(
			token=token,
			user_id=user_id,
			role_name=role_name,
			bank_id=bank_id)
	except Exception as e:  # e.g. connection error, or a response that is not JSON
		print(f"  {e}")
		result = None
	if isinstance(result, dict) and result.get("entitlement_id"):
		print(f"  ✓ granted {role_name}{where}")
	else:
		failed.append(f"{role_name}{where}")
		print(f"  ✗ could not grant {role_name}{where}")

if skipped:
	print(f"Skipped {len(skipped)} of {len(entity_names)} entities not on OBP yet; "
		"create them, then run this again")
if failed:
	print(f"✗ {len(failed)} Role(s) could not be granted: {', '.join(failed)}")
	sys.exit(1)
