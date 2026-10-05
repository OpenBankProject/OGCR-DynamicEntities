"""Which dynamic entity fields the Dynamic Queries need indexed.

Whether a field is indexed is decided by how the data is queried, not by the data
model, so it is read from the Dynamic Query declarations in this repo (the
`*_query.json` files that dynamic_resource_docs.py pushes as programming_lang Query)
rather than from the spreadsheet. obp_dynamic_api.should_index_field adds these
fields to its baseline (references, <entity>_id, ALWAYS_INDEX_FIELD_NAMES).

A declaration needs, on the entity it reads (`from`): every field its `where`
filters on, and every field it returns (`select`), because a caller may filter and
sort the result on any of them (obp_filter, obp_sort_by), which OBP allows on
indexed fields only. A lookup query (LOOKUP_QUERIES) is the exception: the caller
only ever filters it to one activity's rows, so it needs that one field, not its
whole `select` (indexing long text such as description costs writes for nothing). On each joined entity: the join's `on` field, every field of the join's
`where`, and the field its `pick` / `order` sorts by (`latest_by:<field>`).

A reverse join is linked by a field of the joined entity, which OBP looks up by
index. A forward join is linked by the `from` entity's field, and its `on` names the
joined entity's own id field, which is indexed anyway. So `on` is listed for the
joined entity either way; a field the entity doesn't have is never indexed.

No side effects on import (no login), so offline scripts can use it.

Usage:
    python3 query_indexes.py     # for each query, the fields it needs indexed and why
"""

import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
QUERY_FILES_GLOB = "*_query.json"

# Queries the caller filters to one activity (obp_filter[activity_id]=eq:<id>, the
# registry's activity detail page, see dynamic_resource_docs.py): query file -> the
# field it is looked up by. Only that field of `select` is indexed.
LOOKUP_QUERIES = {
	"registry_activity_query.json": "activity_id",
	"registry_activity_practices_query.json": "activity_id",
	"registry_activity_sdgs_query.json": "activity_id",
	"registry_activity_certificates_query.json": "activity_id",
}


def _order_field(text):
	"""'latest_by:issue_date' -> 'issue_date'; None for anything else."""
	if isinstance(text, str) and ":" in text:
		kind, field = text.split(":", 1)
		if kind.strip() in ("latest_by", "earliest_by") and field.strip():
			return field.strip()
	return None


def needs_with_reasons(declaration, lookup_key=None):
	"""[(entity, field, why)] that one Dynamic Query declaration needs indexed, in declaration order.

	`lookup_key` (from LOOKUP_QUERIES) replaces the whole `select` with that one field.
	"""
	needs = []
	source = declaration.get("from")
	if source:
		for field in (declaration.get("where") or {}):
			needs.append((source, field, "filtered by the query's where"))
		if lookup_key:
			needs.append((source, lookup_key, f"the caller looks the query up by it (obp_filter[{lookup_key}])"))
		else:
			for field in declaration.get("select") or []:
				needs.append((source, field, "returned by the query, so callers may filter and sort on it"))
	for join in declaration.get("join") or []:
		entity = join.get("entity")
		if not entity:
			continue
		if join.get("on"):
			needs.append((entity, join["on"], f"the field the {source} -> {entity} join is linked on"))
		for field in (join.get("where") or {}):
			needs.append((entity, field, f"filtered by the {entity} join's where"))
		for key in ("pick", "order"):
			field = _order_field(join.get(key))
			if field:
				needs.append((entity, field, f"sorted by the {entity} join's {key} ({join[key]})"))
	return needs


def needs_of(declaration, lookup_key=None):
	"""{entity: {field}} that one Dynamic Query declaration needs indexed."""
	needs = defaultdict(set)
	for entity, field, _ in needs_with_reasons(declaration, lookup_key):
		needs[entity].add(field)
	return needs


def query_index_needs(directory=HERE):
	"""{entity: {field: [query file, ...]}} over every Query declaration in `directory`."""
	needs = defaultdict(lambda: defaultdict(list))
	for path in sorted(Path(directory).glob(QUERY_FILES_GLOB)):
		try:
			declaration = json.loads(path.read_text())
		except ValueError as e:
			raise SystemExit(f"{path.name}: not valid JSON: {e}")
		for entity, fields in needs_of(declaration, LOOKUP_QUERIES.get(path.name)).items():
			for field in fields:
				needs[entity][field].append(path.name)
	return needs


# Loaded once: {entity: {field: [query file, ...]}}, and {entity: {field}}.
QUERY_INDEX_SOURCES = query_index_needs()
QUERY_INDEXED_FIELDS = {entity: set(fields) for entity, fields in QUERY_INDEX_SOURCES.items()}


if __name__ == "__main__":
	paths = sorted(HERE.glob(QUERY_FILES_GLOB))
	print(f"Fields the Dynamic Queries need indexed ({len(paths)} query file(s), {QUERY_FILES_GLOB}).")
	print("They are declared \"indexed\": true on top of the baseline (references, <entity>_id);")
	print("./update_dynamic_entities.sh applies them on OBP.")
	for path in paths:
		declaration = json.loads(path.read_text())
		needs = needs_with_reasons(declaration, LOOKUP_QUERIES.get(path.name))
		lookup = f", looked up by {LOOKUP_QUERIES[path.name]}" if path.name in LOOKUP_QUERIES else ""
		print(f"\n{path.name}  (reads {declaration.get('from')}{lookup})")
		if not needs:
			print("  nothing beyond the baseline")
		width = max((len(f"{e}.{f}") for e, f, _ in needs), default=0)
		for entity, field, why in needs:
			print(f"  {entity + '.' + field:<{width}}  {why}")
