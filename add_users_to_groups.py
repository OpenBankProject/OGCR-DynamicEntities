"""Add users to the OGCR Role Groups, as ticked in a users spreadsheet.

The sheet (by default the `Users-Groups-DO_NOT_COMMIT` sheet of
DO_NOT_COMMIT/Users-Group-DO_NOT_COMMIT.xlsx, which holds real usernames and
must not be committed) has a header on row 1:

    A Username | B Provider | C onwards: one column per group (e.g. Operator)

and one row per user, with TRUE (or a checkmark) under each group the user
should be in. The group columns run from C until the first empty header, and
are matched by name to the OBP Groups that create_role_groups.sh made at the
bank id of the entities' space (OBP_ENTITY_SPACE_ID, or SYS for system level).

Each user is looked up by username, and by provider too when column B is filled
(needed when the same username exists at more than one provider). Adding a user
grants them the group's Roles. Users already in a group are left as they are.
Nobody is removed: a user who is in a group but not ticked for it is only reported.

Needs CanGetAnyUser, and CanAddUserToGroupAtOneBank at that bank id (or
CanAddUserToGroupAtAllBanks); CanGetEntitlementsForAnyBank to see who is
already in a group.

Usage:
    python3 add_users_to_groups.py [path/to/users.xlsx] [--sheet NAME] [--user USERNAME] [--dry-run]

Exits 0 on success, 1 if the sheet could not be used or anything failed.
"""

import argparse
import sys

import pandas as pd
import requests

from check_min_field_matrix import has_green_checkmark
from create_role_groups import USERS_URL, get_group_members, get_groups_at_space, headers
from obp_space import ROLE_BANK_ID

DEFAULT_FILE = "DO_NOT_COMMIT/Users-Group-DO_NOT_COMMIT.xlsx"
DEFAULT_SHEET = "Users-Groups-DO_NOT_COMMIT"
FIRST_GROUP_COLUMN = 2  # column C


def cell(row, idx):
	value = row.iloc[idx] if len(row) > idx else None
	return "" if value is None or pd.isna(value) else str(value).strip()


def read_sheet(file_path, sheet):
	"""Return (group_names, users, errors). users is a list of
	{"row", "username", "provider", "groups"}, in sheet order."""
	df = pd.read_excel(file_path, sheet_name=sheet, engine="openpyxl")
	errors = []
	headers_ = [str(h).strip() for h in df.columns]
	if len(headers_) < 2 or headers_[0].lower() != "username" or headers_[1].lower() != "provider":
		errors.append(f"A1:B1 should be 'Username' and 'Provider', found {headers_[:2]}")
		return [], [], errors
	group_names = []
	for h in headers_[FIRST_GROUP_COLUMN:]:
		if not h or h.startswith("Unnamed:"):
			break
		group_names.append(h)

	users, seen = [], {}
	for index, row in df.iterrows():
		excel_row = index + 2  # header is row 1
		username = cell(row, 0)
		if not username:
			continue
		provider = cell(row, 1)
		key = (username, provider)
		if key in seen:
			errors.append(f"A{excel_row}: {username} is already listed at A{seen[key]}")
			continue
		seen[key] = excel_row
		groups = [name for i, name in enumerate(group_names)
			if has_green_checkmark(cell(row, FIRST_GROUP_COLUMN + i))]
		users.append({"row": excel_row, "username": username, "provider": provider, "groups": groups})
	return group_names, users, errors


def find_user(username, provider):
	"""Return (user, problem): the OBP user, or None and why not."""
	params = {"username": username, "limit": 50}
	if provider:
		params["provider"] = provider
	response = requests.get(USERS_URL, params=params, headers=headers(), timeout=30)
	if not response.ok:
		return None, f"lookup failed: {response.status_code} {response.text}"
	found = response.json().get("users", [])
	if not found:
		return None, "no such user" + (f" at provider {provider}" if provider else "")
	if len(found) > 1:
		providers = ", ".join(sorted(u.get("provider", "") for u in found))
		return None, f"{len(found)} users with this username (providers: {providers}); fill in the Provider column"
	return found[0], None


def main():
	parser = argparse.ArgumentParser(description="Add users to the OGCR Role Groups, as ticked in a users spreadsheet.")
	parser.add_argument("file", nargs="?", default=DEFAULT_FILE, help=f"Path to the xlsx file (default: {DEFAULT_FILE})")
	parser.add_argument("--sheet", default=DEFAULT_SHEET, help=f"Sheet to read (default: {DEFAULT_SHEET})")
	parser.add_argument("--user", help="Only this username (column A)")
	parser.add_argument("--dry-run", action="store_true", help="Only say who would be added to which group")
	args = parser.parse_args()
	tag = "[DRY RUN] " if args.dry_run else ""

	try:
		group_names, users, errors = read_sheet(args.file, args.sheet)
	except Exception as e:
		print(f"✗ Could not read sheet {args.sheet!r} of {args.file}: {e}")
		return 1
	for e in errors:
		print(f"✗ {e}")
	if errors:
		print("✗ Fix the sheet first. Nothing was changed.")
		return 1
	if args.user:
		users = [u for u in users if u["username"] == args.user]
		if not users:
			print(f"✗ {args.user} is not in column A of {args.sheet!r}")
			return 1

	try:
		on_obp = get_groups_at_space()
	except Exception as e:
		print(f"✗ Could not list the groups at bank id {ROLE_BANK_ID}: {e}")
		return 1
	missing = [g for g in group_names if g not in on_obp]
	if missing:
		print(f"✗ No group at bank id {ROLE_BANK_ID} named: {', '.join(missing)} "
			"(run ./create_role_groups.sh, or fix the header). Nothing was changed.")
		return 1

	members = {}  # group name -> {user_id: ...}
	for name in group_names:
		group = on_obp[name]
		if not group.get("list_of_roles"):
			print(f"! Group {name!r} has no Roles, so its members can't be seen or given anything")
		try:
			members[name] = get_group_members(group["group_id"])
		except Exception as e:
			print(f"✗ Could not list the members of {name!r}: {e}")
			return 1

	print(f"{tag}{len(users)} user(s) from {args.sheet!r}, groups at bank id {ROLE_BANK_ID}: {', '.join(group_names)}")
	failed = 0
	for u in users:
		label = u["username"] + (f" ({u['provider']})" if u["provider"] else "")
		user, problem = find_user(u["username"], u["provider"])
		if problem:
			failed += 1
			print(f"✗ A{u['row']} {label}: {problem}")
			continue
		user_id = user["user_id"]
		in_groups = [name for name in group_names if user_id in members[name]]
		extra = [name for name in in_groups if name not in u["groups"]]
		to_add = [name for name in u["groups"] if name not in in_groups]
		print(f"{label} ({user_id}): ticked {', '.join(u['groups']) or 'none'}")
		for name in u["groups"]:
			if name not in to_add:
				print(f"    = already in {name!r}")
		for name in extra:
			print(f"    ! in {name!r} but not ticked for it (not removed)")
		for name in to_add:
			print(f"    {tag}+ ADD to {name!r}")
			if args.dry_run:
				continue
			response = requests.post(f"{USERS_URL}/{user_id}/group-entitlements",
				json={"group_id": on_obp[name]["group_id"]}, headers=headers(), timeout=30)
			if response.ok:
				print(f"      ✓ {len(response.json().get('entitlements_created', []))} Role(s) granted")
			else:
				failed += 1
				print(f"      ✗ {response.status_code} {response.text}")

	if failed:
		print(f"✗ {failed} failure(s)")
		return 1
	return 0


if __name__ == "__main__":
	sys.exit(main())
