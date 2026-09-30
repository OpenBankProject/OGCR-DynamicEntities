"""Create or update one OBP Group per Role Group in the minimum fields spreadsheet.

The Role Group matrix (columns R onwards of min_field_matrix.xlsx; see
role_groups.py) says which record endpoints each group may call on each entity.
Each column becomes an OBP Group, named after its header, at the bank id of the
entities' space (OBP_ENTITY_SPACE_ID, or SYS for system level; see obp_space.py),
holding the matching CanCreate/Get/Update/DeleteDynamicEntityRecord_<entity>
Roles, plus CanGetDynamicEntityDefinitions (role_groups.MEMBER_ROLES) so every
member can list the entity definitions. Adding a user to the group then grants
them those Roles at that bank id.

A group that already exists there (matched by name) has its Roles replaced by
the sheet's, so it always matches the sheet. Groups there that are not in the
sheet are left alone.

OBP copies a group's Roles to a user when the user is ADDED to the group, so
changing the group does not change its existing members' Roles. After each
existing group is updated, OBP brings its members up to date in place, without
anyone leaving the group (POST /obp/v7.0.0/management/groups/GROUP_ID/sync-members):
  - a Role of the group a member does not hold at all is granted to them;
  - a Role taken out of the group has the member's entitlement for it, granted
    by this group, deleted -- unless another group the member is in still grants
    that Role, in which case it is kept and recorded against that group.
With --dry-run the members are previewed against the group's Roles as they are
on OBP now, since the group itself is not updated.

With --user USERNAME the groups are still created and updated from the sheet,
but only that user is brought up to date, in every group they are in (at any
bank id), and the other members are left as they are until a run without --user
(POST /obp/v7.0.0/management/users/USER_ID/sync-groups). That also clears the
user's entitlements left by groups since deleted: each is moved to another of
their groups that grants the Role, or deleted.

Needs CanCreateGroupAtOneBank, CanUpdateGroupAtOneBank and CanGetGroupsAtOneBank
at that bank id (or the ...AtAllBanks versions); updating members also needs
CanAddUserToGroupAtOneBank and CanRemoveUserFromGroupAtOneBank (or ...AtAllBanks);
--user also needs CanGetAnyUser.

Usage:
    python3 create_role_groups.py [path/to/min_field_matrix.xlsx] [--user USERNAME [--provider PROVIDER]] [--dry-run]

Exits 0 on success, 1 if the sheet has errors in the matrix or anything failed.
"""

import argparse
import sys
from collections import defaultdict

from get_and_delete_dynamic_entities import get_all_system_dynamic_entities
from obp_client import token, obp_host, session
from obp_space import ROLE_BANK_ID, describe
from role_groups import MEMBER_ROLES, group_roles, parse_role_groups

DEFAULT_SPREADSHEET = "min_field_matrix.xlsx"
GROUPS_URL = f"{obp_host}/obp/v6.0.0/management/groups"
USERS_URL = f"{obp_host}/obp/v6.0.0/users"
SYNC_GROUPS_URL = f"{obp_host}/obp/v7.0.0/management/groups"
SYNC_USERS_URL = f"{obp_host}/obp/v7.0.0/management/users"


def headers():
	return {"Authorization": f"DirectLogin token={token}", "Content-Type": "application/json"}


def get_groups_at_space():
	"""{group_name: group} of the groups at ROLE_BANK_ID."""
	response = session.get(GROUPS_URL, params={"bank_id": ROLE_BANK_ID}, headers=headers(), timeout=30)
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


def get_group_members(group_id):
	"""{user_id: {"username", "roles", "entitlement_ids"}} of a group's members, from the
	entitlements it granted (`entitlement_ids` maps role -> entitlement id).
	A member holding none of the group's Roles through it (e.g. the group had none) is not seen."""
	response = session.get(f"{GROUPS_URL}/{group_id}/entitlements", headers=headers(), timeout=30)
	if not response.ok:
		raise RuntimeError(f"{response.status_code} {response.text}")
	members = {}
	for e in response.json().get("entitlements", []):
		member = members.setdefault(e["user_id"],
			{"username": e.get("username", ""), "roles": set(), "entitlement_ids": {}})
		member["roles"].add(e["role_name"])
		member["entitlement_ids"][e["role_name"]] = e["entitlement_id"]
	return members


