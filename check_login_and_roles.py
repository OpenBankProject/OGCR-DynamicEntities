"""Check DirectLogin and the current user's Roles — nothing else.

Read-only: it logs in with the credentials from `.env` / the environment
(OBP_HOSTNAME, OBP_USERNAME, OBP_PASSWORD, OBP_CONSUMER_KEY), fetches the
current user, and reports which of the Roles this project needs are present
and which are missing. It creates, updates and deletes nothing.

When OBP_ENTITY_SPACE_ID is set it also checks that bank exists.

Roles checked, at the bank id of the entities' space (OBP_ENTITY_SPACE_ID, or
SYS for system level; see obp_space.py):
  - the entity DEFINITION Roles
  - the entity RECORD Roles for every `Entity: <name>` in the parsed entities
    file (default `entities_output.txt`)
  - any extra Roles passed with --role (at the empty bank id, or
    ROLE@BANK_ID for a bank level Role)

Usage:
    python3 check_login_and_roles.py [path/to/entities_output.txt]
                                     [--no-entities] [--role ROLE[@BANK_ID] ...]
                                     [--list]

Exits 0 if login worked and every checked Role is present, 1 if login failed,
2 if any Role is missing, 3 if the OBP_ENTITY_SPACE_ID bank does not exist.
"""

import argparse
import logging
import os
import sys

import requests
from dotenv import load_dotenv

from obp_space import ROLE_BANK_ID, SPACE_ID, describe

load_dotenv()

logging.basicConfig(
	level=os.getenv('OBP_LOG_LEVEL', 'INFO'),
	format='%(asctime)s | %(levelname)-8s | %(message)s',
	datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)

DEFAULT_INPUT = "entities_output.txt"
ENTITY_PREFIX = "Entity:"
# The Roles the dynamic entity management endpoints require (per the server's resource docs). They
# replaced the old CanXSystemLevelDynamicEntity names and, like the record Roles, are granted at the
# bank id of the space.
META_ROLE_NAMES = [
	"CanCreateDynamicEntityDefinition",
	"CanDeleteDynamicEntityDefinition",
	"CanGetDynamicEntityDefinitions",
	"CanUpdateDynamicEntityDefinition",
]
RECORD_ROLE_PREFIXES = [
	"CanCreateDynamicEntityRecord_",
	"CanDeleteDynamicEntityRecord_",
	"CanGetDynamicEntityRecord_",
	"CanUpdateDynamicEntityRecord_",
]


def mask_credential(value):
	"""Mask a credential showing first 3 and last 2 characters"""
	if len(value) <= 5:
		return value[:1] + '*' * (len(value) - 1)
	return value[:3] + '*' * (len(value) - 5) + value[-2:]


def parse_entity_names(path):
	"""Extract entity names from `Entity: <name>` lines in the parsed file."""
	names = []
	with open(path, encoding="utf-8") as f:
		for line in f:
			line = line.rstrip("\n")
			if line.startswith(ENTITY_PREFIX):
				name = line[len(ENTITY_PREFIX):].strip()
				if name:
					names.append(name)
	return names


def direct_login(host, username, password, consumer_key):
	"""Return a DirectLogin token, or None (with the reason logged)."""
	url = f"{host}/my/logins/direct"
	authorization = f"DirectLogin username={username},password={password},consumer_key={consumer_key}"
	headers = {'Content-Type': 'application/json', 'Authorization': authorization}
	try:
		response = requests.post(url, headers=headers, timeout=30)
	except requests.exceptions.RequestException as e:
		logger.error(f"✗ Cannot reach {url}: {e}")
		return None
	try:
		body = response.json()
	except ValueError:
		body = {}
	if "token" not in body:
		logger.error(f"✗ DirectLogin failed ({response.status_code}): {response.text}")
		return None
	return body["token"]


def get_current_user(host, token):
	url = f"{host}/obp/v6.0.0/users/current"
	headers = {'Authorization': f"DirectLogin token={token}"}
	response = requests.get(url, headers=headers, timeout=30)
	if response.status_code != 200:
		logger.error(f"✗ GET {url} failed ({response.status_code}): {response.text}")
		return None
	return response.json()


