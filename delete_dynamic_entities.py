#!/usr/bin/env python3
"""Delete all system dynamic entities using the OBP management API.

This script calls the GET endpoint to list entities and then deletes each by ID.

It expects `obp_client.py` to define `token` and `obp_host` (as in the repository).
"""
import argparse
import json
import sys
import requests
from obp_client import token as DIRECTLOGIN_TOKEN, obp_host as BASE_URL

GET_URL = f"{BASE_URL}/obp/v5.1.0/management/system-dynamic-entities"
DELETE_URL_TEMPLATE = f"{BASE_URL}/obp/v5.1.0/management/system-dynamic-entities/{{}}"


def get_all_dynamic_entities(token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"DirectLogin token={token}"
    resp = requests.get(GET_URL, headers=headers)
    resp.raise_for_status()
    return resp.json()


def delete_dynamic_entity(entity_id, token=None):
    url = DELETE_URL_TEMPLATE.format(entity_id)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"DirectLogin token={token}"
    resp = requests.delete(url, headers=headers)
    resp.raise_for_status()
    return resp


def main():
    parser = argparse.ArgumentParser(description="Delete all system dynamic entities from OBP management API")
    parser.add_argument("--yes", action="store_true", help="Perform deletion without interactive confirmation")
    parser.add_argument("--dry-run", action="store_true", help="Only list entities that would be deleted")
    parser.add_argument("--token", default=DIRECTLOGIN_TOKEN, help="DirectLogin token (overrides obp_client.token)")
    args = parser.parse_args()

    try:
        data = get_all_dynamic_entities(args.token)
    except Exception as e:
        print(f"Failed to fetch dynamic entities: {e}")
        sys.exit(1)

    entities = data.get("dynamic_entities") or []
    if not entities:
        print("No dynamic entities found.")
        return

    print(f"Found {len(entities)} dynamic entities:")
    for e in entities:
        eid = e.get("dynamicEntityId")
        name = next((k for k in e.keys() if k not in ("dynamicEntityId", "userId", "hasPersonalEntity")), None)
        print(f" - {name or '<unknown>'}: {eid}")

    if args.dry_run:
        print("Dry run mode; no deletions performed.")
        return

    if not args.yes:
        confirm = input("Proceed to delete ALL listed entities? Type 'yes' to continue: ")
        if confirm.strip().lower() != "yes":
            print("Aborted by user.")
            return

    deleted = 0
    failed = 0
    for e in entities:
        eid = e.get("dynamicEntityId")
        try:
            delete_dynamic_entity(eid, args.token)
            print(f"Deleted: {eid}")
            deleted += 1
        except Exception as exc:
            print(f"Failed to delete {eid}: {exc}")
            failed += 1

    print(f"Done. Deleted: {deleted}. Failed: {failed}")


if __name__ == "__main__":
    main()

