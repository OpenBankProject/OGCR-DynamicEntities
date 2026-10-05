#!/usr/bin/env bash
#
# time_registry_query.sh
#
# Time the registry Dynamic Query endpoint (/registry/activities-query): log each
# call's time in ms and how many records it returned, by running
# time_registry_query.py. Read-only. All arguments are passed through.
#
# Usage:
#   ./time_registry_query.sh [--runs N] [--params "obp_limit=10"] [--auth]
#
# Lines are also appended to logs/time_registry_query.log.
# Host and space come from your .env (OBP_HOSTNAME, OBP_ENTITY_SPACE_ID).

set -euo pipefail

# Run from the directory this script lives in, so relative paths resolve.
cd "$(dirname "$0")"

# Prefer the project virtualenv if it exists (has requests installed).
if [ -z "${PYTHON:-}" ] && [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
fi
PYTHON="${PYTHON:-python3}"

exec "$PYTHON" time_registry_query.py "$@"
