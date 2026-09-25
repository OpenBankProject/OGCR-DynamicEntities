"""Check the OGCR minimum fields spreadsheet (min_field_matrix.xlsx) for problems.

Offline and read-only: it does not log in to OBP or change anything. It reads
the sheet the same way `parse_minimum_fields.py` does (first sheet, header on
row 1, column A = entity / field name, B = required, C = optional, D = type,
F = description, G = example, stop at END_OF_FILE) and reports, with the
Excel cell, anything that would be dropped, renamed or silently changed when
the entities are created.

POSSIBLE ERRORS it can report (the sheet does not say what it means):
  - entity name with characters OBP rejects (e.g. a space), or a duplicate
  - entity with no included fields (the parser silently drops it)
  - field type that is not a known type (the parser silently makes it a string)
  - misspelt `reference:` (e.g. `referece:`)
  - reference to an entity not defined in the sheet and not built into OBP
    (the parser silently makes it a string)
  - two fields in one entity that end up with the same name
POSSIBLE WARNINGS it can report (probably fine, worth a look):
  - no END_OF_FILE marker
  - included field with an empty type (becomes a string)
  - field name changed by sanitising (e.g. dots or spaces become `_`)
  - example that does not fit its type (integer, number, boolean,
    DATE_WITH_DAY, json)
  - type written in a different case (e.g. `Integer`)

Usage:
    python3 check_min_field_matrix.py [path/to/min_field_matrix.xlsx] [--strict]

Exits 0 if there are no errors (1 with --strict if there are warnings too),
1 if there are errors or the file cannot be read.
"""

import argparse
import ast
import datetime
import json
import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
DEFAULT_INPUT = "min_field_matrix.xlsx"
END_MARKER = "END_OF_FILE"
ENTITY_NAME_RE = re.compile(r"[A-Za-z0-9_\-]+")


def load_definitions(filename, names):
	"""Return the named top-level functions / constants of a sibling module without
	importing it: parse_minimum_fields and obp_dynamic_api log in to OBP on import,
	and this check must work offline. Reading them from source keeps the rules here
	in step with the real parser."""
	tree = ast.parse((HERE / filename).read_text(encoding="utf-8"))
	wanted = [n for n in tree.body
		if (isinstance(n, ast.FunctionDef) and n.name in names)
		or (isinstance(n, ast.Assign) and any(getattr(t, "id", None) in names for t in n.targets))]
	namespace = {"re": re, "pd": pd}
	exec(compile(ast.Module(body=wanted, type_ignores=[]), filename, "exec"), namespace)
	missing = [n for n in names if n not in namespace]
	if missing:
		raise RuntimeError(f"{', '.join(missing)} not found in {filename}")
	return namespace


parser_defs = load_definitions("parse_minimum_fields.py",
	["_has_green_checkmark", "PUBLIC_ACCESS_HEADERS", "_normalise_header", "_find_public_access_column"])
api_defs = load_definitions("obp_dynamic_api.py", ["SCALAR_ALLOWED_TYPES", "BUILTIN_REFERENCE_TYPES"])
has_green_checkmark = parser_defs["_has_green_checkmark"]
SCALAR_ALLOWED_TYPES = api_defs["SCALAR_ALLOWED_TYPES"]
BUILTIN_REFERENCE_TYPES = api_defs["BUILTIN_REFERENCE_TYPES"]


def sanitise_field_name(name):
	"""Same rule as parse_minimum_fields.py."""
	safe = re.sub(r"[^A-Za-z0-9_\-]", "_", name.replace(".", "_"))
	return re.sub(r"_+", "_", safe).strip("_")


def cell_str(row, idx):
	if len(row) <= idx or pd.isna(row.iloc[idx]):
		return ""
	return str(row.iloc[idx]).strip()


def example_str(row):
	"""Column G the way the parser reads it (dates as YYYY-MM-DD, quotes stripped)."""
	if len(row) <= 6 or pd.isna(row.iloc[6]):
		return ""
	value = row.iloc[6]
	if isinstance(value, (pd.Timestamp, datetime.datetime, datetime.date)):
		return value.strftime("%Y-%m-%d")
	s = str(value).strip()
	if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
		s = s[1:-1].strip()
	return s


def example_problem(prop_type, example):
	"""Return why `example` does not fit `prop_type`, or None."""
	if prop_type == "integer" and not re.fullmatch(r"-?\d+(\.0+)?", example):
		return "is not an integer"
	if prop_type == "number" and not re.fullmatch(r"-?\d+(\.\d+)?", example):
		return "is not a number"
	if prop_type == "boolean" and example.lower() not in ("true", "false"):
		return "is not true/false"
	if prop_type == "DATE_WITH_DAY":
		try:
			datetime.datetime.strptime(example, "%Y-%m-%d")
		except ValueError:
			return "is not a YYYY-MM-DD date"
	if prop_type == "json":
		try:
			json.loads(example)
		except ValueError:
			return "is not valid JSON"
	return None


