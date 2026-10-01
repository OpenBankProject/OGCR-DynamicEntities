"""Check the field types in OBP's generated OpenAPI document against the spreadsheet.

Downloads the dynamic-entity OpenAPI document from OBP_HOSTNAME
(/obp/v7.0.0/resource-docs/OBPv7.0.0/openapi.yaml?content=dynamic) and, for every
entity in the sheet in the space (OBP_ENTITY_SPACE_ID, see obp_space.py; empty is
system level), compares each field's type with the type the
sheet declares. Every operation is checked (GET, POST, PUT, PATCH, DELETE, the
list), in request and response bodies.

OBP generates these types from each field's example, not from its declared type,
so they can be wrong even when the entity on OBP is right (e.g. a number field
with a whole-number example is documented as integer). Types the document cannot
express are expected as follows:
  number, integer, boolean   -> the same
  string, DATE_WITH_DAY      -> string
  reference:<entity>         -> string
  json                       -> object or array

Reported: entities in the sheet missing from the document, fields missing from it,
fields in it that the sheet doesn't have (apart from <entity>_id, the record id
OBP adds), and type mismatches with the operations
they appear in. Anonymous: one GET, no login needed. OBP caches the document; its
"Generated on" time is printed.

Usage:
    python3 check_openapi_field_types.py [path/to/min_field_matrix.xlsx]

Exits 0 when every type matches, 1 when any differ, 2 if the sheet or the document
could not be read.
"""

import argparse
import re
import sys
from collections import defaultdict

import yaml

from obp_client import obp_host, session
from obp_dynamic_api import build_entity_definition_from_parsed
from obp_space import SPACE_ID
from parse_minimum_fields import parse_xlsx_entities

DEFAULT_SPREADSHEET = "min_field_matrix.xlsx"
OPENAPI_PATH = "/obp/v7.0.0/resource-docs/OBPv7.0.0/openapi.yaml?content=dynamic"
SYSTEM_BANK_IDS = ("SYS", "")
YAML_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)  # the document is several MB


def expected_doc_types(sheet_type):
	"""The OpenAPI types that are right for a field of this sheet type."""
	if sheet_type in ("number", "integer", "boolean"):
		return {sheet_type}
	if sheet_type == "json":
		return {"object", "array"}
	return {"string"}  # string, DATE_WITH_DAY, reference:<entity>


def entity_of_path(path, bank_id):
	"""The entity a document path belongs to at bank_id, or None.

	Paths look like /banks/<bank>/<entity>[/{id}] at a bank and /<entity>[/{id}]
	at system level; a `public/` segment may come before the entity."""
	prefix = "" if bank_id in SYSTEM_BANK_IDS else f"/banks/{bank_id}"
	if not path.startswith(prefix + "/"):
		return None
	parts = path[len(prefix) + 1:].split("/")
	if parts[0] == "public":
		parts = parts[1:]
	if not parts or not parts[0] or (not prefix and parts[0] in ("banks", "my")):
		return None
	return parts[0]


def field_schemas(schema, entity):
	"""{field: schema} of the entity's fields in a request or response body schema.

	Request bodies hold the fields directly; responses wrap them in `<entity>` or,
	for the list, in `<entity>_list` items."""
	props = (schema or {}).get("properties") or {}
	if entity in props:
		return (props[entity] or {}).get("properties") or {}
	if f"{entity}_list" in props:
		return ((props[f"{entity}_list"] or {}).get("items") or {}).get("properties") or {}
	return {k: v for k, v in props.items() if k != "bank_id"}


def document_types(document, bank_id):
	"""{entity: {field: {type: [operation, ...]}}} for the entities at bank_id."""
	found = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
	for path, operations in (document.get("paths") or {}).items():
		entity = entity_of_path(path, bank_id)
		if not entity:
			continue
		by_id = "/{" in path
		for method, op in operations.items():
			if not isinstance(op, dict):
				continue
			label = f"{method.upper()}{' by id' if by_id else (' list' if method == 'get' else '')}"
			bodies = []
			request = ((op.get("requestBody") or {}).get("content") or {}).get("application/json", {}).get("schema")
			if request:
				bodies.append((f"{label} request", request))
			for code, response in (op.get("responses") or {}).items():
				schema = ((response or {}).get("content") or {}).get("application/json", {}).get("schema")
				if schema:
					bodies.append((f"{label} response", schema))
			for where, schema in bodies:
				for field, field_schema in field_schemas(schema, entity).items():
					found[entity][field][(field_schema or {}).get("type", "(none)")].append(where)
	return found


def main():
	parser = argparse.ArgumentParser(description="Check the field types in OBP's OpenAPI document against the spreadsheet.")
	parser.add_argument("file", nargs="?", default=DEFAULT_SPREADSHEET,
		help=f"Path to the xlsx file (default: {DEFAULT_SPREADSHEET})")
	args = parser.parse_args()
	url = f"{obp_host}{OPENAPI_PATH}"
	bank_id = SPACE_ID or "SYS"

	sheet = parse_xlsx_entities(args.file)
	if not sheet:
		print(f"✗ No entities read from {args.file}")
		return 2
	try:
		response = session.get(url, timeout=300)
		response.raise_for_status()
		document = yaml.load(response.text, Loader=YAML_LOADER)
	except Exception as e:
		print(f"✗ Could not read the OpenAPI document {url}: {e}")
		return 2

	generated = re.search(r"Generated on: (\S+)", (document.get("info") or {}).get("description", ""))
	print(f"{url}")
	print(f"  generated on {generated.group(1) if generated else '(unknown)'}; bank id {bank_id}; sheet {args.file}")
	on_doc = document_types(document, bank_id)

	problems = 0
	checked = 0
	missing_entities = []
	for name, wrapper in sheet.items():
		if name not in on_doc:
			missing_entities.append(name)
			continue
		definition = build_entity_definition_from_parsed(name, wrapper["fields"], has_personal=False,
			has_community=False, has_public=wrapper.get("public_access", False), allowed_reference_types=None)
		declared = {field: prop["type"] for field, prop in definition[name]["properties"].items()}
		lines = []
		for field, sheet_type in declared.items():
			in_doc = on_doc[name].get(field)
			if not in_doc:
				lines.append(f"  - {field} ({sheet_type}): not in the document")
				continue
			checked += 1
			wanted = expected_doc_types(sheet_type)
			for doc_type, operations in sorted(in_doc.items()):
				if doc_type not in wanted:
					lines.append(f"  ✗ {field}: sheet {sheet_type}, document {doc_type} in {', '.join(operations)}")
		# OBP adds <entity>_id (the record id) to every entity itself.
		for field in sorted(set(on_doc[name]) - set(declared) - {f"{name}_id"}):
			lines.append(f"  + {field}: in the document, not in the sheet")
		if lines:
			problems += len(lines)
			print(f"\n~ {name}")
			print("\n".join(lines))

	if missing_entities:
		problems += len(missing_entities)
		print(f"\nIn the sheet but not in the document at bank id {bank_id}: {', '.join(missing_entities)}")

	print()
	if problems:
		print(f"✗ {problems} problem(s); {checked} field(s) checked")
		return 1
	print(f"✓ All {checked} field(s) of {len(sheet)} entities have the right type in every operation")
	return 0


if __name__ == "__main__":
	sys.exit(main())
