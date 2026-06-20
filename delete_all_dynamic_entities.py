import logging
import sys
from get_and_delete_dynamic_entities import (
    get_all_system_dynamic_entities,
    get_all_objects_for_system_dynamic_entity,
    delete_object_for_system_dynamic_entity,
    delete_system_dynamic_entity
)
from obp_client import token, obp_host

# Maximum number of delete passes. Each pass deletes whatever it can; foreign-key
# (reference) constraints can block a parent until its children are gone, so we
# loop and let later passes mop up what earlier passes couldn't.
MAX_PASSES = 8

# Configure logging with better formatting
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Configuration
BASE_URL = obp_host
DIRECTLOGIN_TOKEN = token


def print_separator(char="=", length=80):
    """Print a separator line for better visual separation"""
    logger.info(char * length)


def _extract_entity_name_and_id(entity):
    """Return (entity_name, entity_id) from a dynamic entity listing entry.

    The API may return several keys; this helper ignores common control keys and
    picks the remaining key as the entity name. It also tolerates legacy/internal
    shapes that include an 'entity_name' key.
    """
    control_keys = {"hasPersonalEntity", "has_personal_entity", "dynamicEntityId", "dynamic_entity_id", "userId", "user_id"}
    # Find candidate keys that are not control/meta keys
    candidates = [k for k in entity.keys() if k not in control_keys]
    # Default id lookup
    entity_id = entity.get("dynamicEntityId") or entity.get("dynamic_entity_id") or "N/A"
    if not candidates:
        return ("<unknown>", entity_id)

    # If a candidate key is the literal 'entity_name', try to read its value
    if candidates[0] == "entity_name":
        val = entity.get("entity_name")
        if isinstance(val, str):
            return (val, entity_id)
        if isinstance(val, dict):
            inner = [k for k in val.keys() if k not in control_keys]
            if inner:
                return (inner[0], entity_id)
        # Fallback to the literal key name
        return ("entity_name", entity_id)

    # Otherwise return the first non-control key (this is usually the real entity name)
    return (candidates[0], entity_id)


def _delete_objects_for_entity(entity_name):
    """Best-effort delete of every object of one entity. Returns #deleted."""
    try:
        response = get_all_objects_for_system_dynamic_entity(entity_name, token=DIRECTLOGIN_TOKEN)
    except Exception as e:
        logger.error(f"  ✗ API error while fetching objects for {entity_name}: {e}")
        return 0
    if response is None:
        return 0  # entity already gone (404)

    objects = response.get(f"{entity_name.lower()}_list", [])
    if not objects:
        return 0

    id_key = f"{entity_name.lower()}_id"
    object_ids = [x[id_key] for x in objects if id_key in x]
    deleted = 0
    for obj_id in object_ids:
        try:
            delete_object_for_system_dynamic_entity(entity_name, obj_id, token=DIRECTLOGIN_TOKEN)
            logger.info(f"  ✓ Deleted object {entity_name}/{obj_id}")
            deleted += 1
        except Exception as e:
            # A reference (FK) constraint can block this until the referencing
            # object is gone; a later pass will retry.
            logger.warning(f"  ⏳ Could not delete object {entity_name}/{obj_id} yet: {e}")
    return deleted


def wipe_all_dynamic_entities():
    """Delete every system dynamic entity (objects + definitions).

    Repeats in passes because foreign-key (reference) constraints can make
    deletion order matter: a parent entity/object cannot be removed while a
    child still references it. Each pass deletes whatever it can; we stop once
    nothing remains, or once a pass makes no progress (stuck).

    Returns True if the instance is fully clean afterwards, else False.
    """
    for pass_num in range(1, MAX_PASSES + 1):
        try:
            entities = get_all_system_dynamic_entities(token=DIRECTLOGIN_TOKEN)["dynamic_entities"]
        except Exception as e:
            logger.error(f"✗ Failed to list dynamic entities: {e}")
            return False

        if not entities:
            logger.info(f"✓ No dynamic entities remain (clean after {pass_num - 1} pass(es)).")
            return True

        logger.info(f"--- Pass {pass_num}/{MAX_PASSES}: {len(entities)} entity definition(s) remaining ---")
        progress = 0

        # Delete objects first (frees object-level FK references), then definitions.
        for entity in entities:
            entity_name, _ = _extract_entity_name_and_id(entity)
            progress += _delete_objects_for_entity(entity_name)

        for entity in entities:
            entity_name, entity_id = _extract_entity_name_and_id(entity)
            if entity_id == "N/A":
                logger.error(f"  ✗ Missing entity id for {entity_name}, cannot delete definition")
                continue
            try:
                delete_system_dynamic_entity(entity_id, token=DIRECTLOGIN_TOKEN)
                logger.info(f"  ✓ Deleted entity definition: {entity_name} (ID: {entity_id})")
                progress += 1
            except Exception as e:
                # Likely blocked by a reference from another entity's schema/data;
                # a later pass will retry once that other entity is gone.
                logger.warning(f"  ⏳ Could not delete entity {entity_name} yet: {e}")

        if progress == 0:
            logger.error(
                f"✗ Pass {pass_num} made no progress while {len(entities)} entit(y/ies) remain. "
                "Stopping to avoid an infinite loop."
            )
            return False

    # Exhausted MAX_PASSES — verify whether anything is left.
    try:
        remaining = get_all_system_dynamic_entities(token=DIRECTLOGIN_TOKEN)["dynamic_entities"]
    except Exception as e:
        logger.error(f"✗ Failed final verification: {e}")
        return False
    if remaining:
        logger.error(f"✗ Still {len(remaining)} entit(y/ies) after {MAX_PASSES} passes.")
        return False
    return True


def main():
    logger.info("Starting Delete ALL Dynamic Entities Script")
    logger.warning("⚠️  WARNING: This will delete ALL system dynamic entities and their data!")
    print_separator()

    clean = wipe_all_dynamic_entities()

    print_separator()
    if clean:
        logger.info("✓ Delete ALL Dynamic Entities Script Completed — instance is clean")
        print_separator("=")
        return 0

    # Surface the names of whatever survived, then fail with a non-zero exit so
    # callers (e.g. recreate_ogcr_entities.sh under `set -e`) abort instead of
    # recreating on top of a dirty instance.
    try:
        leftover = get_all_system_dynamic_entities(token=DIRECTLOGIN_TOKEN)["dynamic_entities"]
        names = ", ".join(_extract_entity_name_and_id(e)[0] for e in leftover)
        logger.error(f"✗ Wipe incomplete. Remaining: {names}")
    except Exception:
        logger.error("✗ Wipe incomplete and could not list remaining entities.")
    print_separator("=")
    return 1


if __name__ == "__main__":
    sys.exit(main())