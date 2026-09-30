"""Grant a user record Roles on some dynamic entities, at one bank id.

For each --entity, --access says which Roles (letters as in the Role Group
matrix, see role_groups.py): C create, R get (list and one), U update, D delete.
The bank id defaults to that of the entities' space (OBP_ENTITY_SPACE_ID, or
SYS for system level; see obp_space.py); --bank-id grants at another one.

Only Roles the user does not already hold at that bank id are granted (the user
gets an email for each one). It lists them and asks before granting; --dry-run
only lists them.

Usage:
    python3 grant_user_dynamic_entity_roles.py USERNAME --entity NAME [--entity NAME ...]
        [--access CRUD] [--bank-id BANK_ID] [--provider PROVIDER] [--dry-run]

Needs CanGetAnyUser and CanCreateEntitlementAtAnyBank for the logged in user (.env).
"""

import argparse
import re
import sys

from obp_client import obp_host, session, token
from obp_space import ROLE_BANK_ID
from role_groups import roles_for

parser = argparse.ArgumentParser(description="Grant a user record Roles on some dynamic entities.")
parser.add_argument("username", help="The user to grant to (not the one logged in from .env)")
parser.add_argument("--entity", action="append", required=True, metavar="NAME",
	help="Dynamic entity name; may be repeated")
parser.add_argument("--access", default="CRUD", help="Any of the letters C R U D (default: CRUD)")
parser.add_argument("--bank-id", default=ROLE_BANK_ID,
	help=f"Bank id to grant at (default: {ROLE_BANK_ID}, the space of the entities)")
parser.add_argument("--provider", help="Needed if the username exists at more than one provider")
parser.add_argument("--dry-run", action="store_true", help="Only list the Roles that would be granted")
args = parser.parse_args()
access = args.access.upper()
if not re.fullmatch(r"[CRUD]+", access):
	sys.exit(f"✗ --access {args.access!r} may only contain the letters C R U D")
H = {"Authorization": f"DirectLogin token={token}", "Content-Type": "application/json"}

params = {"username": args.username}
if args.provider:
	params["provider"] = args.provider
response = session.get(f"{obp_host}/obp/v6.0.0/users", params=params, headers=H, timeout=30)
if not response.ok:
	sys.exit(f"✗ {response.status_code} {response.text}")
users = response.json().get("users", [])
if len(users) != 1:
	sys.exit(f"✗ {len(users)} users named {args.username} at {obp_host}; pass --provider")
user = users[0]
held = {e.get("role_name") for e in user.get("entitlements", {}).get("list", [])
	if e.get("bank_id") == args.bank_id}

wanted = [role for entity in args.entity for role in roles_for(entity, access)]
missing = [r for r in wanted if r not in held]
print(f"{user['username']} ({user['user_id']}) at {obp_host}")
print(f"{len(wanted) - len(missing)} of {len(wanted)} Roles already held at {args.bank_id}; {len(missing)} to grant:")
for r in missing:
	print(f"  + {r}")
if not missing or args.dry_run:
	sys.exit(0)

if input(f"Grant these {len(missing)} Roles (one email each to {user['username']})? Type 'yes': ").strip() != "yes":
	sys.exit("Aborted. Nothing was granted.")

failed = 0
for role_name in missing:
	# v7.0.0: the older versions reject the SYS bank id.
	r = session.post(f"{obp_host}/obp/v7.0.0/users/{user['user_id']}/entitlements",
		json={"bank_id": args.bank_id, "role_name": role_name}, headers=H, timeout=30)
	if r.ok:
		print(f"  ✓ {role_name}")
	else:
		failed += 1
		print(f"  ✗ {role_name}: {r.status_code} {r.text}")
print(f"{len(missing) - failed} granted, {failed} failed")
sys.exit(1 if failed else 0)
