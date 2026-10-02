#!/usr/bin/env bash
#
# recreate_dynamic_entities.sh
#
# Recreate ONLY the OGCR dynamic entities from min_field_matrix.xlsx:
#   0. Check the sheet (check_min_field_matrix.py) and stop on any error, before
#      anything is deleted. Regenerate entities_output.txt (the list of OGCR
#      entities) from the xlsx, and, if OBP_ENTITY_SPACE_ID is set, create that bank if it doesn't exist.
#   1. Delete ONLY those OGCR entities on OBP (objects + definitions). Other
#      dynamic entities on the instance are left untouched.
#   2. Create the entities defined in min_field_matrix.xlsx.
#   3. Create example objects for those entities, then the registry's
#      demo records (create_registry_demo_data.sh).
#   4. Create/update the Role Groups from the sheet's matrix (create_role_groups.sh).
#   5. Add users to those groups from DO_NOT_COMMIT/Users-Group-DO_NOT_COMMIT.xlsx (add_users_to_groups.sh),
#      if that file exists.
#   6. Recreate the Dynamic Resource Docs (recreate_dynamic_resource_docs.sh).
#
# Usage:
#   ./recreate_dynamic_entities.sh [path/to/min_field_matrix.xlsx] [--yes] [--only]
#
# --only recreates only the entities (steps 0-3), skipping the groups, users and resource docs.
#
# Everything it prints is also saved to logs/recreate_dynamic_entities_<time>.log,
# with a header (host, space, sheet, git commit, options) and every timing, also
# the fast ones the console leaves out -- a complete record to hand to someone
# (or an agent) looking into the dynamic entities. logs/ is git-ignored: the log
# can hold real usernames from step 5.
#
# It first shows the host and space it will work on and asks for confirmation;
# --yes skips the question (for automation). Without a terminal to ask on and
# without --yes, it stops. Preview with ./dry_run_recreate_dynamic_entities.sh.
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
  echo "   Docs:     skipped (--only)"
else
  echo "   Groups:   create/update from ${MATRIX}, then add users from ${USERS_SHEET}"
  echo "   Docs:     recreate the Dynamic Resource Docs"
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

# Complete log of this run: from here on, everything printed goes to the console
# AND the log file. Unbuffered Python keeps its lines in order with the shell's.
LOG_DIR="logs"
mkdir -p "$LOG_DIR"
LOG_FILE="${LOG_DIR}/recreate_dynamic_entities_$(date +%Y%m%d-%H%M%S).log"
export OGCR_LOG_FILE="$(pwd)/${LOG_FILE}"  # timing.py writes the fast timings here too
export PYTHONUNBUFFERED=1
{
  echo "# recreate_dynamic_entities.sh log"
  echo "# Started:  $(date -Is)"
  echo "# Host:     ${TARGET_HOST}"
  echo "# Entities: ${TARGET_SPACE}  (OBP_ENTITY_SPACE_ID=${TARGET_SPACE_ID})"
  echo "# Sheet:    ${MATRIX}"
  echo "# Options:  only=${ONLY_ENTITIES} yes=${ASSUME_YES}"
  if GIT_COMMIT="$(git rev-parse --short HEAD 2>/dev/null)"; then
    git diff --quiet HEAD 2>/dev/null || GIT_COMMIT+=" (with uncommitted changes)"
  else
    GIT_COMMIT="unknown"
  fi
  echo "# Git:      ${GIT_COMMIT}"
  echo "# Timings:  lines starting with ⏱; the console only shows those over 1s, this log has them all"
  echo
} > "$LOG_FILE"
exec > >(tee -a "$LOG_FILE") 2>&1
echo "Logging to ${LOG_FILE}"

