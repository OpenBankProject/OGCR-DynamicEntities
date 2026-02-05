import logging
from obp_client import token, obp_host


from get_and_delete_dynamic_entities import (
	get_all_system_dynamic_entities,
	get_all_objects_for_system_dynamic_entity,
	delete_object_for_system_dynamic_entity,
	delete_system_dynamic_entity)
from dynamic_entities import (
	create_all_entities,
	ENTITY_PROJECT,
	ENTITY_PARCEL,
	ENTITY_PARCEL_OWNERSHIP_VERIFICATION,
	ENTITY_PROJECT_PARCEL_VERIFICATION,
	ENTITY_PROJECT_VERIFICATION,
	ENTITY_PARCEL_MONITORING_PERIOD_VERIFICATION,
	ENTITY_PROJECT_MONITORING_PERIOD_VERIFICATION
)

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

my_dynamic_entities_names = [
	ENTITY_PROJECT,
	ENTITY_PARCEL,
	ENTITY_PARCEL_OWNERSHIP_VERIFICATION,
	ENTITY_PROJECT_PARCEL_VERIFICATION,
	ENTITY_PROJECT_VERIFICATION,
	ENTITY_PARCEL_MONITORING_PERIOD_VERIFICATION,
	ENTITY_PROJECT_MONITORING_PERIOD_VERIFICATION
]


def print_separator(char="=", length=80):
	"""Print a separator line for better visual separation"""
	logger.info(char * length)


def main():
	logger.info("Starting Dynamic Entities Management Script")
	print_separator()

	# =========================================================================
	# STEP 1: Delete all entity objects for each dynamic entity
	# =========================================================================
	logger.info("STEP 1: Deleting entity objects")
	print_separator("-")
	
	total_objects_deleted = 0
	total_objects_failed = 0
	
	for name in my_dynamic_entities_names:
		logger.info(f"Processing entity: {name}")
		
		try:
			response = get_all_objects_for_system_dynamic_entity(name, token=DIRECTLOGIN_TOKEN)
			
			# If response is None, entity doesn't exist (404) - skip it
			if response is None:
				logger.info(f"  → Entity {name} does not exist yet - skipping")
				continue
			
			# Handle case where the list key might not exist (no objects)
			objects = response.get(f"{name.lower()}_list", [])
			
			if not objects:
				logger.info(f"  → No objects found for {name}")
				continue
			
			logger.info(f"  ✓ Found {len(objects)} object(s) for {name}")
			
		except Exception as e:
			# This is an actual error (API failure, auth issue, etc.)
			logger.error(f"  ✗ API error while fetching objects for {name}: {e}")
			continue
		
		object_ids = [x[f'{name.lower()}_id'] for x in objects]
		logger.info(f"  → Object IDs: {', '.join(object_ids)}")
		
		for idx, obj_id in enumerate(object_ids, 1):
			try:
				delete_object_for_system_dynamic_entity(name, obj_id, token=DIRECTLOGIN_TOKEN)
				logger.info(f"  ✓ [{idx}/{len(object_ids)}] Deleted object: {obj_id}")
				total_objects_deleted += 1
			except Exception as e:
				logger.error(f"  ✗ [{idx}/{len(object_ids)}] Failed to delete object {obj_id}: {e}")
				total_objects_failed += 1
		
		logger.info("")  # Empty line for readability
	
	print_separator("-")
	logger.info(f"Object Deletion Summary: {total_objects_deleted} deleted, {total_objects_failed} failed")
	print_separator()
	
	# =========================================================================
	# STEP 2: Delete the dynamic entities themselves
	# =========================================================================
	logger.info("STEP 2: Deleting dynamic entity definitions")
	print_separator("-")
	
	try:
		all_dynamic_entities = get_all_system_dynamic_entities(token=DIRECTLOGIN_TOKEN)["dynamic_entities"]
		logger.info(f"Retrieved {len(all_dynamic_entities)} total dynamic entities from system")
	except Exception as e:
		logger.error(f"Failed to retrieve dynamic entities: {e}")
		return

	# Debug: show all entity names from API
	logger.info("Entity names from API:")
	for entity in all_dynamic_entities:
		keys = list(entity.keys())
		logger.info(f"  Keys: {keys}")

	# Debug: show what we're looking for
	logger.info(f"Looking for these entity names: {my_dynamic_entities_names}")

	my_dynamic_entities = [x for x in all_dynamic_entities if list(x.keys())[1] in my_dynamic_entities_names]
	my_dynamic_entities_ids = [x["dynamicEntityId"] for x in my_dynamic_entities]

	logger.info(f"Found {len(my_dynamic_entities_ids)} matching entities to delete")
	
	if not my_dynamic_entities_ids:
		logger.info("No matching entities found to delete")
	else:
		total_entities_deleted = 0
		total_entities_failed = 0
		
		for idx, entity_id in enumerate(my_dynamic_entities_ids, 1):
			try:
				delete_system_dynamic_entity(entity_id, token=DIRECTLOGIN_TOKEN)
				logger.info(f"  ✓ [{idx}/{len(my_dynamic_entities_ids)}] Deleted entity: {entity_id}")
				total_entities_deleted += 1
			except Exception as e:
				logger.error(f"  ✗ [{idx}/{len(my_dynamic_entities_ids)}] Failed to delete entity {entity_id}: {e}")
				total_entities_failed += 1
		
		print_separator("-")
		logger.info(f"Entity Deletion Summary: {total_entities_deleted} deleted, {total_entities_failed} failed")
	
	print_separator()
	
	# =========================================================================
	# STEP 3: (Re)create all dynamic entities
	# =========================================================================
	logger.info("STEP 3: Creating dynamic entities")
	print_separator("-")
	
	try:
		create_all_entities()
	except Exception as e:
		logger.error(f"Error during entity creation: {e}")
	
	print_separator()
	logger.info("Dynamic Entities Management Script Completed")
	print_separator("=")


if __name__ == "__main__":
	main()