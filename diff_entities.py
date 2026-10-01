"""Show how the dynamic entities on OBP differ from the spreadsheet, at one bank id.

Each entity in the sheet is built exactly as parse_minimum_fields.py --create
would build it (build_entity_definition_from_parsed), and compared with the
definition on OBP in the space (OBP_ENTITY_SPACE_ID, see obp_space.py; --bank-id
for another, SYS for system level). Reported:
  - entities only in the sheet, or only on OBP;
  - fields only in the sheet, or only on OBP;
  - per field: type, required, indexed, and (unless --structure-only) the
    description and example;
  - per entity: hasPublicAccess, hasPersonalEntity, hasCommunityAccess, and
    (unless --structure-only) the description.

A reference:X field whose entity X is not on OBP is expected as a string, as
the create step makes it. The audit log entity (dummy_data_creation_log_helpers.py) is not in the
sheet and is left out. Read-only: one GET.

Usage:
    python3 diff_entities.py [path/to/min_field_matrix.xlsx] [--bank-id BANK_ID] [--structure-only]

Exits 0 when they match, 1 when they differ, 2 if the sheet or OBP could not be read.
"""

import argparse
import json
import os
import sys

from obp_client import obp_host, session, token
from obp_dynamic_api import BUILTIN_REFERENCE_TYPES, build_entity_definition_from_parsed
from obp_space import SPACE_ID
from dummy_data_creation_log_helpers import LOG_ENTITY_NAME
from parse_minimum_fields import parse_xlsx_entities

DEFAULT_SPREADSHEET = "min_field_matrix.xlsx"
SYSTEM_BANK_IDS = ("SYS", "")

# Entity level flags: sheet definition key -> OBP response key.
FLAGS = {
	"hasPublicAccess": "has_public_access",
	"hasPersonalEntity": "has_personal_entity",
	"hasCommunityAccess": "has_community_access",
}


def env_bool(name):
	return os.getenv(name, "false").strip().lower() in ("1", "true", "yes", "y", "on")


def get_entities_on_obp(bank_id):
	"""{entity_name: entity} of the dynamic entity definitions at bank_id."""
	if bank_id in SYSTEM_BANK_IDS:
		url = f"{obp_host}/obp/v6.0.0/management/system-dynamic-entities"
	else:
		url = f"{obp_host}/obp/v6.0.0/management/banks/{bank_id}/dynamic-entities"
	response = session.get(url, headers={"Authorization": f"DirectLogin token={token}"}, timeout=60)
	if not response.ok:
		raise RuntimeError(f"{response.status_code} {response.text}")
	return {e["entity_name"]: e for e in response.json().get("dynamic_entities", [])}


def show(value):
	text = json.dumps(value, ensure_ascii=False)
	return text if len(text) <= 80 else text[:77] + "..."


def diff_entity(name, expected, actual, structure_only):
	"""The differences between one entity built from the sheet and the one on OBP, as lines."""
	lines = []
	for sheet_key, obp_key in FLAGS.items():
		want, have = bool(expected.get(sheet_key)), bool(actual.get(obp_key))
		if want != have:
			lines.append(f"  {sheet_key}: sheet {want}, OBP {have}")

	want_schema = expected[name]
	have_schema = actual.get("schema") or {}
	if not structure_only and want_schema["description"] != have_schema.get("description"):
		lines.append(f"  description: sheet {show(want_schema['description'])}")
		lines.append(f"               OBP   {show(have_schema.get('description'))}")

	want_props = want_schema["properties"]
	have_props = have_schema.get("properties") or {}
	want_required = set(want_schema["required"])
	have_required = set(have_schema.get("required") or [])

	for field in want_props:
		if field not in have_props:
			lines.append(f"  + {field} ({want_props[field]['type']}): in the sheet, not on OBP")
	for field in have_props:
		if field not in want_props:
			lines.append(f"  - {field} ({have_props[field].get('type')}): on OBP, not in the sheet")

	checks = ["type", "indexed"] + ([] if structure_only else ["description", "example"])
	for field, want in want_props.items():
		have = have_props.get(field)
		if have is None:
			continue
		changes = []
		for key in checks:
			w, h = want.get(key), have.get(key)
			if key == "indexed":
				w, h = bool(w), bool(h)
			if w != h:
				changes.append(f"{key}: sheet {show(w)}, OBP {show(h)}")
		if (field in want_required) != (field in have_required):
			changes.append(f"required: sheet {field in want_required}, OBP {field in have_required}")
		if changes:
			lines.append(f"  ~ {field}")
			lines.extend(f"      {c}" for c in changes)
	return lines


def main():
	parser = argparse.ArgumentParser(description="Show how the dynamic entities on OBP differ from the spreadsheet.")
	parser.add_argument("file", nargs="?", default=DEFAULT_SPREADSHEET,
		help=f"Path to the xlsx file (default: {DEFAULT_SPREADSHEET})")
	parser.add_argument("--bank-id", default=SPACE_ID or "SYS",
		help=f"Bank id of the entities on OBP (default: {SPACE_ID or 'SYS'}, the space; SYS for system level)")
	parser.add_argument("--structure-only", action="store_true",
		help="Compare fields, types, required, indexed and flags only; not descriptions or examples")
	args = parser.parse_args()

	sheet = parse_xlsx_entities(args.file)
	if not sheet:
		print(f"✗ No entities read from {args.file}")
		return 2
	if not token:
		print("✗ DirectLogin failed")
		return 2
	try:
		on_obp = get_entities_on_obp(args.bank_id)
	except Exception as e:
		print(f"✗ Could not list the dynamic entities at bank id {args.bank_id}: {e}")
		return 2

	has_personal = env_bool("HAS_PERSONAL_ENTITY")
	has_community = env_bool("HAS_COMMUNITY_ACCESS")
	allowed_refs = {f"reference:{n}" for n in on_obp} | BUILTIN_REFERENCE_TYPES

	print(f"{args.file}: {len(sheet)} entities; {obp_host} bank id {args.bank_id}: {len(on_obp)} entities")
	differ = 0
	matching = 0
	for name, wrapper in sheet.items():
		if name not in on_obp:
			continue
		expected = build_entity_definition_from_parsed(
			name, wrapper["fields"], has_personal=has_personal, has_community=has_community,
			has_public=wrapper.get("public_access", False), entity_description=wrapper.get("description"),
			allowed_reference_types=allowed_refs)
		lines = diff_entity(name, expected, on_obp[name], args.structure_only)
		if lines:
			differ += 1
			print(f"\n~ {name}")
			print("\n".join(lines))
		else:
			matching += 1

	only_sheet = [n for n in sheet if n not in on_obp]
	only_obp = sorted(n for n in on_obp if n not in sheet and n != LOG_ENTITY_NAME)
	if only_sheet:
		print(f"\n+ In the sheet, not on OBP ({len(only_sheet)}): {', '.join(only_sheet)}")
	if only_obp:
		print(f"\n- On OBP, not in the sheet ({len(only_obp)}): {', '.join(only_obp)}")

	print(f"\n{matching} matching, {differ} differing, {len(only_sheet)} only in the sheet, {len(only_obp)} only on OBP")
	return 1 if differ or only_sheet or only_obp else 0


if __name__ == "__main__":
	sys.exit(main())
