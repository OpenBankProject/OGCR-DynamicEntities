"""Bring the dynamic entity definitions on OBP up to date with the spreadsheet, in place.

recreate_dynamic_entities.sh deletes every entity and creates it again. Deleting an
entity makes OBP delete its users' record Role grants too, so the groups grant them
again and every user gets an email per Role. This script changes the definitions
where they are instead, so the grants, and the records, stay.

It compares each entity in the sheet with the one in the space (OBP_ENTITY_SPACE_ID,
see obp_space.py), the same way diff_entities.py does, and sorts it:

  create     only in the sheet: created (new grants only, for new Roles)
  update     differs, and OBP can change it in place: updated
  recreate   a structural change to an entity that has records: left alone
  unchanged  matches the sheet

OBP's rule for an entity that has records (isSchemaCompatibleChange): every existing
field keeps its name and type, and no field becomes required. New optional fields may
be added (the stored records just don't have them); descriptions, examples, indexed,
lengths and the access flags may change freely, and a field may stop being required.
An entity with no records takes any change. So a field removed or retyped, or a field
(new or existing) made required, on an entity with records is "recreate": the message
says so, and what to do instead. An OBP older than this rule refuses new fields too,
with OBP-09023, which is reported as a failed update. Entities on OBP that the sheet no longer has are listed and left
alone.

Without --yes nothing is changed: it only reports what it would do.

Usage:
    python3 update_dynamic_entities.py [path/to/min_field_matrix.xlsx] [--yes]

Exits 0 when the space matches the sheet (or will once --yes is applied), 1 when an
entity needs a recreate, is only on OBP, or a change failed, 2 if the sheet or OBP
could not be read.
"""

import argparse
import sys

from diff_entities import diff_entity, env_bool, get_entities_on_obp
from example_data_creation_log_helpers import LOG_ENTITY_NAME
from obp_client import obp_host, token
from obp_dynamic_api import (
	BUILTIN_REFERENCE_TYPES,
	build_entity_definition_from_parsed,
	create_dynamic_entity_from_parsed,
	update_system_dynamic_entity,
)
from obp_space import SPACE_ID, describe
from parse_minimum_fields import parse_xlsx_entities

DEFAULT_SPREADSHEET = "min_field_matrix.xlsx"


def structural_changes(name, expected, actual):
	"""Why OBP would refuse this update on an entity with records, as lines (empty: it would accept it).
	Mirrors OBP's DynamicEntityHelper.isSchemaCompatibleChange: a new field is fine unless it is
	required, which the newly-required check reports."""
	want = expected[name]
	have = actual.get("schema") or {}
	want_types = {field: prop["type"] for field, prop in want["properties"].items()}
	have_types = {field: prop.get("type", "") for field, prop in (have.get("properties") or {}).items()}
	reasons = []
	for field in sorted(set(have_types) - set(want_types)):
		reasons.append(f"field {field} removed")
	for field in sorted(f for f in want_types if f in have_types and want_types[f] != have_types[f]):
		reasons.append(f"field {field} type {have_types[field]} -> {want_types[field]}")
	for field in sorted(set(want["required"]) - set(have.get("required") or [])):
		reasons.append(f"field {field} newly required")
	return reasons


