#!/usr/bin/env bash
#
# create_registry_demo_data.sh
#
# Create demo records for the registry endpoint (operators, activities, and the
# activity_verification and certificate_of_compliance rows it joins) by running
# create_registry_demo_data.py. All arguments are passed through.
#
# Usage:
#   ./create_registry_demo_data.sh [path/to/min_field_matrix.xlsx] [--token TOKEN] [--activities N]
#
# --activities N (default 10) generates activities 11..N as well.
#
# Notes:
#   - Run create_example_data.py (or recreate_dynamic_entities.sh) first: the new
#     activities reference the first existing parcel, certification scheme and
#     certification body.
#   - Rows already present are skipped, so it is safe to re-run.
#   - Credentials/host come from your .env, same as the Python scripts.

set -euo pipefail

# Run from the directory this script lives in, so relative paths resolve.
cd "$(dirname "$0")"

# Prefer the project virtualenv if it exists (has pandas/openpyxl/requests installed).
if [ -z "${PYTHON:-}" ] && [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
fi
PYTHON="${PYTHON:-python3}"

exec "$PYTHON" create_registry_demo_data.py "$@"
