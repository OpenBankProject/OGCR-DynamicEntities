#!/usr/bin/env bash
#
# publish_smart_contracts_page.sh
#
# Publish smart_contracts_glossary_app.html as the App /pages/ogcr-smart-contracts,
# which shows the Dynamic Glossary Item "OGCR Smart Contracts" (published by
# publish_smart_contracts_glossary_item.sh, so publish that first), by running
# publish_architecture_page.py. Reports only unless --yes; never replaces edits
# made in App Studio unless --overwrite. All arguments are passed through.
#
# Usage:
#   ./publish_smart_contracts_page.sh [--yes] [--overwrite] [--pull] [--publish | --draft]
#
# Exit code 0 on success (or nothing to do), 1 otherwise.

set -euo pipefail

# Run from the directory this script lives in, so relative paths resolve.
cd "$(dirname "$0")"

# Prefer the project virtualenv if it exists (has requests/python-dotenv installed).
if [ -z "${PYTHON:-}" ] && [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
fi
PYTHON="${PYTHON:-python3}"

# Run on the OBP target: LOCAL (default), PROD or BOTH, from --target= or OBP_TARGET.
source ./target.sh

exec "$PYTHON" publish_architecture_page.py --kind app --source smart_contracts_glossary_app.html \
  --slug ogcr-smart-contracts --title "OGCR Smart Contracts" "$@"
