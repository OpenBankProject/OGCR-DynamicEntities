#!/usr/bin/env bash
#
# recreate_ogcr_entities.sh
#
# Recreate ONLY the OGCR dynamic entities from min_field_matrix.xlsx:
#   0. Regenerate entities_output.txt (the list of OGCR entities) from the xlsx,
#      and, if OBP_ENTITY_SPACE_ID is set, create that bank if it doesn't exist.
#   1. Delete ONLY those OGCR entities on OBP (objects + definitions). Other
#      dynamic entities on the instance are left untouched.
#   2. Create the entities defined in min_field_matrix.xlsx.
#   3. Create example/dummy objects for those entities.
#   4. Create/update the Role Groups from the sheet's matrix (create_role_groups.sh).
#   5. Add users to those groups from DO_NOT_COMMIT/Users-Group-DO_NOT_COMMIT.xlsx (add_users_to_groups.sh),
#      if that file exists.
#
# Usage:
#   ./recreate_ogcr_entities.sh [path/to/min_field_matrix.xlsx] [--yes] [--only]
#
# --only recreates only the entities (steps 0-3), skipping the groups and users.
#
# It first shows the host and space it will work on and asks for confirmation;
# --yes skips the question (for automation). Without a terminal to ask on and
# without --yes, it stops. Preview with ./dry_run_create_ogcr_entities.sh.
#
# Notes:
#   - Token/host come from obp_client.py (or your .env), same as the Python scripts.
#   - Access flags HAS_PERSONAL_ENTITY / HAS_COMMUNITY_ACCESS are read from the env.
#   - Where the entities live comes from OBP_ENTITY_SPACE_ID: a bank id puts them
#     all under that bank; empty means system level. Every step uses the same
#     space, so only that space's entities are deleted and recreated.
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

MATRIX="min_field_matrix.xlsx"
USERS_SHEET="DO_NOT_COMMIT/Users-Group-DO_NOT_COMMIT.xlsx"
ASSUME_YES=false
ONLY_ENTITIES=false
for arg in "$@"; do
  case "$arg" in
    --yes) ASSUME_YES=true ;;
    --only) ONLY_ENTITIES=true ;;
    -*) echo "Unknown option: $arg" >&2; exit 2 ;;
    *) MATRIX="$arg" ;;
  esac
done
ENTITY_LIST="entities_output.txt"

# Show exactly where this run will delete and create, read the same way the Python
# scripts read it (.env, overridden by any variable already set in the shell).
TARGET="$("$PYTHON" -c '
import os
from obp_space import SPACE_ID, describe
print(os.getenv("OBP_HOSTNAME", "http://obp-api-internal-route-obp.apps-crc.testing"))
print(describe())
print(SPACE_ID or "(empty)")
')"
{ read -r TARGET_HOST; read -r TARGET_SPACE; read -r TARGET_SPACE_ID; } <<< "$TARGET"

echo "=================================================="
echo " About to DELETE and RECREATE the OGCR entities"
echo "   Host:     ${TARGET_HOST}"
echo "   Entities: ${TARGET_SPACE}  (OBP_ENTITY_SPACE_ID=${TARGET_SPACE_ID})"
echo "   Sheet:    ${MATRIX}"
if [ "$ONLY_ENTITIES" = true ]; then
  echo "   Groups:   skipped (--only)"
else
  echo "   Groups:   create/update from ${MATRIX}, then add users from ${USERS_SHEET}"
fi
echo " Existing records of those entities there will be lost."
echo "=================================================="
if [ "$ASSUME_YES" != true ]; then
  if [ ! -t 0 ]; then
    echo "No terminal to confirm on; re-run with --yes to proceed." >&2
    exit 1
  fi
  read -r -p "Type 'yes' to continue: " ANSWER
  if [ "$ANSWER" != "yes" ]; then
    echo "Aborted. Nothing was changed."
    exit 1
  fi
fi
echo

echo "=================================================="
echo " STEP 0: Regenerating ${ENTITY_LIST} from ${MATRIX}"
echo "=================================================="
# Keep the delete list in sync with the spreadsheet, so we delete exactly what
# we are about to recreate (and nothing else).
"$PYTHON" parse_minimum_fields.py "$MATRIX" --save --output "$ENTITY_LIST"

# Bank level entities need their bank to exist; stop here if it can't be created.
"$PYTHON" create_space_bank.py

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

if [ "$ONLY_ENTITIES" = true ]; then
  echo
  echo "Done. Dynamic entities recreated and populated from ${MATRIX}."
  echo "Role Groups and users skipped (--only)."
  exit 0
fi

echo
echo "=================================================="
echo " STEP 4: Creating/updating Role Groups from ${MATRIX}"
echo "=================================================="
# A failure here stops the run: users can't be added to groups that aren't right.
"$PYTHON" create_role_groups.py "$MATRIX"

echo
echo "=================================================="
echo " STEP 5: Adding users to the Role Groups"
echo "=================================================="
USERS_FAILED=false
if [ -f "$USERS_SHEET" ]; then
  # Report failures (e.g. a user not on this OBP) but still finish the run.
  "$PYTHON" add_users_to_groups.py "$USERS_SHEET" || USERS_FAILED=true
else
  echo "No ${USERS_SHEET}; skipping. Nobody was added to the groups."
fi

echo
echo "Done. Dynamic entities recreated and populated from ${MATRIX}, Role Groups updated."
if [ "$USERS_FAILED" = true ]; then
  echo "✗ Some users could not be added to their groups; see STEP 5 above." >&2
  exit 1
fi
