#!/usr/bin/env bash
#
# publish_smart_contracts_glossary_item.sh
#
# Publish OGCR-Smart-Contracts/docs/glossary_item.md as the Dynamic Glossary
# Item "OGCR Smart Contracts", by running publish_architecture_glossary_item.py.
# The text lives next to the contracts so it changes with them; this repo only
# publishes it. "OGCR Architecture" embeds it, so publish this one first.
# Reports only unless --yes; never replaces edits made on OBP unless --overwrite.
# All arguments are passed through.
#
# The contracts repo is expected next to this one; set OGCR_SMART_CONTRACTS_DIR
# if it is elsewhere.
#
# Usage:
#   ./publish_smart_contracts_glossary_item.sh [--yes] [--overwrite] [--pull]
#
# Exit code 0 on success (or nothing to do), 1 otherwise.

set -euo pipefail

# Run from the directory this script lives in, so relative paths resolve.
cd "$(dirname "$0")"

CONTRACTS_DIR="${OGCR_SMART_CONTRACTS_DIR:-../OGCR-Smart-Contracts}"
SOURCE="$CONTRACTS_DIR/docs/glossary_item.md"

if [ ! -f "$SOURCE" ]; then
  echo "Not found: $SOURCE (clone OGCR-Smart-Contracts next to this repo, or set OGCR_SMART_CONTRACTS_DIR)" >&2
  exit 1
fi

# Prefer the project virtualenv if it exists.
if [ -z "${PYTHON:-}" ] && [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
fi
PYTHON="${PYTHON:-python3}"

# Run on the OBP target: LOCAL (default), PROD or BOTH, from --target= or OBP_TARGET.
source ./target.sh

exec "$PYTHON" publish_architecture_glossary_item.py \
  --source "$SOURCE" --title "OGCR Smart Contracts" "$@"
