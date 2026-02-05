import logging
from get_and_delete_dynamic_entities import (
    get_all_system_dynamic_entities,
    get_all_objects_for_system_dynamic_entity,
    delete_object_for_system_dynamic_entity,
    delete_system_dynamic_entity
)
from obp_client import token, obp_host

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


def main():
    logger.info("Starting Delete ALL Dynamic Entities Script")
    logger.warning("⚠️  WARNING: This will delete ALL system dynamic entities!")
    print_separator()
    
    # =========================================================================
    # STEP 1: Get all dynamic entities
    # =========================================================================
    logger.info("STEP 1: Retrieving all dynamic entities")
    print_separator("-")
    
    try:
        response = get_all_system_dynamic_entities(token=DIRECTLOGIN_TOKEN)
        all_dynamic_entities = response["dynamic_entities"]
        logger.info(f"✓ Found {len(all_dynamic_entities)} total dynamic entities")
    except Exception as e:
        logger.error(f"✗ Failed to retrieve dynamic entities: {e}")
        return
    
    if not all_dynamic_entities:
        logger.info("No dynamic entities found. Nothing to delete.")
        print_separator()
        return
    
    # Log all entity names
    logger.info("Dynamic entities to be deleted:")
    for idx, entity in enumerate(all_dynamic_entities, 1):
        entity_name, entity_id = _extract_entity_name_and_id(entity)
        logger.info(f"  [{idx}] {entity_name} (ID: {entity_id})")
    
    print_separator()
    
    # =========================================================================
    # STEP 2: Delete all entity objects for each dynamic entity
    # =========================================================================
    logger.info("STEP 2: Deleting all entity objects")
    print_separator("-")
    
    total_objects_deleted = 0
    total_objects_failed = 0
    
    for idx, entity in enumerate(all_dynamic_entities, 1):
        entity_name, _ = _extract_entity_name_and_id(entity)
        logger.info(f"[{idx}/{len(all_dynamic_entities)}] Processing entity: {entity_name}")
        
        try:
            response = get_all_objects_for_system_dynamic_entity(entity_name, token=DIRECTLOGIN_TOKEN)
            # Handle case where the list key might not exist (no objects)
            objects = response.get(f"{entity_name.lower()}_list", [])
            
            if not objects:
                logger.info(f"  → No objects found for {entity_name}")
                continue
            
            logger.info(f"  ✓ Found {len(objects)} object(s) for {entity_name}")
            
        except Exception as e:
            # This is an actual error (API failure, auth issue, etc.)
            logger.error(f"  ✗ API error while fetching objects for {entity_name}: {e}")
            continue
        
        object_ids = [x[f'{entity_name.lower()}_id'] for x in objects]
        logger.info(f"  → Object IDs: {', '.join(object_ids[:5])}{' ...' if len(object_ids) > 5 else ''}")
        
        for obj_idx, obj_id in enumerate(object_ids, 1):
            try:
                delete_object_for_system_dynamic_entity(entity_name, obj_id, token=DIRECTLOGIN_TOKEN)
                logger.info(f"  ✓ [{obj_idx}/{len(object_ids)}] Deleted object: {obj_id}")
                total_objects_deleted += 1
            except Exception as e:
                logger.error(f"  ✗ [{obj_idx}/{len(object_ids)}] Failed to delete object {obj_id}: {e}")
                total_objects_failed += 1
        
        logger.info("")  # Empty line for readability
    
    print_separator("-")
    logger.info(f"Object Deletion Summary: {total_objects_deleted} deleted, {total_objects_failed} failed")
    print_separator()
    
    # =========================================================================
    # STEP 3: Delete all dynamic entity definitions
    # =========================================================================
    logger.info("STEP 3: Deleting all dynamic entity definitions")
    print_separator("-")
    
    total_entities_deleted = 0
    total_entities_failed = 0
    
    for idx, entity in enumerate(all_dynamic_entities, 1):
        entity_name, entity_id = _extract_entity_name_and_id(entity)

        try:
            if entity_id == "N/A":
                logger.error(f"  ✗ [{idx}/{len(all_dynamic_entities)}] Missing entity id for {entity_name}, skipping")
                total_entities_failed += 1
                continue

            delete_system_dynamic_entity(entity_id, token=DIRECTLOGIN_TOKEN)
            logger.info(f"  ✓ [{idx}/{len(all_dynamic_entities)}] Deleted entity: {entity_name} (ID: {entity_id})")
            total_entities_deleted += 1
        except Exception as e:
            logger.error(f"  ✗ [{idx}/{len(all_dynamic_entities)}] Failed to delete entity {entity_name}: {e}")
            total_entities_failed += 1
    
    print_separator("-")
    logger.info(f"Entity Deletion Summary: {total_entities_deleted} deleted, {total_entities_failed} failed")
    print_separator()
    
    logger.info("Delete ALL Dynamic Entities Script Completed")
    print_separator("=")


if __name__ == "__main__":
    main()