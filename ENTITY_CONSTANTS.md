# Entity Constants and Helper Functions

## Overview

This document describes the entity constants and helper functions used throughout the OGCR Dynamic Entities project. All entity names are centralized in `dynamic_entities.py` to ensure consistency across the codebase.

## Configuration

Entity names have no prefix. `OBP_ENTITY_PREFIX` has been removed: to keep one set of OGCR entities apart from another, put them under a bank with `OBP_ENTITY_SPACE_ID` instead (see the README, "Where the entities live").

## Entity Name Constants

All entity constants are defined in `dynamic_entities.py` and should be imported wherever entity names are needed.

### Import Statement

```python
from dynamic_entities import (
    ENTITY_PROJECT,
    ENTITY_PARCEL,
    ENTITY_PARCEL_OWNERSHIP_VERIFICATION,
    ENTITY_PROJECT_PARCEL_VERIFICATION,
    ENTITY_PROJECT_VERIFICATION,
    ENTITY_PARCEL_MONITORING_PERIOD_VERIFICATION,
    ENTITY_PROJECT_MONITORING_PERIOD_VERIFICATION
)
```

### Available Constants

| Constant | Value | Description |
|----------|------------------------------|-------------|
| `ENTITY_PROJECT` | `project` | Carbon credit project |
| `ENTITY_PARCEL` | `parcel` | Land parcel |
| `ENTITY_PARCEL_OWNERSHIP_VERIFICATION` | `parcel_owner_verification` | Parcel ownership verification |
| `ENTITY_PROJECT_PARCEL_VERIFICATION` | `project_parcel_verification` | Project-parcel verification (baseline) |
| `ENTITY_PROJECT_VERIFICATION` | `project_verification` | Project verification |
| `ENTITY_PARCEL_MONITORING_PERIOD_VERIFICATION` | `parcel_monitoring_period_verification` | Parcel monitoring period verification |
| `ENTITY_PROJECT_MONITORING_PERIOD_VERIFICATION` | `project_monitoring_period_verification` | Project monitoring period verification |

## Helper Functions

Three helper functions are provided to generate consistent keys from entity constants:

### `get_response_key(entity_constant)`

Generates the response key from an entity constant. This is used when parsing API responses.

**Usage:**
```python
from dynamic_entities import ENTITY_PROJECT, get_response_key

response = create_dynamic_entity_object(ENTITY_PROJECT, data, token)
response_key = get_response_key(ENTITY_PROJECT)  # Returns: 'project'
project_obj = response[response_key]
```

### `get_id_key(entity_constant)`

Generates the ID key from an entity constant. This is used to extract object IDs from API responses.

**Usage:**
```python
from dynamic_entities import ENTITY_PROJECT, get_response_key, get_id_key

response = create_dynamic_entity_object(ENTITY_PROJECT, data, token)
response_key = get_response_key(ENTITY_PROJECT)
project_obj = response[response_key]

id_key = get_id_key(ENTITY_PROJECT)  # Returns: 'project_id'
project_id = project_obj[id_key]
```

### `get_list_key(entity_constant)`

Generates the list key from an entity constant. This is used when fetching multiple objects.

**Usage:**
```python
from dynamic_entities import ENTITY_PROJECT, get_list_key

response = get_all_objects_for_system_dynamic_entity(ENTITY_PROJECT, token)
list_key = get_list_key(ENTITY_PROJECT)  # Returns: 'project_list'
projects = response[list_key]
```

## Complete Example

Here's a complete example showing how to use entity constants and helper functions:

