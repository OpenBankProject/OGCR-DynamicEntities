import logging
from obp_client import token, obp_host
from get_and_delete_dynamic_entities import get_all_objects_for_system_dynamic_entity
from dynamic_entities import (
    ENTITY_PROJECT,
    ENTITY_PARCEL,
    ENTITY_PARCEL_OWNERSHIP_VERIFICATION,
    ENTITY_PROJECT_PARCEL_VERIFICATION,
    ENTITY_PROJECT_VERIFICATION,
    ENTITY_PARCEL_MONITORING_PERIOD_VERIFICATION,
    ENTITY_PROJECT_MONITORING_PERIOD_VERIFICATION,
    get_list_key
)
import json

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

# All entities to retrieve
ENTITIES = [
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


def format_json(data):
    """Format data as indented JSON string"""
    return json.dumps(data, indent=2)


def display_record(record, entity_name, indent="    "):
    """Display a single record in a readable format"""
    for key, value in record.items():
        if isinstance(value, dict):
            logger.info(f"{indent}{key}:")
            for sub_key, sub_value in value.items():
                logger.info(f"{indent}  {sub_key}: {sub_value}")
        elif isinstance(value, str) and len(value) > 60:
            # Truncate long strings (like geo_data)
            logger.info(f"{indent}{key}: {value[:60]}...")
        else:
            logger.info(f"{indent}{key}: {value}")


def main():
    logger.info("Starting Get All Data Script")
    print_separator()
    
    all_data = {}
    total_records = 0
    
    # =========================================================================
    # Retrieve data from all entities
    # =========================================================================
    logger.info("Retrieving data from all dynamic entities")
    print_separator("-")
    
    for idx, entity_name in enumerate(ENTITIES, 1):
        logger.info(f"[{idx}/{len(ENTITIES)}] Fetching: {entity_name}")
        
        try:
            response = get_all_objects_for_system_dynamic_entity(
                entity_name,
                token=DIRECTLOGIN_TOKEN
            )
            
            # If response is None, entity doesn't exist (404) - skip it
            if response is None:
                logger.info(f"  → Entity {entity_name} does not exist yet - skipping")
                all_data[entity_name] = []
                continue
            
            # Handle case where the list key might not exist (no objects)
            # The key format is: prefix_entityname_list (with underscores between each part)
            # e.g., "project_list" for project
            list_key = get_list_key(entity_name)
            objects = response.get(list_key, [])
            
            if not objects:
                logger.info(f"  → No records found for {entity_name}")
                all_data[entity_name] = []
                continue
            
            logger.info(f"  ✓ Found {len(objects)} record(s)")
            all_data[entity_name] = objects
            total_records += len(objects)
            
            # Display summary of records
            for record_idx, record in enumerate(objects, 1):
                logger.info(f"  Record #{record_idx}:")
                display_record(record, entity_name)
                logger.info("")  # Empty line between records
            
        except Exception as e:
            logger.error(f"  ✗ Error fetching {entity_name}: {e}")
            all_data[entity_name] = []
            continue
        
        logger.info("")  # Empty line between entities
    
    print_separator("-")
    logger.info(f"Total records retrieved: {total_records}")
    print_separator()
    
    # =========================================================================
    # Summary by entity
    # =========================================================================
    logger.info("SUMMARY BY ENTITY")
    print_separator("-")
    
    for entity_name in ENTITIES:
        count = len(all_data.get(entity_name, []))
        logger.info(f"  {entity_name:<30} {count:>3} record(s)")
    
    print_separator()
    
    # =========================================================================
    # Optional: Save to JSON file
    # =========================================================================
    try:
        output_file = "all_dynamic_entities_data.json"
        with open(output_file, 'w') as f:
            json.dump(all_data, f, indent=2)
        logger.info(f"✓ Data saved to: {output_file}")
    except Exception as e:
        logger.error(f"✗ Failed to save data to file: {e}")
    
    print_separator()
    logger.info("Get All Data Script Completed")
    print_separator("=")
    
    return all_data


if __name__ == "__main__":
    main()