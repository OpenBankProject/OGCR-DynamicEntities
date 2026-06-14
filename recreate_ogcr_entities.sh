#!/usr/bin/env bash
#
# recreate_ogcr_entities.sh
#
# Recreate the OGCR dynamic entities from min_field_matrix.xlsx:
#   1. Delete all existing system dynamic entities on OBP (and their objects).
#   2. Create the entities defined in min_field_matrix.xlsx.
#   3. Create example/dummy objects for those entities.
#
# Usage:
#   ./recreate_ogcr_entities.sh [path/to/min_field_matrix.xlsx]
#
# Notes:
#   - Token/host come from obp_client.py (or your .env), same as the Python scripts.
#   - Access flags HAS_PERSONAL_ENTITY / HAS_COMMUNITY_ACCESS are read from the env.

set -euo pipefail

# Run from the directory this script lives in, so relative paths resolve.
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
MATRIX="${1:-min_field_matrix.xlsx}"

echo "=================================================="
echo " STEP 1: Deleting all existing dynamic entities"
echo "=================================================="
"$PYTHON" delete_all_dynamic_entities.py

echo
echo "=================================================="
echo " STEP 2: Creating entities from ${MATRIX}"
echo "=================================================="
"$PYTHON" parse_minimum_fields.py "$MATRIX" --create --yes

echo
echo "=================================================="
echo " STEP 3: Creating example data from ${MATRIX}"
echo "=================================================="
"$PYTHON" create_dummy_data.py "$MATRIX"

echo
echo "Done. Dynamic entities recreated and populated from ${MATRIX}."
