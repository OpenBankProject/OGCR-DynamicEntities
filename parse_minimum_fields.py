#!/usr/bin/env python3
"""
Script to parse xlsx file and extract entity dictionaries.
Reads column A until 'END_OF_FILE', creates dictionaries for each entity
with column A as keys and column D as values.
"""

import pandas as pd
import sys
from pathlib import Path
from obp_dynamic_api import create_dynamic_entity_from_parsed
import argparse
import os
import datetime


def _has_green_checkmark(cell_value):
	"""
	Check if a cell contains a green checkmark.

	Args:
		cell_value (str): The cell value to check

	Returns:
		bool: True if cell contains a green checkmark
	"""
	if not cell_value:
		return False

	# Common representations of green checkmarks
	checkmarks = ['✓', '✔', '✅', '☑', '√', 'YES', 'Y', 'TRUE', '1']
	cell_upper = cell_value.upper().strip()

	return any(mark in cell_upper for mark in checkmarks)


def parse_xlsx_entities(file_path):
	"""
	Parse xlsx file to extract entity dictionaries.

	Args:
		file_path (str): Path to the xlsx file

	Returns:
		dict: Dictionary containing all entity dictionaries
	"""
	try:
		# Read the xlsx file
		df = pd.read_excel(file_path, engine='openpyxl')

		# Initialize variables
		entities = {}
		current_entity = None
		current_dict = {}

		# Iterate through rows
		for index, row in df.iterrows():
			# Get values from columns A, B, C, and D (0-indexed: A=0, B=1, C=2, D=3)
			col_a_value = row.iloc[0] if pd.notna(row.iloc[0]) else ""
			col_b_value = row.iloc[1] if len(row) > 1 and pd.notna(row.iloc[1]) else ""
			col_c_value = row.iloc[2] if len(row) > 2 and pd.notna(row.iloc[2]) else ""
			col_d_value = row.iloc[3] if len(row) > 3 and pd.notna(row.iloc[3]) else ""
			# Column F (index 5) holds descriptions; Column G (index 6) holds examples
			col_f_value = row.iloc[5] if len(row) > 5 and pd.notna(row.iloc[5]) else ""
			col_g_value = row.iloc[6] if len(row) > 6 and pd.notna(row.iloc[6]) else ""
			# Column K (index 10) holds "Field Is Indexed" — required for a field to be
			# usable in OBP's ?obp_exists[Entity]/?obp_not_exists[Entity]/filter[...] queries.
			col_k_value = row.iloc[10] if len(row) > 10 and pd.notna(row.iloc[10]) else ""

			# Convert to string for processing (handle Excel dates safely)
			col_a_str = str(col_a_value).strip()
			col_b_str = str(col_b_value).strip()
			col_c_str = str(col_c_value).strip()
			col_d_str = str(col_d_value).strip()
			col_f_str = str(col_f_value).strip()
			is_indexed = _has_green_checkmark(str(col_k_value).strip())
			# If pandas read a datetime/timestamp, format as YYYY-MM-DD to match DATE_WITH_DAY
			if col_g_value == "" or pd.isna(col_g_value):
				col_g_str = ""
			else:
				if isinstance(col_g_value, (pd.Timestamp, datetime.datetime, datetime.date)):
					try:
						col_g_str = col_g_value.strftime("%Y-%m-%d")
					except Exception:
						col_g_str = str(col_g_value).strip()
				else:
					col_g_str = str(col_g_value).strip()

			# Clean example string: remove surrounding double or single quotes if present
			cleaned_example = col_g_str
			if len(cleaned_example) >= 2:
				if (cleaned_example.startswith('"') and cleaned_example.endswith('"')) or (
					cleaned_example.startswith("'") and cleaned_example.endswith("'")
				):
					cleaned_example = cleaned_example[1:-1].strip()

			# Check for stop marker
			if col_a_str == "END_OF_FILE":
				# Save current entity if exists
				if current_entity and current_dict:
					entities[current_entity] = current_dict
				break

			# Check if this row starts a new entity
			if col_a_str.lower().startswith("entity:"):
				# Save previous entity if exists
				if current_entity and current_dict:
					entities[current_entity] = {"description": current_entity_description, "fields": current_dict}

				# Start new entity
				entity_name = col_a_str[7:].strip()  # Remove "entity:" prefix
				current_entity = entity_name
				current_dict = {}
				# capture entity-level description from column F when present
				current_entity_description = col_f_str if col_f_str else f"Parsed entity {entity_name}"

			elif current_entity:
				# Add to current entity dictionary if we have a valid key
				if col_a_str and col_a_str != "nan":
					# sanitize field name: replace dots with underscore to satisfy allowed chars
					# sanitize field name: only allow A-Z a-z 0-9 underscore and hyphen
					# replace any other character with underscore, collapse repeated underscores
					import re
					safe_key_raw = col_a_str.replace('.', '_')
					safe_key = re.sub(r'[^A-Za-z0-9_\-]', '_', safe_key_raw)
					# collapse multiple underscores
					safe_key = re.sub(r'_+', '_', safe_key).strip('_')
					# Check for green check marks in columns B and C
					has_green_check_b = _has_green_checkmark(col_b_str)
					has_green_check_c = _has_green_checkmark(col_c_str)

					if has_green_check_b:
						# Column B has green check - add normally; preserve column D as value
						# and attach column G as explicit example when available
						entry = {"value": col_d_str, "indexed": is_indexed}
						if cleaned_example:
							entry["example"] = cleaned_example
						if col_f_str:
							entry["description"] = col_f_str
						current_dict[safe_key] = entry
					elif has_green_check_c:
						# Column C has green check but not B - mark as optional
						opt_key = f"{safe_key} (optional)"
						entry = {"value": col_d_str, "indexed": is_indexed}
						if cleaned_example:
							entry["example"] = cleaned_example
						if col_f_str:
							entry["description"] = col_f_str
						current_dict[opt_key] = entry
				# If neither B nor C has green check, skip this row

		# Save the last entity if exists
		if current_entity and current_dict:
			entities[current_entity] = {"description": current_entity_description, "fields": current_dict}

		return entities

	except FileNotFoundError:
		print(f"Error: File '{file_path}' not found.")
		return {}
	except Exception as e:
		print(f"Error reading file: {e}")
		return {}


