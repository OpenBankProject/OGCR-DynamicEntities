#!/usr/bin/env bash
#
# publish_architecture_glossary_item.sh
#
# Publish architecture_glossary_item.md as the Dynamic Glossary Item "OGCR
# Architecture", by running publish_architecture_glossary_item.py. Reports only
# unless --yes; never replaces edits made on OBP unless --overwrite. All
# arguments are passed through.
#
# Usage:
#   ./publish_architecture_glossary_item.sh [--yes] [--overwrite] [--pull]
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

exec "$PYTHON" publish_architecture_glossary_item.py "$@"
