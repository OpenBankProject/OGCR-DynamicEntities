import requests
import logging
import json
from obp_client import token, obp_host
from dotenv import load_dotenv
import os

# Configure logging
logger = logging.getLogger(__name__)
# Configuration
BASE_URL = obp_host  # Replace with your OBP instance URL
DIRECTLOGIN_TOKEN = token  # Optional: Replace with your DirectLogin token
load_dotenv()
PREFIX = os.getenv('OBP_ENTITY_PREFIX', '').lower()
if PREFIX != '':
	if not PREFIX.endswith("_"):
		PREFIX = PREFIX + "_"
# Entity name constants
ENTITY_PROJECT = f"{PREFIX}project"
ENTITY_PARCEL = f"{PREFIX}parcel"
ENTITY_PARCEL_OWNERSHIP_VERIFICATION = f"{PREFIX}parcel_owner_verification"
ENTITY_PROJECT_PARCEL_VERIFICATION = f"{PREFIX}project_parcel_verification"
ENTITY_PROJECT_VERIFICATION = f"{PREFIX}project_verification"
ENTITY_PARCEL_MONITORING_PERIOD_VERIFICATION = f"{PREFIX}parcel_monitoring_period_verification"
ENTITY_PROJECT_MONITORING_PERIOD_VERIFICATION = f"{PREFIX}project_monitoring_period_verification"

# Helper functions to get response keys and ID keys from entity constants
def get_response_key(entity_constant):
	"""
	Get the response key from an entity constant.
	E.g., 'ogcr3_project' -> 'ogcr3_project'
	"""
	return entity_constant.lower()

def get_id_key(entity_constant):
	"""
	Get the ID key from an entity constant.
	E.g., 'ogcr3_project' -> 'ogcr3_project_id'
	"""
	return f"{entity_constant.lower()}_id"

def get_list_key(entity_constant):
	"""
	Get the list key from an entity constant.
	E.g., 'ogcr3_project' -> 'ogcr3_project_list'
	"""
	return f"{entity_constant.lower()}_list"

def create_system_dynamic_entity(entity_definition, token=None):
	"""
	Create a system-level dynamic entity in OBP.

	Accepts the legacy {entity_name, has_personal_entity, definition} shape and
	converts it to the format OBP actually expects: {hasPersonalEntity, <name>: schema}.

	Args:
		entity_definition (dict): The dynamic entity definition
		token (str, optional): DirectLogin authentication token

	Returns:
		dict: The API response
	"""
	url = f"{BASE_URL}/obp/v5.1.0/management/system-dynamic-entities"

	# Convert legacy format to OBP-expected format if needed
	if "entity_name" in entity_definition and "definition" in entity_definition:
		name = entity_definition["entity_name"]
		has_personal = entity_definition.get("has_personal_entity", False)
		payload = {
			"hasPersonalEntity": has_personal,
			name: entity_definition["definition"],
		}
	else:
		payload = entity_definition

	headers = {
		"Content-Type": "application/json"
	}

	# Add authentication if token is provided
	if token:
		headers["Authorization"] = f"DirectLogin token={token}"

	try:
		response = requests.post(url, headers=headers, json=payload)
		response.raise_for_status()
		return response.json()
	except requests.exceptions.RequestException as e:
		logger.error(f"Error creating system dynamic entity: {e}")
		logger.error(f"Request URL: {url}")
		logger.error(f"Request body:\n{json.dumps(payload, indent=2)}")
		if hasattr(e, 'response') and e.response is not None:
			logger.error(f"Response: {e.response.text}")
		raise