```python
from dynamic_entities import (
    ENTITY_PROJECT,
    get_response_key,
    get_id_key,
    get_list_key
)
from dynamic_entities_objects import create_dynamic_entity_object

# Create a new project
project_data = {
    "project_owner": "John Smith - Passport: US123456789"
}

response = create_dynamic_entity_object(
    ENTITY_PROJECT,  # Use constant instead of hardcoded string
    project_data,
    token
)

# Extract the project object using helper function
response_key = get_response_key(ENTITY_PROJECT)
project_obj = response[response_key]

# Extract the project ID using helper function
id_key = get_id_key(ENTITY_PROJECT)
project_id = project_obj[id_key]

print(f"Created project with ID: {project_id}")

# Later, fetch all projects
response = get_all_objects_for_system_dynamic_entity(ENTITY_PROJECT, token)
list_key = get_list_key(ENTITY_PROJECT)
all_projects = response[list_key]
```

## Entity Usage in Scripts

### `main.py`
- Uses all entity constants to manage the lifecycle of dynamic entities
- Creates, deletes, and recreates entities

### `create_dummy_data.py`
- Uses entity constants to create test data
- Uses helper functions to parse API responses

### `get_all_data.py`
- Uses entity constants to fetch all data
- Uses `get_list_key()` to extract object lists

### `dynamic_entities_objects.py`
- Uses entity constants in wrapper functions for creating entity objects

## Entity Hierarchy

```
Project (ENTITY_PROJECT)
├── Parcel (ENTITY_PARCEL)
│   ├── Parcel Ownership Verification (ENTITY_PARCEL_OWNERSHIP_VERIFICATION)
│   ├── Project-Parcel Verification (ENTITY_PROJECT_PARCEL_VERIFICATION)
│   └── Parcel Monitoring Period Verification (ENTITY_PARCEL_MONITORING_PERIOD_VERIFICATION)
├── Project Verification (ENTITY_PROJECT_VERIFICATION)
└── Project Monitoring Period Verification (ENTITY_PROJECT_MONITORING_PERIOD_VERIFICATION)
```

## Foreign Key Relationships

- `ENTITY_PARCEL.project_id` → `ENTITY_PROJECT`
- `ENTITY_PARCEL_OWNERSHIP_VERIFICATION.parcel_id` → `ENTITY_PARCEL`
- `ENTITY_PROJECT_PARCEL_VERIFICATION.parcel_id` → `ENTITY_PARCEL`
- `ENTITY_PROJECT_PARCEL_VERIFICATION.project_id` → `ENTITY_PROJECT`
- `ENTITY_PROJECT_VERIFICATION.project_id` → `ENTITY_PROJECT`
- `ENTITY_PARCEL_MONITORING_PERIOD_VERIFICATION.parcel_id` → `ENTITY_PARCEL`
- `ENTITY_PARCEL_MONITORING_PERIOD_VERIFICATION.project_id` → `ENTITY_PROJECT`
- `ENTITY_PROJECT_MONITORING_PERIOD_VERIFICATION.project_id` → `ENTITY_PROJECT`

## Best Practices

1. **Always use entity constants** - Never hardcode entity names as strings
2. **Use helper functions** - Use `get_response_key()`, `get_id_key()`, and `get_list_key()` for consistency
3. **Import from dynamic_entities** - All entity constants and helpers are in one place
4. **Configure via .env** - Change the prefix in `.env` file, not in code

## Migration Guide

If you have hardcoded entity names in your code, replace them as follows:

### Before (❌ Don't do this):
```python
# Hardcoded entity name
response = create_entity_object("project", data, token)
project_obj = response["project"]
project_id = project_obj["project_id"]
```

### After (✅ Do this):
```python
from dynamic_entities import ENTITY_PROJECT, get_response_key, get_id_key

# Use constants and helper functions
response = create_entity_object(ENTITY_PROJECT, data, token)
response_key = get_response_key(ENTITY_PROJECT)
project_obj = response[response_key]
id_key = get_id_key(ENTITY_PROJECT)
project_id = project_obj[id_key]
```

## Troubleshooting

### Issue: Entity names don't match API
**Solution:** Make sure you're using the entity constants from `dynamic_entities.py`, not hardcoded strings.

### Issue: "NameError: name 'ENTITY_...' is not defined"
**Solution:** Import the constant from `dynamic_entities`:
```python
from dynamic_entities import ENTITY_PROJECT  # or whichever constant you need
```
