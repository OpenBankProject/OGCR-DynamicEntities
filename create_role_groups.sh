#!/usr/bin/env bash
#
# create_role_groups.sh
#
# Create or update one OBP Group per Role Group column (R onwards) of
# min_field_matrix.xlsx by running create_role_groups.py. Each group holds the
# dynamic entity record Roles its column ticks (C/R/U/D per entity), at the bank
# id of the entities' space (OBP_ENTITY_SPACE_ID, or SYS for system level).
# All arguments are passed through.
#
# Usage:
#   ./create_role_groups.sh [path/to/min_field_matrix.xlsx] [--dry-run]
#
# Notes:
#   - Credentials/host come from your .env, same as the Python scripts.
#   - Members whose Roles no longer match their group are removed from it and
#     added back, so they pick up the change.

set -euo pipefail

# Run from the directory this script lives in, so relative paths resolve.
cd "$(dirname "$0")"

# Prefer the project virtualenv if it exists (has pandas/openpyxl/requests installed).
if [ -z "${PYTHON:-}" ] && [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
fi
PYTHON="${PYTHON:-python3}"

exec "$PYTHON" create_role_groups.py "$@"