# Example 1: Customer Preferences Entity
project_entity = {
	"entity_name": ENTITY_PROJECT,
	"has_personal_entity": False,
	"definition": {
		"description": "a carbon credit project",
		"required": [
			"project_name",
			"project_operator_name"
		],
		"properties": {
			"project_operator_name": {
				"type": "string",
				"example": "Hugo Muller",
				"description": "Name of the project operator / entity managing the project"
			},
			"project_operator_email": {
				"type": "string",
				"example": "hugo@example.com",
				"description": "Contact email for the project operator"
			},
			"project_operator_phone": {
				"type": "string",
				"example": "+49 151 1234567",
				"description": "Contact phone number for the project operator"
			},
			"project_operator_address_line_1": {
				"type": "string",
				"example": "Musterstrasse 1",
				"description": "Operator address line 1"
			},
			"project_operator_address_line_2": {
				"type": "string",
				"example": "Suite 42",
				"description": "Operator address line 2 (optional)"
			},
			"project_operator_postcode": {
				"type": "string",
				"example": "10115",
				"description": "Operator postal code"
			},
			"project_operator_country": {
				"type": "string",
				"example": "Germany",
				"description": "Operator country"
			},
			"project_name": {
				"type": "string",
				"example": "Example Carbon Project",
				"description": "Readable name of the project"
			},
			"project_summary": {
				"type": "string",
				"example": "Smallholder agroforestry restoration on degraded land",
				"description": "Short summary of the project"
			},
			"project_description": {
				"type": "string",
				"example": "A longer description with objectives, scope and impact",
				"description": "Detailed description of the project"
			},
			"project_website": {
				"type": "string",
				"example": "https://example.org/project",
				"description": "Optional website URL for the project"
			},
			"project_image": {
				"type": "string",
				"example": "https://example.org/image.jpg",
				"description": "URL to a representative image for the project"
			},
			"project_media_links": {
				"type": "json",
				"items": { "type": "string" },
				"example": ["https://example.org/video.mp4", "https://example.org/doc.pdf"],
				"description": "List of media links (videos, documents, etc.)"
			},
			"project_activity_type": {
				"type": "string",
				"example": "Agroforestry",
				"description": "High level activity type for the project"
			},
			"project_type": {
				"type": "string",
				"example": "Reforestation",
				"description": "Project classification / type"
			},
			"project_city": {
				"type": "string",
				"example": "Berlin",
				"description": "City where the project is located (if applicable)"
			},
			"project_country": {
				"type": "string",
				"example": "Germany",
				"description": "Country where the project is located"
			},
			"project_cobenefits": {
				"type": "json",
				"items": { "type": "string" },
				"example": ["biodiversity", "water retention"],
				"description": "List of co-benefits produced by the project"
			},
			"project_activity_plan": {
				"type": "string",
				"example": "Planned activities and schedule",
				"description": "Narrative or link describing the activity plan"
			},
			"project_start_date": {
				"type": "string",
				"example": "2024-01-01",
				"description": "Project start date (ISO 8601)"
			},
			"project_end_date": {
				"type": "string",
				"example": "2034-12-31",
				"description": "Project end date (ISO 8601)"
			},
			"project_term_commitment": {
				"type": "integer",
				"example": 10,
				"description": "Term commitment (years)"
			},
			"project_methodology": {
				"type": "string",
				"example": "Methodology name or reference",
				"description": "Methodology applied for carbon accounting"
			},
			"monitoring_period_years": {
				"type": "integer",
				"example": 5,
				"description": "Number of years per monitoring period"
			},
			"monitoring_period_start_date": {
				"type": "string",
				"example": "2024-01-01",
				"description": "Monitoring period start date (ISO 8601)"
			},
			"monitoring_period_end_date": {
				"type": "string",
				"example": "2029-12-31",
				"description": "Monitoring period end date (ISO 8601)"
			}
		}
	}
}

