import requests
from obp_client import token, obp_host
from obp_space import record_path
from dynamic_entities import (
	ENTITY_PROJECT,
	ENTITY_PARCEL,
	ENTITY_PARCEL_OWNERSHIP_VERIFICATION,
	ENTITY_PROJECT_PARCEL_VERIFICATION,
	ENTITY_PROJECT_VERIFICATION,
	ENTITY_PARCEL_MONITORING_PERIOD_VERIFICATION,
	ENTITY_PROJECT_MONITORING_PERIOD_VERIFICATION
)
# Configuration
BASE_URL = obp_host  # Replace with your OBP instance URL
DIRECTLOGIN_TOKEN = token  # Optional: Replace with your DirectLogin token

def create_entity_object(entity_name, payload, token=None):
	url = f"{BASE_URL}{record_path(entity_name)}"

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
		print(f"Error creating system dynamic entity object for {entity_name}: {e}")
		if hasattr(e.response, 'text'):
			print(f"Response: {e.response.text}")
		raise


def create_project(project_owner="", token=None):
	return create_entity_object(ENTITY_PROJECT, {"project_owner": project_owner}, token)


def create_parcel(project_id="", parcel_owner="", geo_data="", token=None):
	return create_entity_object(ENTITY_PARCEL, {"project_id": project_id, "parcel_owner": parcel_owner, "geo_data": geo_data}, token)


def create_parcel_ownership_verification(parcel_id="", status_code="", status_message="", authority="", token=None):
	return create_entity_object(ENTITY_PARCEL_OWNERSHIP_VERIFICATION, {
		"parcel_id": parcel_id,
		"status_code": status_code,
		"status_message": status_message,
		"authority": authority
	}, token)


def create_parcel_verification(parcel_id="", project_id_="", status_code="", status_message="", amount="", token=None):
	return create_entity_object(ENTITY_PROJECT_PARCEL_VERIFICATION, {
		"parcel_id": parcel_id,
		"project_id_": project_id_,
		"status_code": status_code,
		"status_message": status_message,
		"amount": amount
	}, token)

def create_project_verification(project_id="", status_code=None, status_message=None, token=None):
	return create_entity_object(ENTITY_PROJECT_VERIFICATION, {
		"project_id": project_id,
		"status_code": status_code,
		"status_message": status_message
	}, token)


def create_parcel_monitoring_period_verification(parcel_id="", project_id="", status_code="", status_message="", amount="", token=None):
	return create_entity_object(ENTITY_PARCEL_MONITORING_PERIOD_VERIFICATION, {
		"parcel_id": parcel_id,
		"project_id": project_id,
		"status_code": status_code,
		"status_message": status_message,
		"amount": amount
	}, token)


def create_project_monitoring_period_verification(project_id="", status_code="", status_message="", token=None):
	return create_entity_object(ENTITY_PROJECT_MONITORING_PERIOD_VERIFICATION, {
		"project_id": project_id,
		"status_code": status_code,
		"status_message": status_message
	}, token)