def _has_reference_field(fields):
	"""True if any field declares a reference:<name> type."""
	if not isinstance(fields, dict):
		return False
	for v in fields.values():
		if isinstance(v, dict) and isinstance(v.get("value"), str) and v["value"].strip().startswith("reference:"):
			return True
	return False


def _create_entities_two_pass(entities, token=None, host=None, has_personal=False, has_community=False):
	"""Create dynamic entities in two passes so references between them always
	resolve, even when the spreadsheet order has forward references or cycles.

	Pass 1: create every entity with reference fields downgraded to plain
	        strings, so no create depends on another entity existing yet.
	Pass 2: PUT-update each entity that declares references, restoring the real
	        reference:<name> types now that every target entity exists on OBP.
	        References whose target still does not exist stay as strings.
	"""
	from obp_dynamic_api import (
		create_dynamic_entity_from_parsed,
		build_entity_definition_from_parsed,
		update_system_dynamic_entity,
		get_dynamic_entity_id_by_name,
		get_existing_entity_names,
		BUILTIN_REFERENCE_TYPES,
	)

	created_ids = {}

	# ---- Pass 1: create everything with references as strings ----
	print("Pass 1/2: creating entities (references temporarily as strings) ...")
	for entity_name, wrapper in entities.items():
		fields = wrapper.get("fields") if isinstance(wrapper, dict) else wrapper
		description = wrapper.get("description") if isinstance(wrapper, dict) else None
		print(f"Processing entity: {entity_name} ...")
		try:
			resp = create_dynamic_entity_from_parsed(
				entity_name,
				fields,
				token=token,
				base_url=host,
				has_personal=has_personal,
				has_community=has_community,
				entity_description=description,
				downgrade_references=True,
			)
			dyn_id = resp.get("dynamicEntityId", "<no-id>")
			created_ids[entity_name] = dyn_id
			print(f"  {'Exists' if resp.get('existing') else 'Created'}: {dyn_id}")
		except Exception as e:
			print(f"  Failed to create entity {entity_name}: {e}")

	# ---- Pass 2: restore reference types now that all targets exist ----
	entities_with_refs = [
		n for n, w in entities.items()
		if _has_reference_field(w.get("fields") if isinstance(w, dict) else w)
	]
	if not entities_with_refs:
		return

	print("Pass 2/2: restoring reference types ...")
	existing_names = get_existing_entity_names(token=token, base_url=host)
	allowed_refs = {f"reference:{n}" for n in existing_names} | BUILTIN_REFERENCE_TYPES

	for entity_name in entities_with_refs:
		wrapper = entities[entity_name]
		fields = wrapper.get("fields") if isinstance(wrapper, dict) else wrapper
		description = wrapper.get("description") if isinstance(wrapper, dict) else None
		dyn_id = created_ids.get(entity_name) or get_dynamic_entity_id_by_name(entity_name, token=token, base_url=host)
		if not dyn_id or dyn_id == "<no-id>":
			print(f"  Skipping references for {entity_name}: entity was not created")
			continue
		try:
			entity_def = build_entity_definition_from_parsed(
				entity_name,
				fields,
				has_personal=has_personal,
				has_community=has_community,
				entity_description=description,
				allowed_reference_types=allowed_refs,
			)
			update_system_dynamic_entity(dyn_id, entity_def, token=token, base_url=host)
			print(f"  Restored references: {entity_name}")
		except Exception as e:
			print(f"  Failed to restore references for {entity_name}: {e}")