def sync_members(group_id, dry_run, tag):
	"""Bring the group's members in line with its Roles on OBP (POST .../sync-members), without
	taking anyone out of the group. Returns the number of failures."""
	response = session.post(f"{SYNC_GROUPS_URL}/{group_id}/sync-members",
		params={"dry_run": "true"} if dry_run else None, headers=headers(), timeout=120)
	if not response.ok:
		print(f"  ✗ Could not sync the members: {response.status_code} {response.text}")
		return 1
	members = response.json().get("members", [])
	updated = 0
	for m in members:
		created, deleted, moved = m["entitlements_created"], m["entitlements_deleted"], m["entitlements_moved"]
		if not (created or deleted or moved):
			continue
		updated += 1
		print(f"  {tag}UPDATE member {m['username']} ({m['user_id']}): +{len(created)} -{len(deleted)} Role(s)")
		for r in created:
			print(f"      + {r}")
		for r in deleted:
			print(f"      - {r}")
		for mv in moved:
			print(f"      = {mv['role_name']} (kept: now granted by group {mv['to_group_id']})")
	if members:
		print(f"  {len(members)} member(s), {updated} {'to update' if dry_run else 'updated'}")
	return 0


def get_user_memberships(user_id):
	"""The groups the user is in, each with `list_of_entitlements`: the Roles it granted them.
	Needs CanGetUserGroupMembershipsAtOneBank at each group's bank id (or ...AtAllBanks)."""
	response = session.get(f"{USERS_URL}/{user_id}/group-entitlements", headers=headers(), timeout=30)
	if not response.ok:
		raise RuntimeError(f"{response.status_code} {response.text}")
	return response.json().get("group_entitlements", [])


def roles_by_group(memberships):
	"""{(bank_id, role_name): group_name} of the Roles the user holds through their groups."""
	return {(m.get("bank_id") or "", role): m.get("group_name")
		for m in memberships for role in m.get("list_of_entitlements") or []}


def direct_roles(entitlements, memberships):
	"""[(bank_id, role_name)] of the user's entitlements that none of their groups granted: granted
	by hand, by an entitlement request, or by a group since deleted. Removing the user from their
	groups leaves these. `entitlements` as in GET /users (bank_id, role_name)."""
	by_group = roles_by_group(memberships)
	return sorted({(e.get("bank_id") or "", e["role_name"]) for e in entitlements} - by_group.keys())


def print_direct_roles(direct, indent=""):
	"""Say which Roles were not granted through a group, by bank id."""
	if not direct:
		print(f"{indent}All Roles granted through groups")
		return
	print(f"{indent}! {len(direct)} Role(s) not granted through a group (removing the user from groups leaves them):")
	by_bank = defaultdict(list)
	for bank_id, role in direct:
		by_bank[bank_id].append(role)
	for bank_id, roles in sorted(by_bank.items()):
		print(f"{indent}    {bank_id or '(empty)'}: {', '.join(roles)}")


def find_user_id(username, provider):
	"""The user_id of the one user with this username (and provider, if given); raises if not exactly one."""
	params = {"username": username}
	if provider:
		params["provider"] = provider
	response = session.get(USERS_URL, params=params, headers=headers(), timeout=30)
	if not response.ok:
		raise RuntimeError(f"{response.status_code} {response.text}")
	users = response.json().get("users", [])
	if len(users) != 1:
		raise RuntimeError(f"{len(users)} users named {username}" + ("" if provider else "; pass --provider"))
	return users[0]["user_id"]


def sync_user(user_id, group_names, dry_run, tag):
	"""Bring one user in line with every group they are in (POST .../users/USER_ID/sync-groups), and clear
	what is left of groups since deleted. Returns the number of failures."""
	response = session.post(f"{SYNC_USERS_URL}/{user_id}/sync-groups",
		params={"dry_run": "true"} if dry_run else None, headers=headers(), timeout=120)
	if not response.ok:
		print(f"✗ Could not sync {user_id}: {response.status_code} {response.text}")
		return 1
	body = response.json()
	print(f"{tag}SYNC user {body['username']} ({body['user_id']}) in {len(body['groups'])} group(s)")
	for g in body["groups"]:
		created, deleted, moved = g["entitlements_created"], g["entitlements_deleted"], g["entitlements_moved"]
		label = f"deleted group {g['group_id']}" if g["group_deleted"] else \
			f"{group_names.get(g['group_id'], g['group_id'])!r} (bank id {g['bank_id'] or 'none'})"
		if not (created or deleted or moved):
			print(f"    = {label}")
			continue
		print(f"    {label}: +{len(created)} -{len(deleted)} Role(s)")
		for r in created:
			print(f"      + {r}")
		for r in deleted:
			print(f"      - {r}")
		for mv in moved:
			print(f"      = {mv['role_name']} (kept: now granted by group {group_names.get(mv['to_group_id'], mv['to_group_id'])})")
	return 0


