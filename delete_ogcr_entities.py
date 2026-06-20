"""Delete ONLY the OGCR dynamic entities listed in a parsed entities file.

Reads an `entities_output.txt`-style file (produced by `parse_minimum_fields.py
--save`) and, for every `Entity: <name>` line, deletes that system dynamic
entity on OBP — both its objects and its definition. Any dynamic entity NOT
listed in the file is left untouched (unlike `delete_all_dynamic_entities.py`,
which wipes everything).

Deletion runs in repeated passes because reference (foreign-key) constraints
can make order matter: a parent cannot be removed while a child still
references it. Each pass deletes whatever it can; we stop once all target
entities are gone, or once a pass makes no progress.

Usage:
    python3 delete_ogcr_entities.py [path/to/entities_output.txt] [--yes] [--token TOKEN]

Options:
    file (positional)  Path to the parsed entities file. Defaults to
                       `entities_output.txt`.
    --yes              Skip the interactive confirmation prompt.
    --token            DirectLogin token (overrides token from obp_client.py).

Exits non-zero if any target entity could not be deleted, so callers under
`set -e` (e.g. recreate_ogcr_entities.sh) abort instead of recreating on top
of a dirty instance.
"""

import argparse
import logging
import sys

from obp_client import token as default_token
from get_and_delete_dynamic_entities import (
	get_all_system_dynamic_entities,
	get_all_objects_for_system_dynamic_entity,
	delete_object_for_system_dynamic_entity,
	delete_system_dynamic_entity,
)

logging.basicConfig(
	level=logging.INFO,
	format='%(asctime)s | %(levelname)-8s | %(message)s',
	datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)

DEFAULT_INPUT = "entities_output.txt"
ENTITY_PREFIX = "Entity:"
# Maximum delete passes; reference constraints can require several passes.
MAX_PASSES = 8


def print_separator(char="=", length=80):
	logger.info(char * length)


def parse_entity_names(path):
	"""Extract entity names from `Entity: <name>` lines in the parsed file."""
	names = []
	with open(path, encoding="utf-8") as f:
		for line in f:
			line = line.rstrip("\n")
			if line.startswith(ENTITY_PREFIX):
				name = line[len(ENTITY_PREFIX):].strip()
				if name:
					names.append(name)
	return names


def _delete_objects_for_entity(name, token):
	"""Best-effort delete of every object of one entity. Returns #deleted."""
	try:
		response = get_all_objects_for_system_dynamic_entity(name, token=token)
	except Exception as e:
		logger.error(f"  ✗ API error while fetching objects for {name}: {e}")
		return 0
	if response is None:
		return 0  # entity already gone (404)

	id_key = f"{name.lower()}_id"
	objects = response.get(f"{name.lower()}_list", [])
	object_ids = [x[id_key] for x in objects if id_key in x]
	deleted = 0
	for obj_id in object_ids:
		try:
			delete_object_for_system_dynamic_entity(name, obj_id, token=token)
			logger.info(f"  ✓ Deleted object {name}/{obj_id}")
			deleted += 1
		except Exception as e:
			# A reference (FK) constraint can block this until the referencing
			# object is gone; a later pass will retry.
			logger.warning(f"  ⏳ Could not delete object {name}/{obj_id} yet: {e}")
	return deleted


def wipe_target_entities(target_names, token):
	"""Delete the named entities (objects + definitions) in retry passes.

	Returns the list of target entities still present afterwards (empty == clean).
	"""
	target_set = set(target_names)
	for pass_num in range(1, MAX_PASSES + 1):
		try:
			all_entities = get_all_system_dynamic_entities(token=token)["dynamic_entities"]
		except Exception as e:
			logger.error(f"✗ Failed to list dynamic entities: {e}")
			return list(target_set)

		present = {
			e.get("entity_name"): e.get("dynamic_entity_id")
			for e in all_entities
			if e.get("entity_name") in target_set
		}
		if not present:
			logger.info(f"✓ All target entities deleted (clean after {pass_num - 1} pass(es)).")
			return []

		logger.info(f"--- Pass {pass_num}/{MAX_PASSES}: {len(present)} target entit(y/ies) remaining: {', '.join(present)} ---")
		progress = 0

		# Delete objects first (frees object-level FK references), then definitions.
		for name in present:
			progress += _delete_objects_for_entity(name, token)

		for name, entity_id in present.items():
			if not entity_id:
				logger.error(f"  ✗ Missing entity id for {name}, cannot delete definition")
				continue
			try:
				delete_system_dynamic_entity(entity_id, token=token)
				logger.info(f"  ✓ Deleted entity definition: {name} ({entity_id})")
				progress += 1
			except Exception as e:
				# Likely blocked by a reference from another entity; retry next pass.
				logger.warning(f"  ⏳ Could not delete entity {name} yet: {e}")

		if progress == 0:
			logger.error(
				f"✗ Pass {pass_num} made no progress while {len(present)} target entit(y/ies) remain. "
				"Stopping to avoid an infinite loop."
			)
			return list(present)

	# Exhausted MAX_PASSES — report whatever is left.
	try:
		all_entities = get_all_system_dynamic_entities(token=token)["dynamic_entities"]
		return [e.get("entity_name") for e in all_entities if e.get("entity_name") in target_set]
	except Exception:
		return list(target_set)


def main():
	parser = argparse.ArgumentParser(
		description="Delete dynamic entities listed in a parsed entities file."
	)
	parser.add_argument(
		"file",
		nargs="?",
		default=DEFAULT_INPUT,
		help=f"Path to the parsed entities file (default: {DEFAULT_INPUT}).",
	)
	parser.add_argument(
		"--yes",
		action="store_true",
		help="Skip the interactive confirmation prompt.",
	)
	parser.add_argument(
		"--token",
		default=default_token,
		help="DirectLogin token (overrides token from obp_client.py).",
	)
	args = parser.parse_args()

	# -------------------------------------------------------------------------
	# Read the list of entity names to delete
	# -------------------------------------------------------------------------
	try:
		target_names = parse_entity_names(args.file)
	except FileNotFoundError:
		logger.error(f"File not found: {args.file}")
		logger.error("Generate it first with: python3 parse_minimum_fields.py <xlsx> (and save to a file)")
		sys.exit(1)

	if not target_names:
		logger.error(f"No 'Entity:' lines found in {args.file} - nothing to delete.")
		sys.exit(1)

	logger.info(f"Found {len(target_names)} entity name(s) in {args.file}:")
	for name in target_names:
		logger.info(f"  - {name}")
	print_separator()

	# -------------------------------------------------------------------------
	# Confirm before doing anything destructive
	# -------------------------------------------------------------------------
	if not args.yes:
		answer = input(
			f"This will DELETE these {len(target_names)} entities and ALL their records on OBP. Continue? (y/n): "
		).lower().strip()
		if answer not in ("y", "yes"):
			logger.info("Aborted - nothing deleted.")
			sys.exit(0)

	# -------------------------------------------------------------------------
	# Delete the target entities (objects + definitions) in retry passes
	# -------------------------------------------------------------------------
	logger.info("Deleting target OGCR entities (objects + definitions)")
	print_separator("-")

	remaining = wipe_target_entities(target_names, args.token)

	print_separator()
	if not remaining:
		logger.info("✓ All target OGCR entities deleted.")
		print_separator("=")
		return 0

	logger.error(f"✗ Could not delete: {', '.join(remaining)}")
	print_separator("=")
	return 1


if __name__ == "__main__":
	sys.exit(main())
