"""Delete the dynamic entities listed in a parsed entities file.

Reads an `entities_output.txt`-style file (produced by `parse_minimum_fields.py`
when you choose to save results) and, for every `Entity: <name>` line, deletes
that system dynamic entity on OBP — first removing all of its objects, then the
entity definition itself.

Usage:
    python3 delete_entities.py [path/to/entities_output.txt] [--yes] [--token TOKEN]

Options:
    file (positional)  Path to the parsed entities file. Defaults to
                       `entities_output.txt`.
    --yes              Skip the interactive confirmation prompt.
    --token            DirectLogin token (overrides token from obp_client.py).
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
	# STEP 1: Delete all objects for each target entity
	# -------------------------------------------------------------------------
	logger.info("STEP 1: Deleting entity objects")
	print_separator("-")

	total_objects_deleted = 0
	total_objects_failed = 0

	for name in target_names:
		logger.info(f"Processing entity: {name}")
		try:
			response = get_all_objects_for_system_dynamic_entity(name, token=args.token)
			if response is None:
				logger.info(f"  → Entity {name} does not exist yet - skipping")
				continue
			objects = response.get(f"{name.lower()}_list", [])
			if not objects:
				logger.info(f"  → No objects found for {name}")
				continue
			logger.info(f"  ✓ Found {len(objects)} object(s) for {name}")
		except Exception as e:
			logger.error(f"  ✗ API error while fetching objects for {name}: {e}")
			continue

		object_ids = [x[f"{name.lower()}_id"] for x in objects]
		for idx, obj_id in enumerate(object_ids, 1):
			try:
				delete_object_for_system_dynamic_entity(name, obj_id, token=args.token)
				logger.info(f"  ✓ [{idx}/{len(object_ids)}] Deleted object: {obj_id}")
				total_objects_deleted += 1
			except Exception as e:
				logger.error(f"  ✗ [{idx}/{len(object_ids)}] Failed to delete object {obj_id}: {e}")
				total_objects_failed += 1
		logger.info("")

	print_separator("-")
	logger.info(f"Object Deletion Summary: {total_objects_deleted} deleted, {total_objects_failed} failed")
	print_separator()

	# -------------------------------------------------------------------------
	# STEP 2: Delete the entity definitions themselves
	# -------------------------------------------------------------------------
	logger.info("STEP 2: Deleting dynamic entity definitions")
	print_separator("-")

	try:
		all_entities = get_all_system_dynamic_entities(token=args.token)["dynamic_entities"]
		logger.info(f"Retrieved {len(all_entities)} total dynamic entities from system")
	except Exception as e:
		logger.error(f"Failed to retrieve dynamic entities: {e}")
		sys.exit(1)

	# Map entity name -> dynamic_entity_id for the entities we want to delete
	name_to_id = {}
	for entity in all_entities:
		ename = entity.get("entity_name")
		if ename in target_names:
			name_to_id[ename] = entity.get("dynamic_entity_id")

	missing = [n for n in target_names if n not in name_to_id]
	if missing:
		logger.info(f"Not present on OBP (skipped): {', '.join(missing)}")

	total_entities_deleted = 0
	total_entities_failed = 0
	items = list(name_to_id.items())
	for idx, (ename, entity_id) in enumerate(items, 1):
		try:
			delete_system_dynamic_entity(entity_id, token=args.token)
			logger.info(f"  ✓ [{idx}/{len(items)}] Deleted entity: {ename} ({entity_id})")
			total_entities_deleted += 1
		except Exception as e:
			logger.error(f"  ✗ [{idx}/{len(items)}] Failed to delete entity {ename} ({entity_id}): {e}")
			total_entities_failed += 1

	print_separator("-")
	logger.info(f"Entity Deletion Summary: {total_entities_deleted} deleted, {total_entities_failed} failed")
	print_separator("=")


if __name__ == "__main__":
	main()
