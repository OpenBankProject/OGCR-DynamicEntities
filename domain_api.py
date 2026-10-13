"""Manage the Domain API of the space (OBP_ENTITY_SPACE_ID): its entities and Dynamic
Resource Docs published under a base path of its own, e.g. /crcf/ogcr/v1/country
for /obp/v7.0.0/banks/ogcr/dynamic-entities/country. It only renames: every call runs
the same authentication, Roles and access checks as the OBP URL. See the
`Domain APIs` glossary entry on your OBP instance.

Usage:
    python3 domain_api.py list
    python3 domain_api.py create --title "..." [--base-path crcf/ogcr/v1] [--version 1.0.0] [--description ...] [--publicly-discoverable true|false]
    python3 domain_api.py update [--base-path crcf/ogcr/v1] [--version ...] [--title ...] [--description ...] [--publicly-discoverable true|false]
    python3 domain_api.py delete [--base-path crcf/ogcr/v1]
    python3 domain_api.py verify [--base-path crcf/ogcr/v1]

The base path is two to five segments ending with the major version as vN, and
`version` is MAJOR.MINOR.PATCH with MAJOR = N. A breaking change gets a new Domain API
with a new base path (v2) rather than an update. `create` does nothing if a Domain API
with the base path already exists; `update` sends only the options given.

--publicly-discoverable true lists the Domain API, without login, at
/obp/v7.0.0/banks/<bank id>/domain-apis (where OGCR-App's /domain-api page reads it). OBP
defaults it to false on create and keeps it when `update` leaves it out.

`create`, `update` and `verify` then check the base path is served: its OpenAPI
document (<host>/<base path>/openapi.json) must answer 200 without login, retried for
up to --wait seconds (default 15; OBP's other nodes see a change within 10). `delete`
checks it no longer is.

Roles (at the space's bank id, or SYS): CanCreateDomainApi, CanGetDomainApis,
CanUpdateDomainApi, CanDeleteDomainApi.

Exits 0 on success, 1 otherwise.
"""

import argparse
import json
import sys
import time

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


def served(base_path, wait):
	"""The status of the base path's OpenAPI document, called without login, retried up to
	`wait` seconds until it answers 200."""
	url = f"{obp_host}/{base_path}/openapi.json"
	deadline = time.time() + wait
	while True:
		status = session.get(url, timeout=30).status_code
		if status == 200 or time.time() >= deadline:
			return url, status
		time.sleep(2)


def check_served(base_path, wait):
	url, status = served(base_path, wait)
	if status == 200:
		print(f"✓ Served: {url}")
		return 0
	print(f"✗ Not served: {url} answered {status}")
	return 1


def show(domain_api):
	print(f"  {domain_api['base_path']}  version {domain_api.get('version')}  id {domain_api['domain_api_id']}")
	print(f"    url:     {domain_api.get('url')}")
	print(f"    openapi: {domain_api.get('openapi_url')}")
	print(f"    publicly discoverable: {domain_api.get('is_publicly_discoverable')}")


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
		return check_served(args.base_path, args.wait)
	if not args.title:
		print("✗ create needs --title \"...\" (1 to 255 characters); --description is optional")
		return 1
	body = {"base_path": args.base_path, "version": args.version or "1.0.0",
		"title": args.title, "description": args.description or ""}
	if args.publicly_discoverable is not None:
		body["is_publicly_discoverable"] = args.publicly_discoverable
	response = _check(session.post(domain_apis_url(), json=body,
		headers={"Authorization": authorization(token)}, timeout=30), f"Creating Domain API '{args.base_path}'")
	print(f"✓ Created Domain API '{args.base_path}' over bank '{ROLE_BANK_ID}'")
	show(response.json())
	return check_served(args.base_path, args.wait)


def cmd_update(args):
	existing = find(args.base_path)
	if not existing:
		print(f"✗ No Domain API '{args.base_path}' in bank '{ROLE_BANK_ID}'")
		return 1
	body = {key: existing.get(key) for key in ("base_path", "version", "title", "description")}
	for key in ("version", "title", "description"):
		if getattr(args, key) is not None:
			body[key] = getattr(args, key)
	# Left out, OBP keeps the current value.
	if args.publicly_discoverable is not None:
		body["is_publicly_discoverable"] = args.publicly_discoverable
	response = _check(session.put(f"{domain_apis_url()}/{existing['domain_api_id']}", json=body,
		headers={"Authorization": authorization(token)}, timeout=30), f"Updating Domain API '{args.base_path}'")
	print(f"✓ Updated Domain API '{args.base_path}'")
	show(response.json())
	return check_served(args.base_path, args.wait)


def cmd_delete(args):
	existing = find(args.base_path)
	if not existing:
		print(f"✓ No Domain API '{args.base_path}' in bank '{ROLE_BANK_ID}'; nothing to delete")
		return 0
	_check(session.delete(f"{domain_apis_url()}/{existing['domain_api_id']}",
		headers={"Authorization": authorization(token)}, timeout=30), f"Deleting Domain API '{args.base_path}'")
	print(f"✓ Deleted Domain API '{args.base_path}'")
	# Wait for it to stop answering 200 (other nodes see the delete within 10 seconds).
	url = f"{obp_host}/{args.base_path}/openapi.json"
	deadline = time.time() + args.wait
	while (status := session.get(url, timeout=30).status_code) == 200 and time.time() < deadline:
		time.sleep(2)
	if status == 200:
		print(f"✗ Still served: {url} answered 200")
		return 1
	print(f"✓ No longer served: {url} answered {status}")
	return 0


def cmd_verify(args):
	existing = find(args.base_path)
	if not existing:
		print(f"✗ No Domain API '{args.base_path}' in bank '{ROLE_BANK_ID}'")
		return 1
	show(existing)
	return check_served(args.base_path, args.wait)


def main():
	parser = argparse.ArgumentParser(description="Manage the Domain API of the space.")
	parser.add_argument("command", choices=["list", "create", "update", "delete", "verify"])
	parser.add_argument("--base-path", default=DEFAULT_BASE_PATH, help=f"default: {DEFAULT_BASE_PATH}")
	parser.add_argument("--version", default=None, help="MAJOR.MINOR.PATCH (create default: 1.0.0)")
	parser.add_argument("--title", default=None)
	parser.add_argument("--description", default=None)
	parser.add_argument("--publicly-discoverable", default=None, choices=[True, False],
		type=lambda value: {"true": True, "false": False}.get(value.lower(), value), metavar="true|false",
		help="list it publicly at /obp/v7.0.0/banks/<bank id>/domain-apis")
	parser.add_argument("--wait", type=int, default=15, metavar="SECONDS",
		help="how long to retry the served check (default %(default)s)")
	args = parser.parse_args()

	if not token:
		print("✗ Login to OBP failed")
		return 1
	commands = {"list": cmd_list, "create": cmd_create, "update": cmd_update, "delete": cmd_delete,
		"verify": cmd_verify}
	try:
		return commands[args.command](args)
	except (RuntimeError, requests.exceptions.RequestException, json.JSONDecodeError) as e:
		print(f"✗ {e}")
		return 1


if __name__ == "__main__":
	sys.exit(main())
