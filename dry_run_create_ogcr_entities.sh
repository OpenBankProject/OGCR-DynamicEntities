#!/usr/bin/env bash
#
# dry_run_create_ogcr_entities.sh
#
# DRY RUN of recreate_ogcr_entities.sh: reports what it would do -- create the
# space's bank, delete, create, dummy data, and the Roles still needed --
# without doing any of it. Only reads the spreadsheet and makes GET requests.
#
# Usage:
#   ./dry_run_create_ogcr_entities.sh [path/to/min_field_matrix.xlsx]
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

exec "$PYTHON" dry_run_create_ogcr_entities.py "$@"