def check(file_path):
	"""Return (errors, warnings, entity_count), each problem a string starting with its cell."""
	df = pd.read_excel(file_path, engine="openpyxl")
	errors, warnings = [], []
	scalar_by_lower = {t.lower(): t for t in SCALAR_ALLOWED_TYPES}

	entities = {}       # name -> Excel row of its `Entity:` line
	field_counts = {}   # name -> number of included fields
	references = []     # (cell, entity, field, target)
	seen_fields = {}    # (entity, sanitised field) -> cell
	current = None
	found_end = False

	for index, row in df.iterrows():
		excel_row = index + 2  # header is row 1
		col_a = cell_str(row, 0)
		if col_a == END_MARKER:
			found_end = True
			break

		if col_a.lower().startswith("entity:"):
			current = col_a[7:].strip()
			cell = f"A{excel_row}"
			if not ENTITY_NAME_RE.fullmatch(current):
				errors.append(f"{cell}: entity name {current!r} may only contain A-Z a-z 0-9 _ -")
			if current in entities:
				errors.append(f"{cell}: entity {current!r} is already defined at A{entities[current]}")
			entities[current] = excel_row
			field_counts[current] = 0
			continue

		if not current or not col_a or col_a == "nan":
			continue
		required = has_green_checkmark(cell_str(row, 1))
		optional = has_green_checkmark(cell_str(row, 2))
		if not (required or optional):
			continue  # not included in the entity
		field_counts[current] += 1

		field = sanitise_field_name(col_a)
		if field != col_a:
			warnings.append(f"A{excel_row}: field {col_a!r} in {current} becomes {field!r}")
		key = (current, field)
		if key in seen_fields:
			errors.append(f"A{excel_row}: field {field!r} in {current} is already defined at {seen_fields[key]} "
				"(the later one wins)")
		seen_fields[key] = f"A{excel_row}"

		declared = cell_str(row, 3)
		type_cell = f"D{excel_row}"
		prop_type = None
		if not declared:
			warnings.append(f"{type_cell}: {current}.{field} has no type (will be a string)")
		elif declared in SCALAR_ALLOWED_TYPES:
			prop_type = declared
		elif declared.lower() in scalar_by_lower:
			prop_type = scalar_by_lower[declared.lower()]
			warnings.append(f"{type_cell}: {current}.{field} type {declared!r} should be written {prop_type!r}")
		elif declared.startswith("reference:"):
			references.append((type_cell, current, field, declared))
		elif re.match(r"ref\w*:", declared, re.I):
			errors.append(f"{type_cell}: {current}.{field} type {declared!r} looks like a misspelt 'reference:'")
		else:
			errors.append(f"{type_cell}: {current}.{field} type {declared!r} is not one of "
				f"{', '.join(sorted(SCALAR_ALLOWED_TYPES))} or reference:<entity> (will be a string)")

		example = example_str(row)
		if prop_type and example:
			problem = example_problem(prop_type, example)
			if problem:
				warnings.append(f"G{excel_row}: example {example!r} for {current}.{field} ({prop_type}) {problem}")

	if not found_end:
		warnings.append(f"no {END_MARKER} row in column A (the whole sheet was read)")

	for name, count in field_counts.items():
		if count == 0:
			errors.append(f"A{entities[name]}: entity {name!r} has no fields ticked in column B or C "
				"(the parser drops it)")

	for cell, entity, field, declared in references:
		if declared in BUILTIN_REFERENCE_TYPES:
			continue
		target = declared[len("reference:"):].strip()
		if target not in entities:
			errors.append(f"{cell}: {entity}.{field} {declared!r} points to an entity not defined in the sheet "
				"(will be a string)")

	return errors, warnings, len(entities)


def main():
	parser = argparse.ArgumentParser(description="Check the OGCR minimum fields spreadsheet for problems.")
	parser.add_argument("file", nargs="?", default=DEFAULT_INPUT,
		help=f"Path to the xlsx file (default: {DEFAULT_INPUT})")
	parser.add_argument("--strict", action="store_true", help="Fail on warnings as well as errors")
	args = parser.parse_args()

	try:
		errors, warnings, entity_count = check(args.file)
	except FileNotFoundError:
		print(f"✗ File '{args.file}' not found")
		return 1
	except Exception as e:
		print(f"✗ Could not read '{args.file}': {e}")
		return 1

	print(f"Checked {args.file}: {entity_count} entities")
	if errors:
		print(f"\nERRORS FOUND ({len(errors)}):")
		for e in errors:
			print(f"  ✗ {e}")
	if warnings:
		print(f"\nWARNINGS FOUND ({len(warnings)}):")
		for w in warnings:
			print(f"  ! {w}")
	print()
	if errors or (args.strict and warnings):
		print(f"✗ {len(errors)} error(s), {len(warnings)} warning(s)")
		return 1
	print(f"✓ No errors ({len(warnings)} warning(s))")
	return 0


if __name__ == "__main__":
	sys.exit(main())
