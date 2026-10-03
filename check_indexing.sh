#!/usr/bin/env bash
#
# check_indexing.sh
#
# Check that OBP actually uses the dynamic entity indexes, by running
# check_indexing.py: the props (dynamic_entity.indexing.backend=auto), that each
# entity's index is built, and that the Dynamic Queries (*_query.json) are served
# from them. Read-only. All arguments are passed through.
#
# Usage:
#   ./check_indexing.sh [--wait SECONDS]
#
# Exit code 0 when OBP uses the indexes, 1 otherwise.

set -euo pipefail

# Run from the directory this script lives in, so relative paths resolve.
cd "$(dirname "$0")"

# Prefer the project virtualenv if it exists.
if [ -z "${PYTHON:-}" ] && [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
fi
PYTHON="${PYTHON:-python3}"

exec "$PYTHON" check_indexing.py "$@"
