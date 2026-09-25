#!/usr/bin/env bash
#
# check_login_and_roles.sh
#
# Check DirectLogin and the current user's Roles (read-only) by running
# check_login_and_roles.py. All arguments are passed through.
#
# Usage:
#   ./check_login_and_roles.sh [path/to/entities_output.txt] [--no-entities]
#                              [--role ROLE[@BANK_ID] ...] [--list]
#
# Exit code is the Python script's: 0 all OK, 1 login failed, 2 Role(s) missing.

set -euo pipefail

# Run from the directory this script lives in, so relative paths resolve.
cd "$(dirname "$0")"

# Prefer the project virtualenv if it exists (has requests/python-dotenv installed).
if [ -z "${PYTHON:-}" ] && [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
fi
PYTHON="${PYTHON:-python3}"

exec "$PYTHON" check_login_and_roles.py "$@"
