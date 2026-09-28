#!/usr/bin/env bash
#
# grant_user_dynamic_entity_roles.sh
#
# Grant a user record Roles on some dynamic entities (asks first; one email per Role).
# Runs grant_user_dynamic_entity_roles.py; all arguments are passed through. USERNAME is the user to look
# at or grant to, not the one logged in from .env.
#
# Usage:
#   ./grant_user_dynamic_entity_roles.sh USERNAME --entity NAME [--entity NAME ...] [--access CRUD] [--bank-id SYS] [--dry-run]

set -euo pipefail

# Run from the directory this script lives in, so relative paths resolve.
cd "$(dirname "$0")"

# Prefer the project virtualenv if it exists (has requests/python-dotenv installed).
if [ -z "${PYTHON:-}" ] && [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
fi
PYTHON="${PYTHON:-python3}"

exec "$PYTHON" grant_user_dynamic_entity_roles.py "$@"
