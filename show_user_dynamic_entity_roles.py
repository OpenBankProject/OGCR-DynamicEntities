"""List a user's dynamic entity entitlements (definition and record Roles).

By default it lists those at system level: bank id SYS (where system level
dynamic entity Roles are granted now) or empty (older grants). --bank-id lists
those at one bank id instead, e.g. ogcr. Read-only: one GET.

Usage:
    python3 show_user_dynamic_entity_roles.py USERNAME [--bank-id BANK_ID] [--provider PROVIDER]

Needs CanGetAnyUser for the logged in user (.env).
"""

import argparse
import sys

from obp_client import obp_host, session, token

SYSTEM_BANK_IDS = ("SYS", "")

parser = argparse.ArgumentParser(description="List a user's dynamic entity entitlements.")
parser.add_argument("username", help="The user to look at (not the one logged in from .env)")
parser.add_argument("--bank-id", help="Only this bank id (default: system level, SYS or empty)")
parser.add_argument("--provider", help="Needed if the username exists at more than one provider")
args = parser.parse_args()
bank_ids = (args.bank_id,) if args.bank_id else SYSTEM_BANK_IDS
where = f"bank id {args.bank_id}" if args.bank_id else "system level"

params = {"username": args.username}
if args.provider:
	params["provider"] = args.provider
response = session.get(f"{obp_host}/obp/v6.0.0/users", params=params,
	headers={"Authorization": f"DirectLogin token={token}"}, timeout=30)
if not response.ok:
	sys.exit(f"✗ {response.status_code} {response.text}")
users = response.json().get("users", [])
if not users:
	sys.exit(f"✗ No user {args.username} at {obp_host}")

for user in users:
	entitlements = user.get("entitlements", {}).get("list", [])
	dynamic = sorted(
		(e.get("role_name", ""), e.get("bank_id", ""), e.get("entitlement_id", ""))
		for e in entitlements
		if "DynamicEntity" in e.get("role_name", "") and e.get("bank_id", "") in bank_ids)
	print(f"{user.get('username')} ({user.get('user_id')}, provider {user.get('provider')}) at {obp_host}")
	print(f"{len(dynamic)} dynamic entity entitlement(s) at {where}, of {len(entitlements)} in all:")
	for role_name, bank_id, entitlement_id in dynamic:
		print(f"  {role_name:70} bank_id={bank_id or '(empty)':8} {entitlement_id}")
