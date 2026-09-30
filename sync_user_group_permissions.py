"""Bring one user's group memberships and Roles in line with the users sheet and the groups.

  1. Memberships, as ticked in the users sheet (add_users_to_groups.py --user):
     added to each group ticked for them, and removed from each of the sheet's
     groups they are in but not ticked for (--remove-unticked).
  2. Roles (POST /obp/v7.0.0/management/users/USER_ID/sync-groups): in every group
     they are in, at any bank id, a Role of the group they do not hold is granted,
     and one the group no longer grants is deleted, unless another of their groups
     still grants it. Entitlements left by groups since deleted are moved to
     another of their groups that grants the Role, or deleted.

Then it lists the Roles the user holds that none of their groups granted (by
hand, or by an entitlement request), at any bank id: the sync leaves those.

The groups' Roles are taken as they are on OBP: to change them from the Role
Group matrix, run create_role_groups.sh (--user USERNAME to bring only this user
up to date). The user gets an email for each Role granted.

With --dry-run nothing is changed. Step 2 is then previewed against the groups
the user is in now, not as step 1 would leave them.

Usage:
    python3 sync_user_group_permissions.py --user USERNAME [path/to/users.xlsx] [--sheet NAME] [--dry-run]
    python3 sync_user_group_permissions.py USERNAME [--sheet NAME] [--dry-run]

Needs what add_users_to_groups.py needs (CanGetAnyUser, CanGetUserGroupMembershipsAtOneBank,
CanAddUserToGroupAtOneBank and CanRemoveUserFromGroupAtOneBank at the space's bank id,
or the ...AtAllBanks versions), and the add and remove Roles at the bank id of every
other group the user is in.

Exits 0 on success, 1 if anything failed.
"""

import argparse
import sys

import add_users_to_groups
from add_users_to_groups import DEFAULT_FILE, DEFAULT_SHEET, find_user, read_sheet
from create_role_groups import direct_roles, get_groups_at_space, get_user_memberships, print_direct_roles, sync_user


def main():
	parser = argparse.ArgumentParser(description="Bring one user's group memberships and Roles in line with the users sheet and the groups.")
	parser.add_argument("--user", metavar="USERNAME", help="The user to sync (column A of the users sheet)")
	parser.add_argument("positional", nargs="*", metavar="[USERNAME] [FILE]",
		help=f"The user, if not given with --user, then the users xlsx file (default: {DEFAULT_FILE})")
	parser.add_argument("--sheet", default=DEFAULT_SHEET, help=f"Sheet to read (default: {DEFAULT_SHEET})")
	parser.add_argument("--dry-run", action="store_true", help="Only say what would change")
	args = parser.parse_args()
	rest = list(args.positional)
	args.username = args.user or (rest.pop(0) if rest else None)
	if not args.username:
		parser.error("give the user: --user USERNAME")
	if len(rest) > 1:
		parser.error(f"unexpected arguments: {' '.join(rest[1:])}")
	args.file = rest[0] if rest else DEFAULT_FILE
	tag = "[DRY RUN] " if args.dry_run else ""

	print(f"{tag}Step 1/2: {args.username}'s group memberships, as ticked in {args.sheet!r}")
	argv = [args.file, "--sheet", args.sheet, "--user", args.username, "--remove-unticked", "--skip-direct-roles"]
	argv += ["--dry-run"] if args.dry_run else []
	failed = add_users_to_groups.main(argv)

	print(f"\n{tag}Step 2/2: {args.username}'s Roles, in every group they are in")
	if args.dry_run:
		print("(previewed against the groups they are in now, before step 1's changes)")
	# The sheet was read, and the user found in it, in step 1; look them up the same way.
	_, users, _ = read_sheet(args.file, args.sheet)
	row = next((u for u in users if u["username"] == args.username), None)
	if row is None:
		return 1
	user, problem = find_user(row["username"], row["provider"])
	if problem:
		print(f"✗ {args.username}: {problem}")
		return 1
	try:
		group_names = {g["group_id"]: name for name, g in get_groups_at_space().items()}
	except Exception as e:
		print(f"! Could not list the groups (their ids are printed instead): {e}")
		group_names = {}
	failed += sync_user(user["user_id"], group_names, args.dry_run, tag)

	print(f"\n{args.username}'s Roles not granted through a group" + (" (as they are now)" if args.dry_run else ""))
	user, problem = find_user(row["username"], row["provider"])  # again: step 1 and 2 changed them
	try:
		if problem:
			raise RuntimeError(problem)
		print_direct_roles(direct_roles(user.get("entitlements", {}).get("list", []), get_user_memberships(user["user_id"])))
	except Exception as e:
		failed += 1
		print(f"✗ Could not list them: {e}")
	return 1 if failed else 0


if __name__ == "__main__":
	sys.exit(main())
