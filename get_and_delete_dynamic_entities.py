import requests
import logging
from obp_client import token, obp_host

# Configure logging
logger = logging.getLogger(__name__)

# Configuration
BASE_URL = obp_host  # Replace with your OBP instance URL
DIRECTLOGIN_TOKEN = token  # Optional: Replace with your DirectLogin token



def get_all_system_dynamic_entities(token=None):
	"""
	Get all system-level dynamic entities in OBP.

	Args:
		token (str, optional): DirectLogin authentication token

	Returns:
		dict: The API response
	"""
	url = f"{BASE_URL}/obp/v6.0.0/management/system-dynamic-entities"

	headers = {
		"Content-Type": "application/json"
	}

	# Add authentication if token is provided
	if token:
		headers["Authorization"] = f"DirectLogin token={token}"

	try:
		response = requests.get(url, headers=headers)
		response.raise_for_status()
		return response.json()
	except requests.exceptions.RequestException as e:
		logger.error(f"Error getting system dynamic entity: {e}")
		if hasattr(e.response, 'text'):
			logger.error(f"Response: {e.response.text}")
		raise

def get_all_objects_for_system_dynamic_entity(entity_name, token=None):
	"""
	Get all system-level dynamic entities in OBP.

	Args:
		token (str, optional): DirectLogin authentication token

	Returns:
		dict: The API response, or None if entity doesn't exist (404)
	"""
	url = f"{BASE_URL}/obp/dynamic-entity/{entity_name}"

	headers = {
		"Content-Type": "application/json"
	}

	# Add authentication if token is provided
	if token:
		headers["Authorization"] = f"DirectLogin token={token}"

	try:
		response = requests.get(url, headers=headers)
		response.raise_for_status()
		return response.json()
	except requests.exceptions.HTTPError as e:
		# 404 means entity doesn't exist yet - this is fine
		if e.response.status_code == 404:
			logger.info(f"Entity {entity_name} does not exist (404) - skipping")
			return None
		# For other HTTP errors, log and raise
		logger.error(f"Error getting system dynamic entity: {e}")
		if hasattr(e.response, 'text'):
			logger.error(f"Response: {e.response.text}")
		raise
	except requests.exceptions.RequestException as e:
		logger.error(f"Error getting system dynamic entity: {e}")
		raise

def delete_object_for_system_dynamic_entity(entity_name, object_id, token=None):

	url = f"{BASE_URL}/obp/dynamic-entity/{entity_name}/{object_id}"

	headers = {
		"Content-Type": "application/json"
	}

	# Add authentication if token is provided
	if token:
		headers["Authorization"] = f"DirectLogin token={token}"

	try:
		response = requests.delete(url, headers=headers)
		response.raise_for_status()
		return response.json()
	except requests.exceptions.RequestException as e:
		logger.error(f"Error deleting system dynamic entity object: {e}")
		if hasattr(e.response, 'text'):
			logger.error(f"Response: {e.response.text}")
		raise

def delete_system_dynamic_entity(entity_id, token=None):

	url = f"{BASE_URL}/obp/v6.0.0/management/system-dynamic-entities/{entity_id}"

	headers = {
		"Content-Type": "application/json"
	}

	# Add authentication if token is provided
	if token:
		headers["Authorization"] = f"DirectLogin token={token}"

	try:
		response = requests.delete(url, headers=headers)
		response.raise_for_status()
		return response.json()
	except requests.exceptions.RequestException as e:
		logger.error(f"Error deleting system dynamic entity: {e}")
		if hasattr(e.response, 'text'):
			logger.error(f"Response: {e.response.text}")
		raise

