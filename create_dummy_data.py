import logging
import random
import time

import requests
from dotenv import load_dotenv

from dynamic_entities import (
    ENTITY_PARCEL,
    ENTITY_PARCEL_MONITORING_PERIOD_VERIFICATION,
    ENTITY_PARCEL_OWNERSHIP_VERIFICATION,
    ENTITY_PROJECT,
    ENTITY_PROJECT_MONITORING_PERIOD_VERIFICATION,
    ENTITY_PROJECT_PARCEL_VERIFICATION,
    ENTITY_PROJECT_VERIFICATION,
    get_id_key,
    get_response_key,
)
from obp_client import obp_host, token

# Configure logging with better formatting
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Configuration
BASE_URL = obp_host
DIRECTLOGIN_TOKEN = token
load_dotenv()


def print_separator(char="=", length=80):
    """Print a separator line for better visual separation"""
    logger.info(char * length)


def create_dynamic_entity_object(entity_name, data, token=None):
    """
    Create an object for a dynamic entity.

    Args:
        entity_name (str): The name of the dynamic entity
        data (dict): The object data
        token (str, optional): DirectLogin authentication token

    Returns:
        dict: The API response with created object
    """
    url = f"{BASE_URL}/obp/dynamic-entity/{entity_name}"

    headers = {"Content-Type": "application/json"}

    if token:
        headers["Authorization"] = f"DirectLogin token={token}"

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        return result
    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating object for {entity_name}: {e}")
        if hasattr(e.response, "text"):
            logger.error(f"Response: {e.response.text}")
        raise


def get_dynamic_entity_object(entity_name, object_id, token=None):
    """
    Get a specific object from a dynamic entity.

    Args:
        entity_name (str): The name of the dynamic entity
        object_id (str): The ID of the object to fetch
        token (str, optional): DirectLogin authentication token

    Returns:
        dict: The API response with the object
    """
    url = f"{BASE_URL}/obp/dynamic-entity/{entity_name}/{object_id}"

    headers = {"Content-Type": "application/json"}

    if token:
        headers["Authorization"] = f"DirectLogin token={token}"

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        result = response.json()
        return result
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting object for {entity_name}/{object_id}: {e}")
        if hasattr(e.response, "text"):
            logger.error(f"Response: {e.response.text}")
        raise


