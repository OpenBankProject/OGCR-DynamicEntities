#!/usr/bin/env bash
#
# check_query_fields.sh
#
# Check that the Dynamic Queries only read fields the spreadsheet has (offline,
# read-only) by running check_query_fields.py. All arguments are passed through.
#
# Usage:
#   ./check_query_fields.sh [path/to/min_field_matrix.xlsx]
#
# Exit code is the Python script's: 0 every field found, 1 at least one missing.

set -euo pipefail

# Run from the directory this script lives in, so relative paths resolve.
cd "$(dirname "$0")"

# Prefer the project virtualenv if it exists (has pandas/openpyxl installed).
if [ -z "${PYTHON:-}" ] && [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
fi
PYTHON="${PYTHON:-python3}"

exec "$PYTHON" check_query_fields.py "$@"