def main():
	parser = argparse.ArgumentParser(description="Update the dynamic entity definitions on OBP from the spreadsheet, in place.")
	parser.add_argument("file", nargs="?", default=DEFAULT_SPREADSHEET,
		help=f"Path to the xlsx file (default: {DEFAULT_SPREADSHEET})")
	parser.add_argument("--yes", action="store_true", help="Apply the creates and updates (default: report only)")
	args = parser.parse_args()

	sheet = parse_xlsx_entities(args.file)
	if not sheet:
		print(f"✗ No entities read from {args.file}")
		return 2
	if not token:
		print("✗ DirectLogin failed")
		return 2
	bank_id = SPACE_ID or "SYS"
	try:
		on_obp = get_entities_on_obp(bank_id)
	except Exception as e:
		print(f"✗ Could not list the dynamic entities at {describe()}: {e}")
		return 2

	has_personal = env_bool("HAS_PERSONAL_ENTITY")
	has_community = env_bool("HAS_COMMUNITY_ACCESS")
	# References may name an entity on OBP or one this run creates.
	allowed_refs = {f"reference:{n}" for n in set(on_obp) | set(sheet)} | BUILTIN_REFERENCE_TYPES

	def build(name, refs=allowed_refs, downgrade=False):
		wrapper = sheet[name]
		return build_entity_definition_from_parsed(
			name, wrapper["fields"], has_personal=has_personal, has_community=has_community,
			has_public=wrapper.get("public_access", False), entity_description=wrapper.get("description"),
			allowed_reference_types=refs, downgrade_references=downgrade)

	to_create, to_update, to_recreate, unchanged = [], [], [], []
	print(f"{args.file} -> {obp_host}, {describe()}")
	for name in sheet:
		if name not in on_obp:
			to_create.append(name)
			continue
		lines = diff_entity(name, build(name), on_obp[name], structure_only=False)
		if not lines:
			unchanged.append(name)
			continue
		records = on_obp[name].get("record_count") or 0
		reasons = structural_changes(name, build(name), on_obp[name])
		if reasons and records:
			to_recreate.append((name, records, reasons))
		else:
			to_update.append(name)
			print(f"\n~ update {name}" + (f" ({records} record(s) kept)" if records else ""))
			print("\n".join(lines))
	only_obp = sorted(n for n in on_obp if n not in sheet and n != LOG_ENTITY_NAME)

	for name in to_create:
		print(f"\n+ create {name}")
	for name, records, reasons in to_recreate:
		print(f"\n✗ {name}: can't be changed in place, it has {records} record(s) and the sheet changes its structure:")
		for reason in reasons:
			print(f"      {reason}")
		print("  Either recreate everything with ./recreate_dynamic_entities.sh (this entity's records are lost,")
		print("  and every user's record Role grants are deleted and granted again, with emails), or, to keep")
		print("  the records, put the new definition in a new space: a new OBP_ENTITY_SPACE_ID bank.")
	if only_obp:
		print(f"\n- On OBP, not in the sheet, left alone ({len(only_obp)}): {', '.join(only_obp)}")
		print("  Deleting one deletes its records and its users' record Role grants.")

	print(f"\n{len(unchanged)} unchanged, {len(to_update)} to update, {len(to_create)} to create, "
		f"{len(to_recreate)} needing a recreate, {len(only_obp)} only on OBP")

	failed = 0
	updated = []
	if not args.yes:
		if to_create or to_update:
			print("Nothing was changed. Run with --yes to apply the creates and updates.")
	elif not (to_create or to_update):
		print("\nNothing to apply: every entity that can be changed in place already matches the sheet.")
	else:
		print(f"\nApplying to {obp_host}, {describe()}:")
		# New entities first, references to other new entities as strings, so no create waits on
		# another; then every update, which now has all its reference targets.
		created = set()
		for name in to_create:
			wrapper = sheet[name]
			try:
				create_dynamic_entity_from_parsed(
					name, wrapper["fields"], token=token, base_url=obp_host, has_personal=has_personal,
					has_community=has_community, has_public=wrapper.get("public_access", False),
					entity_description=wrapper.get("description"), downgrade_references=True)
				created.add(name)
				print(f"✓ created {name}")
			except Exception as e:
				failed += 1
				print(f"✗ create {name} failed: {e}")
		on_obp = get_entities_on_obp(bank_id)
		for name in to_update + sorted(created):
			if name not in on_obp:
				continue
			# A new entity is updated only to restore references it was created without.
			if name in created and not structural_changes(name, build(name), on_obp[name]):
				continue
			try:
				update_system_dynamic_entity(on_obp[name]["dynamic_entity_id"], build(name), token=token, base_url=obp_host)
				updated.append(name)
				print(f"✓ updated {name}")
			except Exception as e:
				failed += 1
				print(f"✗ update {name} failed: {e}")
		print("\n" + "=" * 50)
		print(f" Done: {len(created)} created, {len(updated)} updated, {failed} failed")
		print("=" * 50)
		if created:
			print(f"  Created: {', '.join(sorted(created))}")
		if updated:
			print(f"  Updated: {', '.join(updated)}")
		if updated or created:
			print("  OBP builds any new indexes in the background.")
		if created:
			print("  New entities have new Roles: run ./create_role_groups.sh to give the groups theirs.")
	if to_recreate or only_obp:
		print(f"Still needing attention (see above): {len(to_recreate)} needing a recreate, {len(only_obp)} only on OBP.")

	return 1 if to_recreate or only_obp or failed else 0


if __name__ == "__main__":
	sys.exit(main())