parcel_entity = {
	"entity_name": ENTITY_PARCEL,
	"has_personal_entity": False,
	"definition": {
		"description": "a piece of land",
		"required": [
			f"{ENTITY_PROJECT}_id",
			"parcel_owner",
			"geo_data"
		],
		"properties": {
			f"{ENTITY_PROJECT}_id": {
				"type": f"reference:{ENTITY_PROJECT}",
				"example": "a8770fca-3d1d-47af-b6d0-7a6c3f124388",
				"description": "ID of the project this parcel belongs to"
			},
			"parcel_owner": {
				"type": "string",
				"example": "hugo muller passport nr. 1234444",
				"description": "legal identifier of landholder"
			},
			"geo_data": {
				"type": "string",
				"example": "some_geo_json",
				"description": "a geojson polygon"
			}
		}
	}
}

parcel_ownership_verification_entity = {
	"entity_name": ENTITY_PARCEL_OWNERSHIP_VERIFICATION,
	"has_personal_entity": False,
	"definition": {
		"description": "Verification of Landownership",
		"required": [
			f"{ENTITY_PARCEL}_id"
		],
		"properties": {
			f"{ENTITY_PARCEL}_id": {
				"type": f"reference:{ENTITY_PARCEL}",
				"example": "3dece208-c95c-11f0-9041-54e1adfac5b1",
				"description": "(uu)id of the parcel that gets verified"
			},
			"status_code": {
				"type": "string",
				"example": "verified",
				"description": "in_progress, verified, failed"
			},
			"status_message": {
				"type": "string",
				"example": "could not find owner",
				"description": "further explanation of status code"
			},
			"authority": {
				"type": "string",
				"example": "Mycountry cadastre",
				"description": "name of  authority that verified the ownership"
			}
		}
	}
}

parcel_verification_entity = {
	"entity_name": ENTITY_PROJECT_PARCEL_VERIFICATION,
	"has_personal_entity": False,
	"definition": {
		"description": "Verification of Project Claim Estimation",
		"required": [
			f"{ENTITY_PARCEL}_id",
			f"{ENTITY_PROJECT}_id"
		],
		"properties": {
			f"{ENTITY_PARCEL}_id": {
				"type": f"reference:{ENTITY_PARCEL}",
				"example": "3dece208-c95c-11f0-9041-54e1adfac5b1",
				"description": "(uu)id of the parcel that gets verified"
			},
			f"{ENTITY_PROJECT}_id": {
				"type": f"reference:{ENTITY_PROJECT}",
				"example": "3dece208-c95c-11f0-9041-54e1adfac5b1",
				"description": "ID of the project this parcel belongs to"
			},
			"status_code": {
				"type": "string",
				"example": "verified",
				"description": "in_progress, verified, failed"
			},
			"status_message": {
				"type": "string",
				"example": "x behaved badly",
				"description": "further explanation of status code"
			},
			"amount": {
				"type": "integer",
				"example": 6,
				"description": "amount of carbon reduction calculated"
			}
		}
	}
}

project_verification_entity = {
	"entity_name": ENTITY_PROJECT_VERIFICATION,
	"has_personal_entity": False,
	"definition": {
		"description": "Verification of Project",
		"required": [
			f"{ENTITY_PROJECT}_id"
		],
		"properties": {
			f"{ENTITY_PROJECT}_id": {
				"type": f"reference:{ENTITY_PROJECT}",
				"example": "3dece208-c95c-11f0-9041-54e1adfac5b1",
				"description": "ID of the project verified"
			},
			"status_code": {
				"type": "string",
				"example": "verified",
				"description": "in_progress, verified, failed"
			},
			"status_message": {
				"type": "string",
				"example": "x behaved badly",
				"description": "further explanation of status code"
			}
		}
	}
}

