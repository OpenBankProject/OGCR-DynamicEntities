#!/usr/bin/env bash
#
# dry_run_recreate_dynamic_entities.sh
#
# DRY RUN of recreate_dynamic_entities.sh: reports what it would do -- create the
# space's bank, delete, create, example data, the Roles still needed, the Dynamic
# Resource Docs, the Role Groups and the users added to them -- without doing any
# of it. Only reads the spreadsheets and makes GET requests, plus a POST to OBP's
# resource doc compile endpoint, which stores nothing.
#
# Usage:
#   ./dry_run_recreate_dynamic_entities.sh [path/to/min_field_matrix.xlsx] [--only]
#
# --only previews only the entities, as recreate_dynamic_entities.sh --only would run.
#
# Notes:
#   - Credentials/host/OBP_ENTITY_SPACE_ID come from your .env, same as the real run.

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
ONLY_ENTITIES=false
for arg in "$@"; do
  case "$arg" in
    --only) ONLY_ENTITIES=true ;;
    -*) echo "Unknown option: $arg" >&2; exit 2 ;;
    *) MATRIX="$arg" ;;
  esac
done

complete() {
  local rule="======================================================================"
  echo
  echo "[DRY RUN] ${rule}"
  echo "[DRY RUN] DRY RUN complete. Nothing was changed. Run ./recreate_dynamic_entities.sh to do it."
  echo "[DRY RUN] ${rule}"
}

"$PYTHON" dry_run_recreate_dynamic_entities.py "$MATRIX"
if [ "$ONLY_ENTITIES" = true ]; then
  echo "[DRY RUN] Role Groups, users and resource docs would be skipped (--only)"
  complete
  exit 0
fi

echo "[DRY RUN]"
echo "[DRY RUN] STEP 4: Role Groups from ${MATRIX}"
# The group previews exit 1 when they find problems; keep going so the whole preview shows.
"$PYTHON" create_role_groups.py "$MATRIX" --dry-run || true
echo "[DRY RUN]"
echo "[DRY RUN] STEP 5: Users from ${USERS_SHEET}"
if [ -f "$USERS_SHEET" ]; then
  "$PYTHON" add_users_to_groups.py "$USERS_SHEET" --dry-run || true
else
  echo "[DRY RUN] No ${USERS_SHEET}; nobody would be added to the groups"
fi

echo "[DRY RUN]"
echo "[DRY RUN] STEP 6: Dynamic Resource Docs"
# Exits 1 when a doc doesn't compile; keep going so the whole preview shows.
./recreate_dynamic_resource_docs.sh --dry-run || true
complete
