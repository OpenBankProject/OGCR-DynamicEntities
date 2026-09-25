"""DRY RUN of recreate_ogcr_entities.sh: say what it would do, without doing it.

Only reads (the spreadsheet, and GET requests to OBP); it creates, updates,
deletes and grants nothing, and does not rewrite entities_output.txt. It walks
the same steps as recreate_ogcr_entities.sh, in the same space
(OBP_ENTITY_SPACE_ID; see obp_space.py):

  0. check the spreadsheet and parse its entities
     ... create the space's bank, if it is missing
  1. delete the OGCR entities in the sheet that exist now (records + definition)
  2. create every entity in the sheet
  3. create the dummy data, the controlled vocabularies and the audit log entity
  and afterwards, what create_entitlements.sh would still need to grant.

Usage:
    python3 dry_run_create_ogcr_entities.py [path/to/min_field_matrix.xlsx]

Exits 0 when the dry run completed (whatever it found), 1 if OBP could not be read.
"""

import sys

import requests

from check_min_field_matrix import check as check_sheet
from create_space_bank import get_bank
from fixtures import fixture_records
from get_and_delete_dynamic_entities import get_all_system_dynamic_entities
from obp_client import token, obp_host
from obp_space import ROLE_BANK_ID, SPACE_ID, describe
from ogcr_log_entity import LOG_ENTITY_NAME
from parse_minimum_fields import parse_xlsx_entities

DEFAULT_SPREADSHEET = "min_field_matrix.xlsx"
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


def say(message=""):
	print(f"[DRY RUN] {message}" if message else "")


def heading(title):
	say()
	say("=" * 70)
	say(title)
	say("=" * 70)


def main():
	spreadsheet = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SPREADSHEET
	if not token:
		say("✗ DirectLogin failed; cannot read OBP")
		return 1
	user = requests.get(f"{obp_host}/obp/v6.0.0/users/current",
		headers={"Authorization": f"DirectLogin token={token}"}, timeout=30).json()

	heading("Nothing below is carried out. This only reports what would happen.")
	say(f"Host:     {obp_host}")
	say(f"User:     {user.get('username')} ({user.get('user_id')})")
	say(f"Entities: {describe()}  (OBP_ENTITY_SPACE_ID={SPACE_ID or '(empty)'}), Roles at bank id {ROLE_BANK_ID}")

	# --- STEP 0: the spreadsheet ----------------------------------------------------------
	heading(f"STEP 0: Spreadsheet {spreadsheet}")
	errors, warnings, _ = check_sheet(spreadsheet)
	if errors:
		say(f"! {len(errors)} error(s) in the sheet (run ./check_min_field_matrix.sh for details):")
		for e in errors:
			say(f"    ✗ {e}")
	else:
		say("✓ No errors in the sheet")
	if warnings:
		say(f"  {len(warnings)} warning(s); see ./check_min_field_matrix.sh")
	entities = parse_xlsx_entities(spreadsheet)
	if not entities:
		say("✗ No entities parsed from the sheet; recreate would have nothing to create")
		return 0
	say(f"Would regenerate entities_output.txt with {len(entities)} entities")

	# --- the space's bank -----------------------------------------------------------------
	bank_exists = True
	if SPACE_ID:
		try:
			bank_exists = get_bank(SPACE_ID) is not None
		except Exception as e:
			say(f"✗ Could not check bank '{SPACE_ID}': {e}")
			return 1
		if bank_exists:
			say(f"Bank '{SPACE_ID}' exists: nothing to create")
		else:
			say(f"WOULD CREATE bank '{SPACE_ID}' (needs the Role CanCreateBank)")

	# What exists in the space now. A bank that does not exist yet holds nothing.
	existing = {}
	if bank_exists:
		try:
			for e in get_all_system_dynamic_entities(token=token)["dynamic_entities"]:
				existing[e.get("entity_name")] = e
		except Exception as e:
			say(f"✗ Could not list the dynamic entities at {describe()}: {e}")
			return 1

	# --- STEP 1: delete -------------------------------------------------------------------
	heading(f"STEP 1: Delete the OGCR entities at {describe()}")
	to_delete = [name for name in entities if name in existing]
	if to_delete:
		total_records = 0
		for name in to_delete:
			count = existing[name].get("record_count")
			total_records += count or 0
			records = f"{count} record(s)" if count is not None else "its records"
			say(f"WOULD DELETE {name}: {records} + definition")
		say(f"= {len(to_delete)} entities, {total_records} records")
	else:
		say("Nothing to delete: none of the sheet's entities exist there")
	others = sorted(n for n in existing if n not in entities and n != LOG_ENTITY_NAME)
	if others:
		say(f"Left untouched (not in the sheet): {', '.join(others)}")

	# --- STEP 2: create -------------------------------------------------------------------
	heading(f"STEP 2: Create the entities at {describe()}")
	for name, entity in entities.items():
		fields = entity.get("fields", {})
		optional = sum(1 for f in fields if f.endswith(" (optional)"))
		public = ", public read" if entity.get("public_access") else ""
		say(f"WOULD CREATE {name}: {len(fields)} fields ({len(fields) - optional} required){public}")
	say(f"= {len(entities)} entities")

	# --- STEP 3: dummy data ---------------------------------------------------------------
	heading("STEP 3: Create the example data")
	if LOG_ENTITY_NAME not in existing:
		say(f"WOULD CREATE the audit log entity {LOG_ENTITY_NAME}")
	objects = 0
	for name in entities:
		rows = len(fixture_records(name))
		if rows:
			say(f"WOULD CREATE {rows} {name} fixture rows")
			objects += rows
		else:
			objects += 1
	say(f"WOULD CREATE one example object for each of the other {len(entities) - sum(1 for n in entities if fixture_records(n))} entities")
	say(f"= about {objects} objects, each also logged to {LOG_ENTITY_NAME}")

	# --- Roles, for create_entitlements.sh ------------------------------------------------
	heading(f"Roles at bank id {ROLE_BANK_ID} (granted separately by ./create_entitlements.sh)")
	held = {(e.get("role_name"), e.get("bank_id", "")) for e in user.get("entitlements", {}).get("list", [])}
	missing_meta = [r for r in META_ROLE_NAMES if (r, ROLE_BANK_ID) not in held]
	if missing_meta:
		say(f"! Missing definition Roles, needed BEFORE step 1: {', '.join(missing_meta)}")
	else:
		say("✓ Definition Roles held")
	missing_record = [p + n for n in entities for p in RECORD_ROLE_PREFIXES if (p + n, ROLE_BANK_ID) not in held]
	if missing_record:
		say(f"Would still need {len(missing_record)} record Role(s) after step 2, for "
			f"{len({r.split('_', 1)[1] for r in missing_record})} entities")
	else:
		say("✓ All record Roles held")

	heading("DRY RUN complete. Nothing was changed. Run ./recreate_ogcr_entities.sh to do it.")
	return 0


if __name__ == "__main__":
	sys.exit(main())