def main():
    logger.info("Starting Dummy Data Creation Script")
    print_separator()

    # Store created IDs for referential integrity
    created_projects = []
    created_parcels = []

    # =========================================================================
    # STEP 1: Create Projects
    # =========================================================================
    logger.info("STEP 1: Creating Projects")
    print_separator("-")

    projects_data = [
        {
            "project_owner": "John Smith - Passport: US123456789",
            "project_name": "California Reforestation Project",
            "project_type": "Reforestation",
            "project_operator": "Green Earth Solutions Inc.",
            "project_country": "United States",
        },
        {
            "project_owner": "Maria Garcia - Passport: ES987654321",
            "project_name": "Iberian Forest Restoration Initiative",
            "project_type": "Forest Conservation",
            "project_operator": "EcoMediterraneo S.L.",
            "project_country": "Spain",
        },
        {
            "project_owner": "Wei Chen - Passport: CN456789123",
            "project_name": "Beijing Urban Green Belt Project",
            "project_type": "Afforestation",
            "project_operator": "China Carbon Solutions Ltd.",
            "project_country": "China",
        },
    ]

    for idx, project_data in enumerate(projects_data, 1):
        try:
            response = create_dynamic_entity_object(
                ENTITY_PROJECT, project_data, DIRECTLOGIN_TOKEN
            )
            # The response contains a nested object with key like 'ogcr2_project'
            # Inside that object is the ID with key like 'ogcr2project_id'
            response_key = get_response_key(ENTITY_PROJECT)
            if response_key in response:
                project_obj = response[response_key]
                # The ID key inside is prefix_entityname_id (with underscores)
                id_key = get_id_key(ENTITY_PROJECT)
                project_id = project_obj.get(id_key)
                if not project_id:
                    logger.error(
                        f"Could not find {id_key} in nested object. Available keys: {list(project_obj.keys())}"
                    )
                    raise KeyError(f"Could not find {id_key} in response")
            else:
                logger.error(
                    f"Could not find {response_key} in response. Available keys: {list(response.keys())}"
                )
                raise KeyError(f"Could not find {response_key} in response")

            created_projects.append(project_id)
            logger.info(
                f"  ✓ [{idx}/{len(projects_data)}] Created project: {project_data['project_owner'][:30]}... (ID: {project_id})"
            )
            # Debug: Log the full response structure
            logger.debug(f"Full project response: {response}")
        except Exception as e:
            logger.error(
                f"  ✗ [{idx}/{len(projects_data)}] Failed to create project: {e}"
            )

    if not created_projects:
        logger.error("No projects created. Cannot continue with parcels.")
        return

    print_separator()

    # Debug: Log the created project IDs
    logger.info(f"Created project IDs: {created_projects}")

    # Verify projects exist by fetching them back
    logger.info("Verifying created projects exist...")
    for project_id in created_projects:
        try:
            project = get_dynamic_entity_object(
                ENTITY_PROJECT, project_id, DIRECTLOGIN_TOKEN
            )
            logger.info(f"  ✓ Verified project {project_id[:8]}... exists")
        except Exception as e:
            logger.error(f"  ✗ Failed to verify project {project_id}: {e}")

    # =========================================================================
    # STEP 2: Create Parcels
    # =========================================================================
    logger.info("STEP 2: Creating Parcels")
    print_separator("-")

    # Use the proper foreign key field name that matches the referenced entity's ID field
    project_id_field = f"{ENTITY_PROJECT}_id"

    parcels_data = [
        {
            project_id_field: created_projects[0],
            "parcel_owner": "John Smith - Passport: US123456789",
            "geo_data": '{"type":"Polygon","coordinates":[[[-122.4,37.8],[-122.4,37.7],[-122.3,37.7],[-122.3,37.8],[-122.4,37.8]]]}',
        },
        {
            project_id_field: created_projects[0],
            "parcel_owner": "John Smith - Passport: US123456789",
            "geo_data": '{"type":"Polygon","coordinates":[[[-122.3,37.8],[-122.3,37.7],[-122.2,37.7],[-122.2,37.8],[-122.3,37.8]]]}',
        },
        {
            project_id_field: created_projects[1],
            "parcel_owner": "Maria Garcia - Passport: ES987654321",
            "geo_data": '{"type":"Polygon","coordinates":[[[-3.7,40.4],[-3.7,40.3],[-3.6,40.3],[-3.6,40.4],[-3.7,40.4]]]}',
        },
        {
            project_id_field: created_projects[1],
            "parcel_owner": "Maria Garcia - Passport: ES987654321",
            "geo_data": '{"type":"Polygon","coordinates":[[[-3.6,40.4],[-3.6,40.3],[-3.5,40.3],[-3.5,40.4],[-3.6,40.4]]]}',
        },
        {
            project_id_field: created_projects[2],
            "parcel_owner": "Wei Chen - Passport: CN456789123",
            "geo_data": '{"type":"Polygon","coordinates":[[[116.4,39.9],[116.4,39.8],[116.5,39.8],[116.5,39.9],[116.4,39.9]]]}',
        },
    ]

    for idx, parcel_data in enumerate(parcels_data, 1):
        try:
            response = create_dynamic_entity_object(
                ENTITY_PARCEL, parcel_data, DIRECTLOGIN_TOKEN
            )
            response_key = get_response_key(ENTITY_PARCEL)
            if response_key in response:
                parcel_obj = response[response_key]
                id_key = get_id_key(ENTITY_PARCEL)
                parcel_id = parcel_obj.get(id_key)
                if not parcel_id:
                    logger.error(
                        f"Could not find {id_key} in nested object. Available keys: {list(parcel_obj.keys())}"
                    )
                    raise KeyError(f"Could not find {id_key} in response")
            else:
                logger.error(
                    f"Could not find {response_key} in response. Available keys: {list(response.keys())}"
                )
                raise KeyError(f"Could not find {response_key} in response")

            # Store parcel ID and project_id for later use
            created_parcels.append(
                {"parcel_id": parcel_id, "project_id": parcel_data[project_id_field]}
            )
            logger.info(
                f"  ✓ [{idx}/{len(parcels_data)}] Created parcel for project {parcel_data[project_id_field][:8]}... (ID: {parcel_id})"
            )
        except Exception as e:
            logger.error(
                f"  ✗ [{idx}/{len(parcels_data)}] Failed to create parcel: {e}"
            )

    if not created_parcels:
        logger.error("No parcels created. Cannot continue with verifications.")
        return

    print_separator()

    # =========================================================================
    # STEP 3: Create Parcel Ownership Verifications
    # =========================================================================
    logger.info("STEP 3: Creating Parcel Ownership Verifications")
    print_separator("-")

    for idx, parcel in enumerate(created_parcels, 1):
        parcel_id_field = f"{ENTITY_PARCEL}_id"
        verification_data = {
            parcel_id_field: parcel["parcel_id"],
            "status_code": "verified" if idx % 3 != 0 else "in_progress",
            "status_message": "Ownership verified successfully"
            if idx % 3 != 0
            else "Verification pending cadastre response",
            "authority": "National Land Registry",
        }

        try:
            response = create_dynamic_entity_object(
                ENTITY_PARCEL_OWNERSHIP_VERIFICATION,
                verification_data,
                DIRECTLOGIN_TOKEN,
            )
            response_key = get_response_key(ENTITY_PARCEL_OWNERSHIP_VERIFICATION)
            verification_obj = response.get(response_key, {})
            id_key = get_id_key(ENTITY_PARCEL_OWNERSHIP_VERIFICATION)
            verification_id = verification_obj.get(id_key)
            logger.info(
                f"  ✓ [{idx}/{len(created_parcels)}] Created ownership verification for parcel {parcel['parcel_id'][:8]}... (Status: {verification_data['status_code']})"
            )
        except Exception as e:
            logger.error(
                f"  ✗ [{idx}/{len(created_parcels)}] Failed to create ownership verification: {e}"
            )

    print_separator()

    # =========================================================================
    # STEP 4: Create Project Verifications
    # =========================================================================
    logger.info("STEP 4: Creating Project Verifications")
    print_separator("-")

    for idx, project_id in enumerate(created_projects, 1):
        project_id_field = f"{ENTITY_PROJECT}_id"
        verification_data = {
            project_id_field: project_id,
            "status_code": "verified" if idx % 2 == 0 else "in_progress",
            "status_message": "Project methodology verified"
            if idx % 2 == 0
            else "Awaiting documentation review",
        }

        try:
            response = create_dynamic_entity_object(
                ENTITY_PROJECT_VERIFICATION, verification_data, DIRECTLOGIN_TOKEN
            )
            response_key = get_response_key(ENTITY_PROJECT_VERIFICATION)
            verification_obj = response.get(response_key, {})
            id_key = get_id_key(ENTITY_PROJECT_VERIFICATION)
            verification_id = verification_obj.get(id_key)
            logger.info(
                f"  ✓ [{idx}/{len(created_projects)}] Created project verification for {project_id[:8]}... (Status: {verification_data['status_code']})"
            )
        except Exception as e:
            logger.error(
                f"  ✗ [{idx}/{len(created_projects)}] Failed to create project verification: {e}"
            )

    print_separator()

    # =========================================================================
    # STEP 5: Create Project-Parcel Verifications
    # =========================================================================
    logger.info("STEP 5: Creating Project-Parcel Verifications")
    print_separator("-")

    for idx, parcel in enumerate(created_parcels, 1):
        parcel_id_field = f"{ENTITY_PARCEL}_id"
        project_id_field = f"{ENTITY_PROJECT}_id"
        verification_data = {
            parcel_id_field: parcel["parcel_id"],
            project_id_field: parcel["project_id"],
            "status_code": "verified" if idx % 4 != 0 else "failed",
            "status_message": "Baseline carbon estimation completed"
            if idx % 4 != 0
            else "Insufficient historical data",
            "amount": 150 + (idx * 50) if idx % 4 != 0 else 0,
        }

        try:
            response = create_dynamic_entity_object(
                ENTITY_PROJECT_PARCEL_VERIFICATION, verification_data, DIRECTLOGIN_TOKEN
            )
            response_key = get_response_key(ENTITY_PROJECT_PARCEL_VERIFICATION)
            verification_obj = response.get(response_key, {})
            id_key = get_id_key(ENTITY_PROJECT_PARCEL_VERIFICATION)
            verification_id = verification_obj.get(id_key)
            logger.info(
                f"  ✓ [{idx}/{len(created_parcels)}] Created project-parcel verification (Amount: {verification_data['amount']} tons CO2)"
            )
        except Exception as e:
            logger.error(
                f"  ✗ [{idx}/{len(created_parcels)}] Failed to create project-parcel verification: {e}"
            )

    print_separator()

    # =========================================================================
    # STEP 6: Create Parcel Monitoring Period Verifications
    # =========================================================================
    logger.info("STEP 6: Creating Parcel Monitoring Period Verifications")
    print_separator("-")

    for idx, parcel in enumerate(created_parcels, 1):
        parcel_id_field = f"{ENTITY_PARCEL}_id"
        project_id_field = f"{ENTITY_PROJECT}_id"
        verification_data = {
            parcel_id_field: parcel["parcel_id"],
            project_id_field: parcel["project_id"],
            "status_code": "verified" if idx % 3 != 0 else "in_progress",
            "status_message": "Monitoring period Q1-2024 verified"
            if idx % 3 != 0
            else "Awaiting satellite data analysis",
            "amount": 80 + (idx * 30) if idx % 3 != 0 else 0,
        }

        try:
            response = create_dynamic_entity_object(
                ENTITY_PARCEL_MONITORING_PERIOD_VERIFICATION,
                verification_data,
                DIRECTLOGIN_TOKEN,
            )
            response_key = get_response_key(
                ENTITY_PARCEL_MONITORING_PERIOD_VERIFICATION
            )
            verification_obj = response.get(response_key, {})
            id_key = get_id_key(ENTITY_PARCEL_MONITORING_PERIOD_VERIFICATION)
            verification_id = verification_obj.get(id_key)
            logger.info(
                f"  ✓ [{idx}/{len(created_parcels)}] Created parcel monitoring verification (Amount: {verification_data['amount']} tons CO2)"
            )
        except Exception as e:
            logger.error(
                f"  ✗ [{idx}/{len(created_parcels)}] Failed to create parcel monitoring verification: {e}"
            )

    print_separator()

    # =========================================================================
    # STEP 7: Create Project Period Verifications
    # =========================================================================
    logger.info("STEP 7: Creating Project Period Verifications")
    print_separator("-")

    for idx, project_id in enumerate(created_projects, 1):
        project_id_field = f"{ENTITY_PROJECT}_id"
        verification_data = {
            project_id_field: project_id,
            "status_code": "verified" if idx % 2 == 1 else "in_progress",
            "status_message": "Q1-2024 project period verified"
            if idx % 2 == 1
            else "Pending final aggregation review",
        }

        try:
            response = create_dynamic_entity_object(
                ENTITY_PROJECT_MONITORING_PERIOD_VERIFICATION,
                verification_data,
                DIRECTLOGIN_TOKEN,
            )
            response_key = get_response_key(
                ENTITY_PROJECT_MONITORING_PERIOD_VERIFICATION
            )
            verification_obj = response.get(response_key, {})
            id_key = get_id_key(ENTITY_PROJECT_MONITORING_PERIOD_VERIFICATION)
            verification_id = verification_obj.get(id_key)
            logger.info(
                f"  ✓ [{idx}/{len(created_projects)}] Created project period verification for {project_id[:8]}... (Status: {verification_data['status_code']})"
            )
        except Exception as e:
            logger.error(
                f"  ✗ [{idx}/{len(created_projects)}] Failed to create project period verification: {e}"
            )

    print_separator()

    # =========================================================================
    # Summary
    # =========================================================================
    logger.info("SUMMARY")
    print_separator("-")
    logger.info(f"✓ Created {len(created_projects)} projects")
    logger.info(f"✓ Created {len(created_parcels)} parcels")
    logger.info(f"✓ Created verification records for all entities")
    print_separator()

    logger.info("Dummy Data Creation Script Completed Successfully!")
    print_separator("=")


if __name__ == "__main__":
    main()
