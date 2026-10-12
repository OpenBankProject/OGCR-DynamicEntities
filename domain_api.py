"""Manage the Domain API of the space (OBP_ENTITY_SPACE_ID): its entities and Dynamic
Resource Docs published under a base path of its own, e.g. /crcf/ogcr/v1/country
for /obp/v7.0.0/banks/ogcr/dynamic-entities/country. It only renames: every call runs
the same authentication, Roles and access checks as the OBP URL. See the
`Domain APIs` glossary entry on your OBP instance.

Usage:
    python3 domain_api.py list
    python3 domain_api.py create --title "..." [--base-path crcf/ogcr/v1] [--version 1.0.0] [--description ...]
    python3 domain_api.py update [--base-path crcf/ogcr/v1] [--version ...] [--title ...] [--description ...]
    python3 domain_api.py delete [--base-path crcf/ogcr/v1]

The base path is two to five segments ending with the major version as vN, and
`version` is MAJOR.MINOR.PATCH with MAJOR = N. A breaking change gets a new Domain API
with a new base path (v2) rather than an update. `create` does nothing if a Domain API
with the base path already exists; `update` sends only the options given.

Roles (at the space's bank id, or SYS): CanCreateDomainApi, CanGetDomainApis,
CanUpdateDomainApi, CanDeleteDomainApi.

Exits 0 on success, 1 otherwise.
"""

import argparse
import json
import sys

import requests

from obp_client import token, obp_host, session, authorization
from obp_space import ROLE_BANK_ID, SPACE_ID

DEFAULT_BASE_PATH = f"crcf/{SPACE_ID or 'sys'}/v1"


def domain_apis_url():
	return f"{obp_host}/obp/v7.0.0/management/banks/{ROLE_BANK_ID}/domain-apis"


def _check(response, what):
	if response.status_code not in (200, 201, 204):
		raise RuntimeError(f"{what} failed ({response.status_code}): {response.text}")
	return response


def list_domain_apis():
	response = _check(session.get(domain_apis_url(), headers={"Authorization": authorization(token)}, timeout=30),
		"Listing Domain APIs")
	return response.json().get("domain_apis", [])


def find(base_path):
	return next((d for d in list_domain_apis() if d.get("base_path") == base_path), None)


def show(domain_api):
	print(f"  {domain_api['base_path']}  version {domain_api.get('version')}  id {domain_api['domain_api_id']}")
	print(f"    url:     {domain_api.get('url')}")
	print(f"    openapi: {domain_api.get('openapi_url')}")


def cmd_list(_args):
	domain_apis = list_domain_apis()
	print(f"Domain APIs of bank '{ROLE_BANK_ID}': {len(domain_apis)}")
	for d in domain_apis:
		show(d)
	return 0


def cmd_create(args):
	existing = find(args.base_path)
	if existing:
		print(f"✓ Domain API '{args.base_path}' already exists")
		show(existing)
		return 0
	if not args.title:
		print("✗ create needs --title \"...\" (1 to 255 characters); --description is optional")
		return 1
	body = {"base_path": args.base_path, "version": args.version or "1.0.0",
		"title": args.title, "description": args.description or ""}
	response = _check(session.post(domain_apis_url(), json=body,
		headers={"Authorization": authorization(token)}, timeout=30), f"Creating Domain API '{args.base_path}'")
	print(f"✓ Created Domain API '{args.base_path}' over bank '{ROLE_BANK_ID}'")
	show(response.json())
	return 0


def cmd_update(args):
	existing = find(args.base_path)
	if not existing:
		print(f"✗ No Domain API '{args.base_path}' in bank '{ROLE_BANK_ID}'")
		return 1
	body = {key: existing.get(key) for key in ("base_path", "version", "title", "description")}
	for key in ("version", "title", "description"):
		if getattr(args, key) is not None:
			body[key] = getattr(args, key)
	response = _check(session.put(f"{domain_apis_url()}/{existing['domain_api_id']}", json=body,
		headers={"Authorization": authorization(token)}, timeout=30), f"Updating Domain API '{args.base_path}'")
	print(f"✓ Updated Domain API '{args.base_path}'")
	show(response.json())
	return 0


def cmd_delete(args):
	existing = find(args.base_path)
	if not existing:
		print(f"✓ No Domain API '{args.base_path}' in bank '{ROLE_BANK_ID}'; nothing to delete")
		return 0
	_check(session.delete(f"{domain_apis_url()}/{existing['domain_api_id']}",
		headers={"Authorization": authorization(token)}, timeout=30), f"Deleting Domain API '{args.base_path}'")
	print(f"✓ Deleted Domain API '{args.base_path}'")
	return 0


def main():
	parser = argparse.ArgumentParser(description="Manage the Domain API of the space.")
	parser.add_argument("command", choices=["list", "create", "update", "delete"])
	parser.add_argument("--base-path", default=DEFAULT_BASE_PATH, help=f"default: {DEFAULT_BASE_PATH}")
	parser.add_argument("--version", default=None, help="MAJOR.MINOR.PATCH (create default: 1.0.0)")
	parser.add_argument("--title", default=None)
	parser.add_argument("--description", default=None)
	args = parser.parse_args()

	if not token:
		print("✗ Login to OBP failed")
		return 1
	commands = {"list": cmd_list, "create": cmd_create, "update": cmd_update, "delete": cmd_delete}
	try:
		return commands[args.command](args)
	except (RuntimeError, requests.exceptions.RequestException, json.JSONDecodeError) as e:
		print(f"✗ {e}")
		return 1


if __name__ == "__main__":
	sys.exit(main())