parcel_monitoring_period_verification = {
	"entity_name": ENTITY_PARCEL_MONITORING_PERIOD_VERIFICATION,
	"has_personal_entity": False,
	"definition": {
		"description": "Verification of Project Claim",
		"required": [
			f"{ENTITY_PARCEL}_id",
			f"{ENTITY_PROJECT}_id"
		],
		"properties": {
			f"{ENTITY_PARCEL}_id": {
				"type": f"reference:{ENTITY_PARCEL}",
				"example": "3dece208-c95c-11f0-9041-54e1adfac5b1",
				"description": "(uu)id of the parcel that gets verified"
			},
			f"{ENTITY_PROJECT}_id": {
				"type": f"reference:{ENTITY_PROJECT}",
				"example": "3dece208-c95c-11f0-9041-54e1adfac5b1",
				"description": "ID of the project this parcel belongs to"
			},
			"status_code": {
				"type": "string",
				"example": "verified",
				"description": "in_progress, verified, failed"
			},
			"status_message": {
				"type": "string",
				"example": "x behaved badly",
				"description": "further explanation of status code"
			},
			"amount": {
				"type": "integer",
				"example": 6,
				"description": "amount of carbon reduction calculated"
			}
		}
	}
}

project_monitoring_period_verification = {
	"entity_name": ENTITY_PROJECT_MONITORING_PERIOD_VERIFICATION,
	"has_personal_entity": False,
	"definition": {
		"description": "Verification of Project",
		"required": [
			f"{ENTITY_PROJECT}_id"
		],
		"properties": {
			f"{ENTITY_PROJECT}_id": {
				"type": f"reference:{ENTITY_PROJECT}",
				"example": "3dece208-c95c-11f0-9041-54e1adfac5b1",
				"description": "ID of the project verified"
			},
			"status_code": {
				"type": "string",
				"example": "verified",
				"description": "in_progress, verified, failed"
			},
			"status_message": {
				"type": "string",
				"example": "x behaved badly",
				"description": "further explanation of status code"
			}
		}
	}
}

entities_data = [
	(ENTITY_PROJECT, project_entity),
	(ENTITY_PARCEL, parcel_entity),
	(ENTITY_PARCEL_OWNERSHIP_VERIFICATION, parcel_ownership_verification_entity),
	(ENTITY_PROJECT_PARCEL_VERIFICATION, parcel_verification_entity),
	(ENTITY_PROJECT_VERIFICATION, project_verification_entity),
	(ENTITY_PARCEL_MONITORING_PERIOD_VERIFICATION, parcel_monitoring_period_verification),
	(ENTITY_PROJECT_MONITORING_PERIOD_VERIFICATION, project_monitoring_period_verification)
	]

def create_all_entities():

	created_count = 0
	failed_count = 0

	for idx, (entity_name, entity) in enumerate(entities_data, 1):
		try:
			response = create_system_dynamic_entity(entity, DIRECTLOGIN_TOKEN)
			entity_id = response.get('dynamic_entity_id', 'N/A')
			logger.info(f"  ✓ [{idx}/{len(entities_data)}] Created entity: {entity_name} (ID: {entity_id})")
			created_count += 1
		except Exception as e:
			logger.error(f"  ✗ [{idx}/{len(entities_data)}] Failed to create entity {entity_name}")
			logger.error(f"      Error details: {e}")
			# The detailed request is already logged by create_system_dynamic_entity()
			failed_count += 1

	logger.info("")
	logger.info(f"Entity Creation Summary: {created_count} created, {failed_count} failed")


def add_entitlement_to_user(token, user_id, role_name, bank_id=""):
	"""
	Add an entitlement (role) to a specific user

	Args:
		token: DirectLogin authentication token
		user_id: The ID of the user to grant the role to
		role_name: The name of the role to grant (e.g., "CanGetAnyUser")
		bank_id: Bank ID for bank-level roles, empty string "" for system-level roles

	Returns:
		Response JSON from the API
	"""
	url = f"{BASE_URL}/obp/v6.0.0/users/{user_id}/entitlements"
	headers = {
		"Authorization": f"DirectLogin token={token}",
		"Content-Type": "application/json"
	}

	data = {
		"bank_id": bank_id,
		"role_name": role_name
	}

	try:
		response = requests.post(url, headers=headers, json=data)
	except requests.exceptions.RequestException as e:
		logger.error(f"Error adding entitlement to user: {e}")
	print(response)
	return response.json()


