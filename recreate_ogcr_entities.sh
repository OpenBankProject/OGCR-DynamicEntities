#!/usr/bin/env bash
#
# recreate_ogcr_entities.sh
#
# Recreate ONLY the OGCR dynamic entities from min_field_matrix.xlsx:
#   0. Regenerate entities_output.txt (the list of OGCR entities) from the xlsx.
#   1. Delete ONLY those OGCR entities on OBP (objects + definitions). Other
#      dynamic entities on the instance are left untouched.
#   2. Create the entities defined in min_field_matrix.xlsx.
#   3. Create example/dummy objects for those entities.
#
# Usage:
#   ./recreate_ogcr_entities.sh [path/to/min_field_matrix.xlsx]
#
# Notes:
#   - Token/host come from obp_client.py (or your .env), same as the Python scripts.
#   - Access flags HAS_PERSONAL_ENTITY / HAS_COMMUNITY_ACCESS are read from the env.
#   - To wipe EVERY dynamic entity instead (not just OGCR), use
#     delete_all_dynamic_entities.py directly.

set -euo pipefail

# Run from the directory this script lives in, so relative paths resolve.
cd "$(dirname "$0")"

# Prefer the project virtualenv if it exists (has pandas/openpyxl installed).
if [ -z "${PYTHON:-}" ] && [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
fi
PYTHON="${PYTHON:-python3}"
MATRIX="${1:-min_field_matrix.xlsx}"
ENTITY_LIST="entities_output.txt"

echo "=================================================="
echo " STEP 0: Regenerating ${ENTITY_LIST} from ${MATRIX}"
echo "=================================================="
# Keep the delete list in sync with the spreadsheet, so we delete exactly what
# we are about to recreate (and nothing else).
"$PYTHON" parse_minimum_fields.py "$MATRIX" --save --output "$ENTITY_LIST"

echo
echo "=================================================="
echo " STEP 1: Deleting the OGCR entities in ${ENTITY_LIST}"
echo "=================================================="
# delete_ogcr_entities.py deletes ONLY the entities listed in ${ENTITY_LIST} and
# exits non-zero if any survive; `set -e` then aborts so we never recreate on
# top of leftovers.
"$PYTHON" delete_ogcr_entities.py "$ENTITY_LIST" --yes
echo "OGCR entities deleted."

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
