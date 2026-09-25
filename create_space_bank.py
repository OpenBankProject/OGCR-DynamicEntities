"""Make sure the bank (aka Space) named by OBP_ENTITY_SPACE_ID exists, creating it if not.

Bank level dynamic entities can only be created inside an existing bank. This
checks for the bank and, if it is missing, creates it with POST /obp/v6.0.0/banks,
which needs the Role CanCreateBank. With OBP_ENTITY_SPACE_ID empty (system level
entities) there is nothing to do.

Usage:
    python3 create_space_bank.py [--full-name "OGCR ..."]

Exits 0 if the bank exists or was created (or no space is configured), 1 otherwise.
"""

import argparse
import sys

import requests

from obp_client import token, obp_host
from obp_space import SPACE_ID


def get_bank(bank_id):
	"""Return the bank JSON, or None if it does not exist. Raises on other errors."""
	response = requests.get(f"{obp_host}/obp/v6.0.0/banks/{bank_id}",
		headers={"Authorization": f"DirectLogin token={token}"}, timeout=30)
	if response.status_code == 404:
		return None
	if response.status_code != 200:
		raise RuntimeError(f"GET bank '{bank_id}' failed ({response.status_code}): {response.text}")
	return response.json()


def create_bank(bank_id, full_name):
	body = {
		"bank_id": bank_id,
		"bank_code": bank_id,
		"full_name": full_name,
		"logo": "",
		"website": "",
		"bank_routings": [{"scheme": "OBP", "address": bank_id}],
	}
	response = requests.post(f"{obp_host}/obp/v6.0.0/banks", json=body,
		headers={"Authorization": f"DirectLogin token={token}"}, timeout=30)
	if response.status_code not in (200, 201):
		raise RuntimeError(f"Creating bank '{bank_id}' failed ({response.status_code}): {response.text}")
	return response.json()


def main():
	parser = argparse.ArgumentParser(description="Create the OBP_ENTITY_SPACE_ID bank if it does not exist.")
	parser.add_argument("--full-name", default=None,
		help="Full name for a newly created bank (default: 'OGCR <bank id>')")
	args = parser.parse_args()

	if not SPACE_ID:
		print("OBP_ENTITY_SPACE_ID is empty: entities are system level, no bank needed")
		return 0
	if not token:
		print("✗ DirectLogin failed; cannot check the bank")
		return 1

	try:
		if get_bank(SPACE_ID):
			print(f"✓ Bank '{SPACE_ID}' already exists")
			return 0
		create_bank(SPACE_ID, args.full_name or f"OGCR {SPACE_ID}")
		print(f"✓ Created bank '{SPACE_ID}'")
		return 0
	except (RuntimeError, requests.exceptions.RequestException) as e:
		print(f"✗ {e}")
		return 1


if __name__ == "__main__":
	sys.exit(main())