# Timing: each step prints how long it took, and a summary of all the steps is
# printed at the end, also when a step fails and stops the run. Inside steps 1-3
# the Python scripts also time each entity and list their slowest.
RUN_T0=$(date +%s%N)
STEP_TIMINGS=()
fmt_ms() { printf '%d.%01ds' $(( $1 / 1000 )) $(( $1 % 1000 / 100 )); }
timed_step() {
  local label="$1"; shift
  local t0 rc=0 ms
  t0=$(date +%s%N)
  "$@" || rc=$?
  ms=$(( ($(date +%s%N) - t0) / 1000000 ))
  STEP_TIMINGS+=("$(printf '%10s  %s%s' "$(fmt_ms "$ms")" "$label" "$([ "$rc" -eq 0 ] || echo "  (failed)")")")
  echo "⏱ ${label}: $(fmt_ms "$ms")"
  return "$rc"
}
print_timings() {
  [ ${#STEP_TIMINGS[@]} -gt 0 ] || return 0
  echo
  echo "=================================================="
  echo " Timings"
  echo "=================================================="
  printf '%s\n' "${STEP_TIMINGS[@]}"
  printf '%10s  %s\n' "$(fmt_ms $(( ($(date +%s%N) - RUN_T0) / 1000000 )))" "total"
  echo "Full log: ${LOG_FILE}"
}
trap print_timings EXIT

echo "=================================================="
echo " STEP 0: Checking ${MATRIX}, regenerating ${ENTITY_LIST}"
echo "=================================================="
# Refuse a sheet with errors (e.g. an example that doesn't fit its type) before
# anything on OBP is deleted.
timed_step "Step 0: check sheet" "$PYTHON" check_min_field_matrix.py "$MATRIX"
# Keep the delete list in sync with the spreadsheet, so we delete exactly what
# we are about to recreate (and nothing else).
timed_step "Step 0: parse sheet" "$PYTHON" parse_minimum_fields.py "$MATRIX" --save --output "$ENTITY_LIST"

# Bank level entities need their bank to exist; stop here if it can't be created.
timed_step "Step 0: check/create bank" "$PYTHON" create_space_bank.py

echo
echo "=================================================="
echo " STEP 1: Deleting the OGCR entities in ${ENTITY_LIST}"
echo "=================================================="
# delete_dynamic_entities.py deletes ONLY the entities listed in ${ENTITY_LIST} and
# exits non-zero if any survive; `set -e` then aborts so we never recreate on
# top of leftovers.
timed_step "Step 1: delete entities" "$PYTHON" delete_dynamic_entities.py "$ENTITY_LIST" --yes
echo "OGCR entities deleted."

echo
echo "=================================================="
echo " STEP 2: Creating entities from ${MATRIX}"
echo "=================================================="
timed_step "Step 2: create entities" "$PYTHON" parse_minimum_fields.py "$MATRIX" --create --yes

echo
echo "=================================================="
echo " STEP 3: Creating example data from ${MATRIX}"
echo "=================================================="
timed_step "Step 3: example data" "$PYTHON" create_example_data.py "$MATRIX"
# Report a failure but still finish the run.
REGISTRY_FAILED=false
timed_step "Step 3: registry data" ./create_registry_demo_data.sh "$MATRIX" || REGISTRY_FAILED=true

if [ "$ONLY_ENTITIES" = true ]; then
  echo
  echo "Done. Dynamic entities recreated and populated from ${MATRIX}."
  echo "Role Groups, users and resource docs skipped (--only)."
  if [ "$REGISTRY_FAILED" = true ]; then
    echo "✗ Some registry demo records were not created; see STEP 3 above." >&2
    exit 1
  fi
  exit 0
fi

echo
echo "=================================================="
echo " STEP 4: Creating/updating Role Groups from ${MATRIX}"
echo "=================================================="
# A failure here stops the run: users can't be added to groups that aren't right.
timed_step "Step 4: Role Groups" "$PYTHON" create_role_groups.py "$MATRIX"

echo
echo "=================================================="
echo " STEP 5: Adding users to the Role Groups"
echo "=================================================="
USERS_FAILED=false
if [ -f "$USERS_SHEET" ]; then
  # Report failures (e.g. a user not on this OBP) but still finish the run.
  timed_step "Step 5: add users" "$PYTHON" add_users_to_groups.py "$USERS_SHEET" || USERS_FAILED=true
else
  echo "No ${USERS_SHEET}; skipping. Nobody was added to the groups."
fi

echo
echo "=================================================="
echo " STEP 6: Recreating the Dynamic Resource Docs"
echo "=================================================="
# Report a failure but still finish the run.
DOCS_FAILED=false
timed_step "Step 6: resource docs" ./recreate_dynamic_resource_docs.sh --yes || DOCS_FAILED=true

echo
echo "Done. Dynamic entities recreated and populated from ${MATRIX}, Role Groups updated, resource docs recreated."
if [ "$REGISTRY_FAILED" = true ]; then
  echo "✗ Some registry demo records were not created; see STEP 3 above." >&2
fi
if [ "$USERS_FAILED" = true ]; then
  echo "✗ Some users could not be added to their groups; see STEP 5 above." >&2
fi
if [ "$DOCS_FAILED" = true ]; then
  echo "✗ The Dynamic Resource Docs were not all recreated; see STEP 6 above." >&2
fi
if [ "$DOCS_FAILED" = true ] || [ "$USERS_FAILED" = true ] || [ "$REGISTRY_FAILED" = true ]; then
  exit 1
fi
