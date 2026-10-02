"""Change fields of one dynamic entity record on OBP, leaving its other fields as they are.

For a one-off fix to stored data, e.g. an example record created with a wrong value:

    python3 patch_record.py activity a_05OFWI037022 country_id=DE

It reads the record in the space (OBP_ENTITY_SPACE_ID, see obp_space.py), shows each
field's current and new value, and changes nothing unless given --yes, which sends a
PATCH (v7.0.0) with only the named fields. A value that is valid JSON is sent as such
(6.5, true, null, {"a": 1}); anything else is sent as a string.

Usage:
    python3 patch_record.py ENTITY RECORD_ID FIELD=VALUE [FIELD=VALUE ...] [--yes]

Exits 0 on success (or when there is nothing to change), 1 if the record can't be read
or the PATCH is refused.
"""

import argparse
import json
import sys

from obp_client import obp_host, session, token
from obp_space import SPACE_ID, describe


def record_url(entity, record_id):
	bank_id = SPACE_ID or "SYS"
	return f"{obp_host}/obp/v7.0.0/banks/{bank_id}/dynamic-entities/{entity}/{record_id}"


def parse_value(text):
	try:
		return json.loads(text)
	except ValueError:
		return text


def main():
	parser = argparse.ArgumentParser(description="Change fields of one dynamic entity record on OBP.")
	parser.add_argument("entity", help="Entity name, e.g. activity")
	parser.add_argument("record_id", help="The record's id, e.g. a_05OFWI037022")
	parser.add_argument("changes", nargs="+", metavar="FIELD=VALUE", help="Fields to set")
	parser.add_argument("--yes", action="store_true", help="Send the PATCH (default: only show it)")
	args = parser.parse_args()

	changes = {}
	for change in args.changes:
		field, sep, value = change.partition("=")
		if not sep or not field:
			parser.error(f"{change!r} is not FIELD=VALUE")
		changes[field] = parse_value(value)

	headers = {"Authorization": f"DirectLogin token={token}", "Content-Type": "application/json"}
	url = record_url(args.entity, args.record_id)
	print(f"{args.entity} {args.record_id} at {obp_host}, {describe()}")
	response = session.get(url, headers=headers, timeout=60)
	if not response.ok:
		print(f"✗ Could not read the record: HTTP {response.status_code} {response.text[:300]}")
		return 1
	record = response.json().get(args.entity, response.json())

	todo = {field: value for field, value in changes.items() if record.get(field) != value}
	for field, value in changes.items():
		mark = "~" if field in todo else "="
		print(f"  {mark} {field}: {json.dumps(record.get(field))} -> {json.dumps(value)}")
	if not todo:
		print("Nothing to change.")
		return 0
	if not args.yes:
		print("Nothing was changed. Run with --yes to apply.")
		return 0

	response = session.patch(url, headers=headers, json=todo, timeout=60)
	if not response.ok:
		print(f"✗ PATCH refused: HTTP {response.status_code} {response.text[:300]}")
		return 1
	updated = response.json().get(args.entity, {})
	for field in todo:
		print(f"✓ {field} is now {json.dumps(updated.get(field))}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
