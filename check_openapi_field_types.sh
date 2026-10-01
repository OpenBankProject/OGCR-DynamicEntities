#!/usr/bin/env bash
#
# check_openapi_field_types.sh
#
# Download OBP's generated OpenAPI document for the dynamic entities and check
# every field's type in it against min_field_matrix.xlsx. Host and space come
# from .env (OBP_HOSTNAME, OBP_ENTITY_SPACE_ID).
# Runs check_openapi_field_types.py; all arguments are passed through. Read-only.
#
# Usage:
#   ./check_openapi_field_types.sh [path/to/min_field_matrix.xlsx]

set -euo pipefail

# Run from the directory this script lives in, so relative paths resolve.
cd "$(dirname "$0")"

# Prefer the project virtualenv if it exists (has requests/PyYAML installed).
if [ -z "${PYTHON:-}" ] && [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
fi
PYTHON="${PYTHON:-python3}"

exec "$PYTHON" check_openapi_field_types.py "$@"
