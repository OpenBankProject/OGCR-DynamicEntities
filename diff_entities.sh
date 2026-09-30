#!/usr/bin/env bash
#
# diff_entities.sh
#
# Show how the dynamic entities on OBP differ from min_field_matrix.xlsx, at one bank id.
# Runs diff_entities.py; all arguments are passed through. Read-only.
#
# Usage:
#   ./diff_entities.sh [path/to/min_field_matrix.xlsx] [--bank-id BANK_ID] [--structure-only]

set -euo pipefail

# Run from the directory this script lives in, so relative paths resolve.
cd "$(dirname "$0")"

# Prefer the project virtualenv if it exists (has requests/python-dotenv installed).
if [ -z "${PYTHON:-}" ] && [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
fi
PYTHON="${PYTHON:-python3}"

exec "$PYTHON" diff_entities.py "$@"
