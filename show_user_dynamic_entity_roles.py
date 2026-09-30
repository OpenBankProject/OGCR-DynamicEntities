"""List a user's dynamic entity entitlements (definition and record Roles).

By default it lists those at the bank id of the entities' space
(OBP_ENTITY_SPACE_ID; see obp_space.py). For system level that is SYS, and the
empty bank id (older grants) is listed too. --bank-id lists those at another
bank id instead. --by-entity lists one line per entity instead, with the record
access its Roles give, in the letters of the Role Group matrix (C create, R get,
U update, D delete; see role_groups.py).

Each Role is marked with the group that granted it, or as not granted through a
group (by hand, by an entitlement request, or by a group since deleted), which
removing the user from groups leaves; so are those at other bank ids, counted at
the end. Read-only.

Usage:
    python3 show_user_dynamic_entity_roles.py USERNAME [--bank-id BANK_ID] [--provider PROVIDER] [--by-entity]

Needs CanGetAnyUser for the logged in user (.env), and CanGetUserGroupMembershipsAtOneBank
(or ...AtAllBanks) to see which group granted what.
"""

import argparse
import sys
from collections import defaultdict

from obp_client import obp_host, session, token
from create_role_groups import direct_roles, get_user_memberships, roles_by_group
from obp_space import ROLE_BANK_ID
from role_groups import ACCESS_ORDER, ROLE_PREFIX_BY_LETTER

SYSTEM_BANK_IDS = ("SYS", "")

parser = argparse.ArgumentParser(description="List a user's dynamic entity entitlements.")
parser.add_argument("username", help="The user to look at (not the one logged in from .env)")
parser.add_argument("--bank-id", default=ROLE_BANK_ID,
	help=f"Only this bank id (default: {ROLE_BANK_ID}, the space of the entities; SYS includes the empty bank id)")
parser.add_argument("--provider", help="Needed if the username exists at more than one provider")
parser.add_argument("--by-entity", action="store_true",
	help="One line per entity, with its record access as C R U D letters")
args = parser.parse_args()
bank_ids = SYSTEM_BANK_IDS if args.bank_id in SYSTEM_BANK_IDS else (args.bank_id,)
where = "system level" if args.bank_id in SYSTEM_BANK_IDS else f"bank id {args.bank_id}"

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
	try:
		memberships = get_user_memberships(user["user_id"])
	except Exception as e:
		memberships = None
		print(f"! Could not list their groups, so not which group granted what: {e}")
	by_group = roles_by_group(memberships or [])

	def source(role_name, bank_id):
		if memberships is None:
			return ""
		group = by_group.get((bank_id or "", role_name))
		return f"via {group!r}" if group else "NOT through a group"

	if args.by_entity:
		# (entity, bank_id) -> access letters; the other Roles (e.g. definitions) are listed after.
		access = defaultdict(set)
		direct = defaultdict(set)  # the letters of those not granted through a group
		others = []
		for role_name, bank_id, _ in dynamic:
			letter = next((c for c, prefix in ROLE_PREFIX_BY_LETTER.items() if role_name.startswith(prefix)), None)
			if letter:
				key = (role_name[len(ROLE_PREFIX_BY_LETTER[letter]):], bank_id)
				access[key].add(letter)
				if source(role_name, bank_id) == "NOT through a group":
					direct[key].add(letter)
			else:
				others.append((role_name, bank_id))
		print(f"{len(access)} entities with record access at {where}:")
		width = max((len(entity) for entity, _ in access), default=0)
		for (entity, bank_id), letters in sorted(access.items()):
			bank = f"  bank_id={bank_id or '(empty)'}" if len(bank_ids) > 1 else ""
			not_group = "".join(c for c in ACCESS_ORDER if c in direct[(entity, bank_id)])
			note = f"  ({not_group} NOT through a group)" if not_group else ""
			print(f"  {entity:{width}}  {''.join(c for c in ACCESS_ORDER if c in letters):4}{bank}{note}".rstrip())
		if others:
			print("Other dynamic entity Roles:")
			for role_name, bank_id in others:
				print(f"  {role_name}  bank_id={bank_id or '(empty)'}  {source(role_name, bank_id)}".rstrip())
	else:
		print(f"{len(dynamic)} dynamic entity entitlement(s) at {where}, of {len(entitlements)} in all:")
		for role_name, bank_id, entitlement_id in dynamic:
			print(f"  {role_name:70} bank_id={bank_id or '(empty)':8} {entitlement_id}  {source(role_name, bank_id)}".rstrip())
	if memberships is not None:
		elsewhere = [(b, r) for b, r in direct_roles(entitlements, memberships) if b not in bank_ids]
		if elsewhere:
			print(f"! {len(elsewhere)} more Role(s) not granted through a group, at bank ids "
				f"{', '.join(sorted({b or '(empty)' for b, _ in elsewhere}))}; --bank-id to see them")