def required_roles(args):
	"""Return a list of (role_name, bank_id) pairs to check."""
	roles = [(r, ROLE_BANK_ID) for r in META_ROLE_NAMES]
	if not args.no_entities:
		if os.path.exists(args.file):
			for name in parse_entity_names(args.file):
				roles += [(p + name, ROLE_BANK_ID) for p in RECORD_ROLE_PREFIXES]
		else:
			logger.warning(f"Entities file '{args.file}' not found — skipping record Roles")
	for r in args.role:
		role_name, _, bank_id = r.partition("@")
		roles.append((role_name, bank_id))
	return roles


def main():
	parser = argparse.ArgumentParser(description="Check DirectLogin and the current user's Roles.")
	parser.add_argument("file", nargs="?", default=DEFAULT_INPUT,
		help=f"Parsed entities file for the record Roles (default: {DEFAULT_INPUT})")
	parser.add_argument("--no-entities", action="store_true",
		help="Only check the entity definition Roles (and any --role)")
	parser.add_argument("--role", action="append", default=[], metavar="ROLE[@BANK_ID]",
		help="Extra Role to check; may be repeated")
	parser.add_argument("--list", action="store_true",
		help="Also print every entitlement the user holds")
	args = parser.parse_args()

	host = os.getenv('OBP_HOSTNAME', "http://obp-api-internal-route-obp.apps-crc.testing")
	missing_env = [k for k in ('OBP_USERNAME', 'OBP_PASSWORD', 'OBP_CONSUMER_KEY') if not os.getenv(k)]
	if missing_env:
		logger.error(f"✗ Not set in environment or .env: {', '.join(missing_env)}")
		return 1
	username = os.environ['OBP_USERNAME']

	logger.info(f"OBP_HOSTNAME: {host}")
	logger.info(f"OBP_USERNAME: {mask_credential(username)}")
	logger.info(f"OBP_CONSUMER_KEY: {mask_credential(os.environ['OBP_CONSUMER_KEY'])}")
	logger.info(f"OBP_ENTITY_SPACE_ID: {SPACE_ID or '(empty)'} -> entities at {describe()}, Roles at bank id {ROLE_BANK_ID}")

	# 1. Login
	token = direct_login(host, username, os.environ['OBP_PASSWORD'], os.environ['OBP_CONSUMER_KEY'])
	if not token:
		return 1
	logger.info("✓ DirectLogin OK")

	user = get_current_user(host, token)
	if user is None:
		return 1
	logger.info(f"✓ Logged in as {user.get('username')} (user_id {user.get('user_id')}, provider {user.get('provider')})")

	# 2. The space's bank must exist, or nothing can be created in it
	if SPACE_ID:
		url = f"{host}/obp/v6.0.0/banks/{SPACE_ID}"
		response = requests.get(url, headers={'Authorization': f"DirectLogin token={token}"}, timeout=30)
		if response.status_code != 200:
			logger.error(f"✗ Bank '{SPACE_ID}' (OBP_ENTITY_SPACE_ID) not found ({response.status_code}): {response.text}")
			return 3
		logger.info(f"✓ Bank '{SPACE_ID}' exists")

	# 3. Roles
	entitlements = user.get("entitlements", {}).get("list", [])
	held = {(e.get("role_name"), e.get("bank_id", "")) for e in entitlements}
	if args.list:
		logger.info(f"Entitlements held ({len(entitlements)}):")
		for role_name, bank_id in sorted(held):
			logger.info(f"  {role_name}" + (f" @ {bank_id}" if bank_id else ""))

	roles = required_roles(args)
	missing = [(r, b) for r, b in roles if (r, b) not in held]
	for role_name, bank_id in missing:
		logger.error(f"  ✗ missing {role_name}" + (f" @ {bank_id}" if bank_id else ""))
	logger.info(f"Roles: {len(roles) - len(missing)}/{len(roles)} present")
	if missing:
		logger.error(f"✗ {len(missing)} Role(s) missing — run create_entitlements.py or grant them manually")
		return 2
	logger.info("✓ All checked Roles present")
	return 0


if __name__ == "__main__":
	sys.exit(main())
