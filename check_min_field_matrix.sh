#!/usr/bin/env bash
#
# check_min_field_matrix.sh
#
# Check the OGCR minimum fields spreadsheet (offline, read-only) by running
# check_min_field_matrix.py. All arguments are passed through.
#
# Usage:
#   ./check_min_field_matrix.sh [path/to/min_field_matrix.xlsx] [--strict]
#
# Exit code is the Python script's: 0 no errors, 1 errors (or warnings with --strict).

set -euo pipefail

# Run from the directory this script lives in, so relative paths resolve.
cd "$(dirname "$0")"

# Prefer the project virtualenv if it exists (has pandas/openpyxl installed).
if [ -z "${PYTHON:-}" ] && [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
fi
PYTHON="${PYTHON:-python3}"

exec "$PYTHON" check_min_field_matrix.py "$@"
