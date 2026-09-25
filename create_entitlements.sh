#!/usr/bin/env bash
#
# create_entitlements.sh
#
# Grant the logged in user the Roles for the OGCR dynamic entities by running
# create_entitlements.py: the entity definition Roles, plus the record Roles for
# every entity in the parsed entities file, all at the bank id of the entities' space
# (OBP_ENTITY_SPACE_ID, or SYS for system level). Roles the user
# already holds come back as 409 "already exists" and are harmless.
# All arguments are passed through.
#
# Usage:
#   ./create_entitlements.sh [path/to/entities_output.txt]
#
# Notes:
#   - Credentials/host come from your .env, same as the Python scripts.
#   - Run ./check_login_and_roles.sh afterwards to confirm every Role is present.

set -euo pipefail

# Run from the directory this script lives in, so relative paths resolve.
cd "$(dirname "$0")"

# Prefer the project virtualenv if it exists (has requests/python-dotenv installed).
if [ -z "${PYTHON:-}" ] && [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
fi
PYTHON="${PYTHON:-python3}"

exec "$PYTHON" create_entitlements.py "$@"