# Earlier versions of this script wrote a generated description starting with this; it is cleared.
OLD_GENERATED_DESCRIPTION = "OGCR Role Group from column "


def main():
	parser = argparse.ArgumentParser(description="Create or update the OBP Groups defined in the spreadsheet's Role Group matrix.")
	parser.add_argument("file", nargs="?", default=DEFAULT_SPREADSHEET,
		help=f"Path to the xlsx file (default: {DEFAULT_SPREADSHEET})")
	parser.add_argument("--user", metavar="USERNAME",
		help="Bring only this user up to date, in every group they are in (other members are left as they are)")
	parser.add_argument("--provider", help="With --user: needed if the username exists at more than one provider")
	parser.add_argument("--dry-run", action="store_true", help="Only say what would be created or updated")
	args = parser.parse_args()
	if args.provider and not args.user:
		parser.error("--provider needs --user")
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

	user_id = None
	if args.user:
		try:
			user_id = find_user_id(args.user, args.provider)
		except Exception as e:
			print(f"✗ Could not find the user {args.user}: {e}")
			return 1
		print(f"Only {args.user} ({user_id}) is brought up to date; other members are left as they are")

	failed = 0
	for group in groups:
		name = group["name"]
		roles = group_roles(group)
		# No description is set; OBP requires the field on create, so it is empty.
		body = {
			"group_name": name,
			"list_of_roles": roles,
			"is_enabled": True,
		}
		existing = on_obp.get(name)
		clear_description = existing is not None and \
			(existing.get("group_description") or "").startswith(OLD_GENERATED_DESCRIPTION)
		if clear_description:
			body["group_description"] = ""
		if existing is None:
			if roles == MEMBER_ROLES:
				print(f"{tag}Skipping {name!r} (column {group['column']}): no access ticked")
				continue
			print(f"{tag}CREATE group {name!r} with {len(roles)} Role(s)")
			for r in roles:
				print(f"    + {r}")
			if args.dry_run:
				continue
			response = session.post(GROUPS_URL, json={**body, "bank_id": ROLE_BANK_ID, "group_description": ""},
				headers=headers(), timeout=30)
		else:
			before = set(existing.get("list_of_roles") or [])
			added = [r for r in roles if r not in before]
			removed = sorted(before - set(roles))
			if not added and not removed and existing.get("is_enabled") and not clear_description:
				print(f"{tag}Unchanged group {name!r} ({existing['group_id']}): {len(roles)} Role(s)")
				if not user_id:
					failed += sync_members(existing["group_id"], args.dry_run, tag)
				continue
			print(f"{tag}UPDATE group {name!r} ({existing['group_id']}): {len(roles)} Role(s)")
			for r in added:
				print(f"    + {r}")
			for r in removed:
				print(f"    - {r}")
			if not existing.get("is_enabled"):
				print("    enable it")
			if clear_description:
				print("    clear the generated description")
			if not args.dry_run:
				response = session.put(f"{GROUPS_URL}/{existing['group_id']}", json=body,
					headers=headers(), timeout=30)
				if not response.ok:
					failed += 1
					print(f"  ✗ {response.status_code} {response.text}")
					continue  # members stay as they are
				print(f"  ✓ {response.json().get('group_id')}")
			if not user_id:
				failed += sync_members(existing["group_id"], args.dry_run, tag)
			continue

		if response.ok:
			print(f"  ✓ {response.json().get('group_id')}")
		else:
			failed += 1
			print(f"  ✗ {response.status_code} {response.text}")

	others = sorted(n for n in on_obp if n not in {g["name"] for g in groups})
	if others:
		print(f"Left untouched (not in the sheet): {', '.join(others)}")
	if user_id:
		# Groups made in this run are not in on_obp; their ids are printed as they are.
		failed += sync_user(user_id, {g["group_id"]: n for n, g in on_obp.items()}, args.dry_run, tag)
	if failed:
		print(f"✗ {failed} failure(s)")
		return 1
	return 0


if __name__ == "__main__":
	sys.exit(main())
