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

			# Convert to string for processing (handle Excel dates safely)
			col_a_str = str(col_a_value).strip()
			col_b_str = str(col_b_value).strip()
			col_c_str = str(col_c_value).strip()
			col_d_str = str(col_d_value).strip()
			col_f_str = str(col_f_value).strip()
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
						entry = {"value": col_d_str}
						if cleaned_example:
							entry["example"] = cleaned_example
						if col_f_str:
							entry["description"] = col_f_str
						current_dict[safe_key] = entry
					elif has_green_check_c:
						# Column C has green check but not B - mark as optional
						opt_key = f"{safe_key} (optional)"
						entry = {"value": col_d_str}
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


def main():
	"""Main function to run the parser."""
	parser = argparse.ArgumentParser(description="Parse minimal field matrix and optionally create dynamic entities on OBP")
	parser.add_argument("file", nargs="?", default="min_field_matrix.xlsx", help="Path to the xlsx file")
	parser.add_argument("--create", action="store_true", help="Create parsed entities on OBP (will call management API)")
	parser.add_argument("--update", action="store_true", help="Update existing parsed entities on OBP (will call management API)")
	parser.add_argument("--token", default=None, help="DirectLogin token to use (overrides obp_client.token)")
	parser.add_argument("--host", default=None, help="OBP host to use (overrides obp_client.obp_host)")
	parser.add_argument("--yes", action="store_true", help="If set with --create, skip confirmation prompt")
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
		print("--create flag provided: will attempt to create parsed entities on OBP")
		if args.update:
			print("--update flag provided: will attempt to update existing parsed entities on OBP")
		if not args.yes:
			confirm = input("Proceed to create entities on OBP? Type 'yes' to continue: ")
			if confirm.strip().lower() != "yes":
				print("Aborted by user.")
				return

		# iterate and call API (create or update)
		for entity_name, entity_wrapper in entities.items():
			print(f"Processing entity: {entity_name} ...")
			try:
				entity_description = entity_wrapper.get("description") if isinstance(entity_wrapper, dict) else None
				fields = entity_wrapper.get("fields") if isinstance(entity_wrapper, dict) else entity_wrapper
				if args.create:
					resp = create_dynamic_entity_from_parsed(
						entity_name,
						fields,
						token=args.token,
						base_url=args.host,
						has_personal=has_personal,
						has_community=has_community,
						entity_description=entity_description,
					)
					print(f"Created: {resp.get('dynamicEntityId', '<no-id>')}")
				elif args.update:
					# find existing dynamicEntityId by name
					from obp_dynamic_api import get_dynamic_entity_id_by_name, build_entity_definition_from_parsed, update_system_dynamic_entity
					dynamic_id = get_dynamic_entity_id_by_name(entity_name, token=args.token, base_url=args.host)
					if not dynamic_id:
						print(f"No existing dynamic entity found for '{entity_name}', skipping update.")
						continue
					# build definition and call update
					entity_def = build_entity_definition_from_parsed(entity_name, fields, entity_description=entity_description)
					resp = update_system_dynamic_entity(dynamic_id, entity_def, token=args.token, base_url=args.host)
					print(f"Updated: {resp.get('dynamicEntityId', dynamic_id)}")
			except Exception as e:
				print(f"Failed to process entity {entity_name}: {e}")
		# end create loop
		return

	# If not creating, offer to save to file
	save_option = input("\nSave results to a file? (y/n): ").lower().strip()
	if save_option in ['y', 'yes']:
		output_file = input("Enter output filename (default: entities_output.txt): ").strip()
		if not output_file:
			output_file = "entities_output.txt"

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