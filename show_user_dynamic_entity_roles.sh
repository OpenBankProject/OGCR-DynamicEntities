#!/usr/bin/env bash
#
# show_user_dynamic_entity_roles.sh
#
# List a user's dynamic entity entitlements (system level, or --bank-id).
# Runs show_user_dynamic_entity_roles.py; all arguments are passed through. USERNAME is the user to look
# at or grant to, not the one logged in from .env.
#
# Usage:
#   ./show_user_dynamic_entity_roles.sh USERNAME [--bank-id BANK_ID] [--provider PROVIDER]

set -euo pipefail

# Run from the directory this script lives in, so relative paths resolve.
cd "$(dirname "$0")"

# Prefer the project virtualenv if it exists (has requests/python-dotenv installed).
if [ -z "${PYTHON:-}" ] && [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
fi
PYTHON="${PYTHON:-python3}"

exec "$PYTHON" show_user_dynamic_entity_roles.py "$@"
