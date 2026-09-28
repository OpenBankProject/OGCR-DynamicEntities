#!/usr/bin/env bash
#
# add_users_to_groups.sh
#
# Add users to the OGCR Role Groups, as ticked in the users spreadsheet
# (default DO_NOT_COMMIT/Users-Group-DO_NOT_COMMIT.xlsx), by running
# add_users_to_groups.py. Nobody is removed. All arguments are passed through.
#
# Usage:
#   ./add_users_to_groups.sh [path/to/users.xlsx] [--sheet NAME] [--user USERNAME] [--dry-run]
#
# Notes:
#   - Credentials/host come from your .env, same as the Python scripts.
#   - Run ./create_role_groups.sh first, so the groups exist.

set -euo pipefail

# Run from the directory this script lives in, so relative paths resolve.
cd "$(dirname "$0")"

# Prefer the project virtualenv if it exists (has pandas/openpyxl/requests installed).
if [ -z "${PYTHON:-}" ] && [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
fi
PYTHON="${PYTHON:-python3}"

exec "$PYTHON" add_users_to_groups.py "$@"
