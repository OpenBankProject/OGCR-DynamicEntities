#!/usr/bin/env bash
#
# create_space_bank.sh
#
# Make sure the bank (aka Space) named by OBP_ENTITY_SPACE_ID exists, creating
# it if not, by running create_space_bank.py. With OBP_ENTITY_SPACE_ID empty
# (system level entities) there is nothing to do. All arguments are passed through.
#
# Usage:
#   ./create_space_bank.sh [--full-name "OGCR ..."]
#
# Notes:
#   - Credentials/host/OBP_ENTITY_SPACE_ID come from your .env.
#   - Creating a bank needs the Role CanCreateBank.
#   - Exit code is the Python script's: 0 bank exists or was created, 1 failed.

set -euo pipefail

# Run from the directory this script lives in, so relative paths resolve.
cd "$(dirname "$0")"

# Prefer the project virtualenv if it exists (has requests/python-dotenv installed).
if [ -z "${PYTHON:-}" ] && [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
fi
PYTHON="${PYTHON:-python3}"

exec "$PYTHON" create_space_bank.py "$@"
