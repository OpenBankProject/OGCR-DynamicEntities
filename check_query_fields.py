"""Check that every field the Dynamic Queries read exists in the spreadsheet.

Offline and read-only: it does not log in to OBP or change anything. For each
`*_query.json` (the Dynamic Query declarations dynamic_resource_docs.py pushes as
programming_lang Query) it checks, against the entities in min_field_matrix.xlsx
(read the way parse_minimum_fields.py reads them: a field is included when column B
or C is ticked):

  - the `from` entity and every joined `entity` exist
  - every field of the query's `select` and `where` exists on the `from` entity
  - every join's `on`, `fields` values, `where` fields and `pick` / `order`
    (`latest_by:<field>`) field exist on the joined entity

OBP checks a Query against the space's entities only when the doc is created or run,
so a field renamed or removed in the sheet otherwise shows up as a doc that cannot be
created (it 404s) or that fails every call with OBP-40065. Run this after changing the
sheet or a query, before ./update_dynamic_entities.sh or a recreate.

Entities OGCR-chain-cache defines (parse_minimum_fields.CHAIN_CACHE_ENTITIES) are not
checked: their fields come from that repo, not this sheet.

Usage:
	python3 check_query_fields.py [path/to/min_field_matrix.xlsx]

Exit code: 0 every field found, 1 at least one missing.
"""

import argparse
import json
import sys
from collections import defaultdict

import pandas as pd

from check_min_field_matrix import (
	DEFAULT_INPUT, END_MARKER, HERE, cell_str, has_green_checkmark, load_definitions, sanitise_field_name,
)
from query_indexes import QUERY_FILES_GLOB, _order_field

CHAIN_CACHE_ENTITIES = load_definitions("parse_minimum_fields.py", ["CHAIN_CACHE_ENTITIES"])["CHAIN_CACHE_ENTITIES"]


def sheet_fields(path):
	"""{entity: {field}} of the fields parse_minimum_fields.py would include."""
	df = pd.read_excel(path, engine="openpyxl")
	entities = defaultdict(set)
	current = None
	for _, row in df.iterrows():
		name = cell_str(row, 0)
		if name == END_MARKER:
			break
		if name.lower().startswith("entity:"):
			current = name[7:].strip()
			entities[current]
			continue
		if current and name and name != "nan":
			if has_green_checkmark(cell_str(row, 1)) or has_green_checkmark(cell_str(row, 2)):
				entities[current].add(sanitise_field_name(name))
	return entities


def fields_read(declaration):
	"""[(entity, field, where in the declaration)] for every field the declaration reads."""
	reads = []
	source = declaration.get("from")
	for field in declaration.get("select") or []:
		reads.append((source, field, "select"))
	for field in declaration.get("where") or {}:
		reads.append((source, field, "where"))
	for i, join in enumerate(declaration.get("join") or []):
		entity = join.get("entity")
		at = f"join[{i}] ({entity})"
		if join.get("on"):
			reads.append((entity, join["on"], f"{at} on"))
		for alias, field in (join.get("fields") or {}).items():
			reads.append((entity, field, f"{at} fields.{alias}"))
		for field in join.get("where") or {}:
			reads.append((entity, field, f"{at} where"))
		for key in ("pick", "order"):
			field = _order_field(join.get(key))
			if field:
				reads.append((entity, field, f"{at} {key}"))
	return reads


def check(sheet, query_paths):
	"""[(query file, problem)] for every entity or field a query reads that the sheet lacks."""
	problems = []
	for path in query_paths:
		declaration = json.loads(path.read_text())
		entities = {declaration.get("from")} | {j.get("entity") for j in declaration.get("join") or []}
		for entity in sorted(e for e in entities if e and e not in CHAIN_CACHE_ENTITIES and e not in sheet):
			problems.append((path.name, f"entity {entity} is not in the sheet"))
		for entity, field, where in fields_read(declaration):
			if entity in CHAIN_CACHE_ENTITIES or entity not in sheet:
				continue
			if field not in sheet[entity]:
				problems.append((path.name, f"{where}: {entity} has no field {field}"))
	return problems


def main():
	parser = argparse.ArgumentParser(description="Check the Dynamic Queries' fields against the spreadsheet (offline).")
	parser.add_argument("matrix", nargs="?", default=DEFAULT_INPUT)
	args = parser.parse_args()

	sheet = sheet_fields(args.matrix)
	query_paths = sorted(HERE.glob(QUERY_FILES_GLOB))
	problems = check(sheet, query_paths)
	print(f"{len(query_paths)} query file(s) checked against {args.matrix} ({len(sheet)} entities)")
	for name, problem in problems:
		print(f"✗ {name}: {problem}")
	if problems:
		print(f"{len(problems)} field(s) missing: fix the query or the sheet before pushing the docs")
		return 1
	print("✓ every entity and field the queries read is in the sheet")
	return 0


if __name__ == "__main__":
	sys.exit(main())
