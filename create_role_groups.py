"""Create or update one OBP Group per Role Group in the minimum fields spreadsheet.

The Role Group matrix (columns R onwards of min_field_matrix.xlsx; see
role_groups.py) says which record endpoints each group may call on each entity.
Each column becomes an OBP Group, named after its header, at the bank id of the
entities' space (OBP_ENTITY_SPACE_ID, or SYS for system level; see obp_space.py),
holding the matching CanCreate/Get/Update/DeleteDynamicEntityRecord_<entity>
Roles. Adding a user to the group then grants them those Roles at that bank id.

A group that already exists there (matched by name) has its Roles replaced by
the sheet's, so it always matches the sheet. Groups there that are not in the
sheet are left alone.

NOTE: OBP copies a group's Roles to a user when the user is ADDED to the group.
Changing the group afterwards does not change existing members' Roles; remove
and re-add them to pick up the change.

Needs CanCreateGroupAtOneBank, CanUpdateGroupAtOneBank and CanGetGroupsAtOneBank
at that bank id (or the ...AtAllBanks versions).

Usage:
    python3 create_role_groups.py [path/to/min_field_matrix.xlsx] [--dry-run]

Exits 0 on success, 1 if the sheet has errors in the matrix or anything failed.
"""

import argparse
import sys

import requests

from get_and_delete_dynamic_entities import get_all_system_dynamic_entities
from obp_client import token, obp_host
from obp_space import ROLE_BANK_ID, describe
from role_groups import group_roles, parse_role_groups

DEFAULT_SPREADSHEET = "min_field_matrix.xlsx"
GROUPS_URL = f"{obp_host}/obp/v6.0.0/management/groups"


def headers():
	return {"Authorization": f"DirectLogin token={token}", "Content-Type": "application/json"}


def get_groups_at_space():
	"""{group_name: group} of the groups at ROLE_BANK_ID."""
	response = requests.get(GROUPS_URL, params={"bank_id": ROLE_BANK_ID}, headers=headers(), timeout=30)
	if not response.ok:
		raise RuntimeError(f"{response.status_code} {response.text}")
	groups = {}
	for g in response.json().get("groups", []):
		if g.get("group_name") in groups:
			print(f"! More than one group named {g['group_name']!r} at bank id {ROLE_BANK_ID}; "
				f"using {groups[g['group_name']]['group_id']}")
			continue
		groups[g.get("group_name")] = g
	return groups


def description_for(group, spreadsheet):
	return (f"OGCR Role Group from column {group['column']} of {spreadsheet}: "
		+ ", ".join(f"{entity} {access}" for entity, access in group["access"].items()))


def main():
	parser = argparse.ArgumentParser(description="Create or update the OBP Groups defined in the spreadsheet's Role Group matrix.")
	parser.add_argument("file", nargs="?", default=DEFAULT_SPREADSHEET,
		help=f"Path to the xlsx file (default: {DEFAULT_SPREADSHEET})")
	parser.add_argument("--dry-run", action="store_true", help="Only say what would be created or updated")
	args = parser.parse_args()
	tag = "[DRY RUN] " if args.dry_run else ""

	groups, errors, warnings = parse_role_groups(args.file)
	for w in warnings:
		print(f"! {w}")
	if errors:
		for e in errors:
			print(f"✗ {e}")
		print(f"✗ {len(errors)} error(s) in the Role Group matrix; fix the sheet first "
			"(./check_min_field_matrix.sh). Nothing was changed.")
		return 1
	if not groups:
		print(f"No Role Group columns found from column R of {args.file}. Nothing to do.")
		return 0
	if not token:
		print("✗ DirectLogin failed")
		return 1

	print(f"{tag}{len(groups)} Role Group(s) in {args.file}, for the entities at {describe()}, "
		f"as OBP Groups at bank id {ROLE_BANK_ID}")

	# The Roles can be put in a group before their entity exists, but they mean nothing until it does.
	existing_entities = {e.get("entity_name")
		for e in get_all_system_dynamic_entities(token=token).get("dynamic_entities", [])}
	missing = sorted({entity for g in groups for entity in g["access"]} - existing_entities)
	if missing:
		print(f"! Not at {describe()} on OBP yet (their Roles are still put in the groups): {', '.join(missing)}")

	try:
		on_obp = get_groups_at_space()
	except Exception as e:
		print(f"✗ Could not list the groups at bank id {ROLE_BANK_ID}: {e}")
		return 1

	failed = 0
	for group in groups:
		name = group["name"]
		roles = group_roles(group)
		body = {
			"group_name": name,
			"group_description": description_for(group, args.file),
			"list_of_roles": roles,
			"is_enabled": True,
		}
		existing = on_obp.get(name)
		if existing is None:
			if not roles:
				print(f"{tag}Skipping {name!r} (column {group['column']}): no access ticked")
				continue
			print(f"{tag}CREATE group {name!r} with {len(roles)} Role(s)")
			for r in roles:
				print(f"    + {r}")
			if args.dry_run:
				continue
			response = requests.post(GROUPS_URL, json={**body, "bank_id": ROLE_BANK_ID},
				headers=headers(), timeout=30)
		else:
			before = set(existing.get("list_of_roles") or [])
			added = [r for r in roles if r not in before]
			removed = sorted(before - set(roles))
			if not added and not removed and existing.get("is_enabled") \
					and existing.get("group_description") == body["group_description"]:
				print(f"{tag}Unchanged group {name!r} ({existing['group_id']}): {len(roles)} Role(s)")
				continue
			print(f"{tag}UPDATE group {name!r} ({existing['group_id']}): {len(roles)} Role(s)")
			for r in added:
				print(f"    + {r}")
			for r in removed:
				print(f"    - {r}")
			if not existing.get("is_enabled"):
				print("    enable it")
			if args.dry_run:
				continue
			response = requests.put(f"{GROUPS_URL}/{existing['group_id']}", json=body,
				headers=headers(), timeout=30)

		if response.ok:
			print(f"  ✓ {response.json().get('group_id')}")
		else:
			failed += 1
			print(f"  ✗ {response.status_code} {response.text}")

	others = sorted(n for n in on_obp if n not in {g["name"] for g in groups})
	if others:
		print(f"Left untouched (not in the sheet): {', '.join(others)}")
	if not args.dry_run:
		print("Note: existing members keep the Roles they got when they joined; "
			"remove and re-add them to pick up changes.")
	if failed:
		print(f"✗ {failed} group(s) failed")
		return 1
	return 0


if __name__ == "__main__":
	sys.exit(main())