def main():
	"""Main function to run the parser."""
	parser = argparse.ArgumentParser(description="Parse minimal field matrix and optionally create dynamic entities on OBP")
	parser.add_argument("file", nargs="?", default="min_field_matrix.xlsx", help="Path to the xlsx file")
	parser.add_argument("--create", action="store_true", help="Create parsed entities on OBP (will call management API)")
	parser.add_argument("--update", action="store_true", help="Update existing parsed entities on OBP (will call management API)")
	parser.add_argument("--token", default=None, help="DirectLogin token to use (overrides obp_client.token)")
	parser.add_argument("--host", default=None, help="OBP host to use (overrides obp_client.obp_host)")
	parser.add_argument("--yes", action="store_true", help="If set with --create, skip confirmation prompt")
	parser.add_argument("--save", action="store_true", help="Save parsed entities to --output non-interactively (no prompt)")
	parser.add_argument("--output", default="entities_output.txt", help="Output file used by --save (default: entities_output.txt)")
	args = parser.parse_args()
	file_path = args.file

	# Read access flags from environment (.env or system env)
	def _env_to_bool(val):
		if val is None:
			return False
		if isinstance(val, bool):
			return val
		s = str(val).strip().lower()
		return s in ("1", "true", "yes", "y", "on")

	has_personal = _env_to_bool(os.getenv("HAS_PERSONAL_ENTITY", "false"))
	has_community = _env_to_bool(os.getenv("HAS_COMMUNITY_ACCESS", "false"))

	# Check if file exists
	if not Path(file_path).exists():
		print(f"File '{file_path}' does not exist.")
		return

	print(f"Parsing file: {file_path}")
	entities = parse_xlsx_entities(file_path)

	if not entities:
		print("No entities found or error occurred.")
		return

	# Display results
	print(f"\nFound {len(entities)} entities:")
	print("=" * 50)

	for entity_name, entity_dict in entities.items():
		print(f"\nEntity: {entity_name}")
		print("-" * 30)
		if entity_dict:
			for key, value in entity_dict.items():
				print(f"  {key}: {value}")
		else:
			print("  (No data)")

	# Optionally create or update entities on OBP management API
	if args.create and args.update:
		print("Cannot use --create and --update together. Choose one.")
		return

	if args.create or args.update:
		if args.create:
			print("--create flag provided: will attempt to create parsed entities on OBP")
		if args.update:
			print("--update flag provided: will attempt to update existing parsed entities on OBP")
		if not args.yes:
			confirm = input("Proceed to create entities on OBP? Type 'yes' to continue: ")
			if confirm.strip().lower() != "yes":
				print("Aborted by user.")
				return

		if args.create:
			# Two-pass create so references between entities always resolve,
			# regardless of spreadsheet ordering or reference cycles.
			_create_entities_two_pass(
				entities,
				token=args.token,
				host=args.host,
				has_personal=has_personal,
				has_community=has_community,
			)
			return

		# --update: refresh existing entities in place. Validate references
		# against the entities that currently exist on OBP.
		from obp_dynamic_api import (
			get_dynamic_entity_id_by_name,
			build_entity_definition_from_parsed,
			update_system_dynamic_entity,
			get_existing_entity_names,
			BUILTIN_REFERENCE_TYPES,
		)
		existing_names = get_existing_entity_names(token=args.token, base_url=args.host)
		allowed_refs = {f"reference:{n}" for n in existing_names} | BUILTIN_REFERENCE_TYPES
		for entity_name, entity_wrapper in entities.items():
			print(f"Processing entity: {entity_name} ...")
			try:
				entity_description = entity_wrapper.get("description") if isinstance(entity_wrapper, dict) else None
				fields = entity_wrapper.get("fields") if isinstance(entity_wrapper, dict) else entity_wrapper
				dynamic_id = get_dynamic_entity_id_by_name(entity_name, token=args.token, base_url=args.host)
				if not dynamic_id:
					print(f"No existing dynamic entity found for '{entity_name}', skipping update.")
					continue
				entity_def = build_entity_definition_from_parsed(
					entity_name, fields, entity_description=entity_description,
					allowed_reference_types=allowed_refs,
				)
				resp = update_system_dynamic_entity(dynamic_id, entity_def, token=args.token, base_url=args.host)
				print(f"Updated: {resp.get('dynamicEntityId', dynamic_id)}")
			except Exception as e:
				print(f"Failed to process entity {entity_name}: {e}")
		return

	# Non-interactive save (used by scripts, e.g. recreate_ogcr_entities.sh)
	if args.save:
		_write_entities_file(entities, file_path, args.output)
		return

	# Otherwise, offer to save interactively
	save_option = input("\nSave results to a file? (y/n): ").lower().strip()
	if save_option in ['y', 'yes']:
		output_file = input("Enter output filename (default: entities_output.txt): ").strip()
		if not output_file:
			output_file = "entities_output.txt"
		_write_entities_file(entities, file_path, output_file)


def _write_entities_file(entities, file_path, output_file):
	"""Write parsed entities to `output_file` in the `Entity: <name>` format
	consumed by delete_ogcr_entities.py."""
	try:
		with open(output_file, 'w', encoding='utf-8') as f:
			f.write(f"Parsed entities from: {file_path}\n")
			f.write("=" * 50 + "\n\n")

			for entity_name, entity_dict in entities.items():
				f.write(f"Entity: {entity_name}\n")
				f.write("-" * 30 + "\n")
				if entity_dict:
					for key, value in entity_dict.items():
						f.write(f"  {key}: {value}\n")
				else:
					f.write("  (No data)\n")
				f.write("\n")

		print(f"Results saved to: {output_file}")
	except Exception as e:
		print(f"Error saving file: {e}")


if __name__ == "__main__":
	main()