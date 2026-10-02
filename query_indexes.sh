#!/usr/bin/env bash
#
# query_indexes.sh
#
# List the dynamic entity fields the Dynamic Query declarations (*_query.json)
# need indexed, and which query needs each, by running query_indexes.py.
# Offline and read-only: it changes nothing. ./update_dynamic_entities.sh
# applies the indexes on OBP.
#
# Usage:
#   ./query_indexes.sh

set -euo pipefail

# Run from the directory this script lives in, so relative paths resolve.
cd "$(dirname "$0")"

# Prefer the project virtualenv if it exists.
if [ -z "${PYTHON:-}" ] && [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
fi
PYTHON="${PYTHON:-python3}"

exec "$PYTHON" query_indexes.py "$@"
