"""Grant the logged in user the Roles for the OGCR dynamic entities.

Grants the entity DEFINITION Roles, plus the RECORD Roles for every
`Entity: <name>` in the parsed entities file (produced by
`parse_minimum_fields.py --save`), all at bank id SYS.

Usage:
    python3 create_entitlements.py [path/to/entities_output.txt]
"""

import sys

import requests

from dynamic_entities import add_entitlement_to_user
from delete_ogcr_entities import DEFAULT_INPUT, parse_entity_names
from obp_client import token, obp_host

entities_file = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_INPUT
entity_names = parse_entity_names(entities_file)
print(f"Read {len(entity_names)} entities from {entities_file}")

# Grant the Roles to whoever is logged in.
response = requests.get(f"{obp_host}/obp/v6.0.0/users/current",
	headers={"Authorization": f"DirectLogin token={token}"})
response.raise_for_status()
user_id = response.json()["user_id"]
print(f"Granting Roles to user_id {user_id}")
# The Roles that gate an entity's DEFINITION. The v6.0.0 system-dynamic-entities management endpoints
# require these (they replaced the old CanXSystemLevelDynamicEntity names) and, like the Record Roles
# below, they are granted at bank id SYS.
meta_role_names = [
	"CanCreateDynamicEntityDefinition",
	"CanDeleteDynamicEntityDefinition",
	"CanGetDynamicEntityDefinitions",
	"CanUpdateDynamicEntityDefinition"
	]
# The Roles that gate an entity's RECORDS. They were renamed on 2026-09-24: the "_System" variant is
# gone, because the Role no longer says which space it applies to -- the bank id of the grant does.
# For a system level entity that bank id is the literal SYS, not the empty string.
role_names = [
	"CanCreateDynamicEntityRecord_",
	"CanDeleteDynamicEntityRecord_",
	"CanGetDynamicEntityRecord_",
	"CanUpdateDynamicEntityRecord_"
	]
system_space_bank_id = "SYS"
for m in meta_role_names:
	add_entitlement_to_user(
		token=token,
		user_id=user_id,
		role_name=m,
		bank_id=system_space_bank_id)

for name in entity_names:
	for r in role_names:
		print(r + name)
		add_entitlement_to_user(
			token=token,
			user_id=user_id,
			role_name=r + name,
			bank_id=system_space_bank_id)