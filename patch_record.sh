#!/usr/bin/env bash
#
# patch_record.sh
#
# Change fields of one dynamic entity record on OBP, leaving its other fields as
# they are, by running patch_record.py. All arguments are passed through.
#
# Usage:
#   ./patch_record.sh ENTITY RECORD_ID FIELD=VALUE [FIELD=VALUE ...] [--yes]
#
# Example:
#   ./patch_record.sh activity a_05OFWI037022 country_id=DE --yes
#
# Without --yes it only shows the current and new values.
# Host and space come from your .env (OBP_HOSTNAME, OBP_ENTITY_SPACE_ID).

set -euo pipefail

# Run from the directory this script lives in, so relative paths resolve.
cd "$(dirname "$0")"

# Prefer the project virtualenv if it exists (has requests installed).
if [ -z "${PYTHON:-}" ] && [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
fi
PYTHON="${PYTHON:-python3}"

exec "$PYTHON" patch_record.py "$@"
