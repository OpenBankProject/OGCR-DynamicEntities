#!/usr/bin/env bash
#
# publish_architecture_page.sh
#
# Publish architecture_page.html as an App Studio page (the obp_portal_page
# record shown on the Portal at /pages/ogcr-architecture), by running
# publish_architecture_page.py. Reports only unless --yes; never replaces edits
# made in App Studio unless --overwrite. All arguments are passed through.
#
# Usage:
#   ./publish_architecture_page.sh [--yes] [--publish|--draft] [--overwrite] [--pull]
#
# Exit code 0 on success (or nothing to do), 1 otherwise.

set -euo pipefail

# Run from the directory this script lives in, so relative paths resolve.
cd "$(dirname "$0")"

# Prefer the project virtualenv if it exists.
if [ -z "${PYTHON:-}" ] && [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
fi
PYTHON="${PYTHON:-python3}"

exec "$PYTHON" publish_architecture_page.py "$@"
