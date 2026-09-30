#!/usr/bin/env bash
#
# sync_user_group_permissions.sh
#
# Bring one user's group memberships (as ticked in the users sheet) and Roles (in every
# group they are in) up to date.
# Runs sync_user_group_permissions.py; all arguments are passed through.
#
# Usage:
#   ./sync_user_group_permissions.sh --user USERNAME [path/to/users.xlsx] [--sheet NAME] [--dry-run]

set -euo pipefail

# Run from the directory this script lives in, so relative paths resolve.
cd "$(dirname "$0")"

# Prefer the project virtualenv if it exists (has requests/python-dotenv installed).
if [ -z "${PYTHON:-}" ] && [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
fi
PYTHON="${PYTHON:-python3}"

exec "$PYTHON" sync_user_group_permissions.py "$@"
