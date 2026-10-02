#!/usr/bin/env bash
#
# update_dynamic_entities.sh
#
# Bring the dynamic entity definitions on OBP up to date with min_field_matrix.xlsx,
# in place, by running update_dynamic_entities.py. Unlike recreate_dynamic_entities.sh
# it deletes nothing, so records and users' Role grants (and their emails) stay.
# Changes OBP can't make in place are reported, with what to do instead.
# All arguments are passed through.
#
# Usage:
#   ./update_dynamic_entities.sh [path/to/min_field_matrix.xlsx] [--yes]
#
# Without --yes it only reports what it would do.

set -euo pipefail

# Run from the directory this script lives in, so relative paths resolve.
cd "$(dirname "$0")"

# Prefer the project virtualenv if it exists (has pandas/openpyxl/requests installed).
if [ -z "${PYTHON:-}" ] && [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
fi
PYTHON="${PYTHON:-python3}"

exec "$PYTHON" update_dynamic_entities.py "$@"
