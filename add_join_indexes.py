#!/usr/bin/env python3
"""
add_join_indexes.py — declare "indexed": true on existing OGCR dynamic entities.

OBP Dynamic Entity join queries (?obp_exists[child]=... / ?obp_not_exists[child]=...)
only work when the reference field forming the edge is declared "indexed": true
(and the nested filter field, and at least one field on the parent). Entities
created before that policy existed (see should_index_field in obp_dynamic_api.py)
carry no index flags, so e.g.

  GET /obp/dynamic-entity/activity?obp_exists[activity_verification]=filter[status_code]=eq:verified

fails with HTTP 400. This script fetches the live definitions, applies the same
policy, shows what would change and — with --apply — PUTs the updated
definitions back. OBP then provisions the index projection in the background.

Usage:
  python3 add_join_indexes.py                      # dry run: activity + activity_verification
  python3 add_join_indexes.py --apply              # write the changes
  python3 add_join_indexes.py --entities a b --apply
  python3 add_join_indexes.py --verify             # run the join query and print the status

Token/host come from obp_client.py (.env), like the other scripts.
"""
import argparse
import copy
import json
import sys

import requests

from obp_client import token as TOKEN, obp_host as HOST
from obp_dynamic_api import (
    list_system_dynamic_entities,
    should_index_field,
    update_system_dynamic_entity,
)

DEFAULT_ENTITIES = ["activity", "activity_verification"]
NON_ENTITY_KEYS = {
    "dynamicEntityId", "userId", "hasPersonalEntity", "hasPublicAccess",
    "hasCommunityAccess", "personalRequiresRole", "useRowLevelAccess", "authMode",
}


def find_entity(listing, name):
    for e in listing.get("dynamic_entities", []):
        if name in e and name not in NON_ENTITY_KEYS:
            return e
    return None


def plan_changes(name, entry):
    """Return (new_entry, [field names newly indexed])."""
    new_entry = copy.deepcopy(entry)
    props = new_entry[name].get("properties", {})
    changed = []
    for field, prop_def in props.items():
        if prop_def.get("indexed") is True:
            continue
        if should_index_field(name, field, prop_def.get("type", "string")):
            prop_def["indexed"] = True
            changed.append(field)
    return new_entry, changed


def put_body(entry):
    body = {k: v for k, v in entry.items() if k not in ("dynamicEntityId", "userId")}
    return body


def verify(base_url, token):
    url = (
        f"{base_url}/obp/dynamic-entity/activity"
        "?obp_exists[activity_verification]=filter[status_code]=eq:verified"
    )
    headers = {"Authorization": f"DirectLogin token={token}"}
    resp = requests.get(url, headers=headers)
    print(f"GET {url}\n-> HTTP {resp.status_code}")
    try:
        body = resp.json()
    except ValueError:
        print(resp.text[:500])
        return resp.ok
    if resp.ok:
        rows = body.get("activity_list", [])
        print(f"   {len(rows)} verified activities returned by the server-side join")
    else:
        print("   " + json.dumps(body, indent=2))
    return resp.ok


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--entities", nargs="+", default=DEFAULT_ENTITIES, help="entity names to update")
    parser.add_argument("--apply", action="store_true", help="PUT the updated definitions (default: dry run)")
    parser.add_argument("--verify", action="store_true", help="run the activity/activity_verification join query")
    args = parser.parse_args()

    if args.verify and not args.apply:
        sys.exit(0 if verify(HOST, TOKEN) else 1)

    listing = list_system_dynamic_entities(token=TOKEN, base_url=HOST)
    any_change = False
    for name in args.entities:
        entry = find_entity(listing, name)
        if not entry:
            print(f"[{name}] not found on {HOST}, skipping")
            continue
        new_entry, changed = plan_changes(name, entry)
        if not changed:
            print(f"[{name}] already up to date")
            continue
        any_change = True
        print(f"[{name}] would set \"indexed\": true on: {', '.join(changed)}")
        if args.apply:
            resp = update_system_dynamic_entity(entry["dynamicEntityId"], put_body(new_entry), token=TOKEN, base_url=HOST)
            print(f"[{name}] updated ({resp.get('dynamicEntityId', entry['dynamicEntityId'])})")

    if not args.apply and any_change:
        print("\nDry run only. Re-run with --apply to write these changes.")
    if args.apply and args.verify:
        verify(HOST, TOKEN)


if __name__ == "__main__":
    main()
