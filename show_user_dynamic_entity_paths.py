"""Show the dynamic entity record paths a user can call, one per line: the v7.0.0
ones first (banks such as ogcr, then SYS), then the legacy /obp/dynamic-entity ones.

In v7.0.0 records live at /obp/v7.0.0/banks/BANK_ID/dynamic-entities/ENTITY[/ID],
BANK_ID being a bank id or SYS for the system space, and each Role is checked
at the BANK_ID in the URL:

    CanCreateDynamicEntityRecord_ENTITY  POST   .../ENTITY
    CanGetDynamicEntityRecord_ENTITY     GET    .../ENTITY  and  .../ENTITY/ID
    CanUpdateDynamicEntityRecord_ENTITY  PUT    .../ENTITY/ID
    CanDeleteDynamicEntityRecord_ENTITY  DELETE .../ENTITY/ID

The same Roles open the unversioned paths, /obp/dynamic-entity/ENTITY[/ID] for
the system space (Roles at SYS) and /obp/dynamic-entity/banks/BANK_ID/ENTITY[/ID]
for a bank. Roles granted at an empty bank id match no path and are listed separately.
Each entity is also checked against the definitions in its space, when the
logged in user (.env) may list them. Read-only.

Usage:
    python3 show_user_dynamic_entity_paths.py USERNAME [--provider PROVIDER]

Needs CanGetAnyUser for the logged in user (.env), and CanGetDynamicEntityDefinitions
at a bank id to check the entities there exist.
"""

import argparse
import re
import sys
from collections import defaultdict

from obp_client import obp_host, session, token

ROLE_RE = re.compile(r"^Can(Create|Get|Update|Delete)DynamicEntityRecord_(.+)$")
PATHS = {
	"Create": [("POST", "")],
	"Get": [("GET", ""), ("GET", "/ID")],
	"Update": [("PUT", "/ID")],
	"Delete": [("DELETE", "/ID")],
}
OPS = ["Create", "Get", "Update", "Delete"]

parser = argparse.ArgumentParser(description="Show the dynamic entity record paths a user can call.")
parser.add_argument("username", help="The user to look at (not the one logged in from .env)")
parser.add_argument("--provider", help="Needed if the username exists at more than one provider")
args = parser.parse_args()
H = {"Authorization": f"DirectLogin token={token}"}

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

by_space = defaultdict(lambda: defaultdict(set))  # bank_id -> entity -> {ops}
for e in user.get("entitlements", {}).get("list", []):
	m = ROLE_RE.match(e.get("role_name", ""))
	if m:
		by_space[e.get("bank_id", "")][m.group(2)].add(m.group(1))


def definitions(bank_id):
	"""Entity names defined in the space, or None if they can't be listed."""
	r = session.get(f"{obp_host}/obp/v7.0.0/management/banks/{bank_id}/dynamic-entities", headers=H, timeout=30)
	if not r.ok:
		return None
	return {d.get("entity_name") for d in r.json().get("dynamic_entities", [])}


def legacy_prefix(bank_id):
	return "/obp/dynamic-entity" + ("" if bank_id == "SYS" else f"/banks/{bank_id}")


def v7_prefix(bank_id):
	return f"/obp/v7.0.0/banks/{bank_id}/dynamic-entities"


# Banks (e.g. ogcr) first, then SYS. Roles at an empty bank id match no path.
spaces = sorted((b for b in by_space if b and b != "SYS")) + (["SYS"] if "SYS" in by_space else [])
defined = {b: definitions(b) for b in spaces}


def print_paths(prefix_for):
	for bank_id in spaces:
		for entity in sorted(by_space[bank_id]):
			known = defined[bank_id]
			note = "" if known is None or entity in known else "   (entity not defined here: 404)"
			for op in OPS:
				if op in by_space[bank_id][entity]:
					for method, suffix in PATHS[op]:
						print(f"{method:6} {prefix_for(bank_id)}/{entity}{suffix}{note}")


print(f"{user['username']} ({user['user_id']}) at {obp_host}")
for bank_id in spaces:
	if defined[bank_id] is None:
		print(f"(could not list the definitions at {bank_id} to check the entities exist)")
if not spaces:
	print("No dynamic entity record Roles.")
else:
	print("\nv7.0.0 paths:")
	print_paths(v7_prefix)
	print("\nLegacy paths:")
	print_paths(legacy_prefix)
if "" in by_space:
	print(f"\nRoles at an empty bank id (no path uses them): {', '.join(sorted(by_space['']))}")
