#!/usr/bin/env bash
#
# check_client_credentials.sh
#
# Check which endpoints the scripts use accept an application token (OAuth2
# client credentials, as a Platform App) instead of a DirectLogin user, by
# running check_client_credentials.py. Read-only. Needs OIDC_ISSUER,
# OIDC_CLIENT_ID and OIDC_CLIENT_SECRET. All arguments are passed through.
#
# Usage:
#   ./check_client_credentials.sh [--entity ENTITY]

set -euo pipefail

# Run from the directory this script lives in, so relative paths resolve.
cd "$(dirname "$0")"

# Prefer the project virtualenv if it exists.
if [ -z "${PYTHON:-}" ] && [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
fi
PYTHON="${PYTHON:-python3}"

# Run on the OBP target: LOCAL (default), PROD or BOTH, from --target= or OBP_TARGET.
source ./target.sh

exec "$PYTHON" check_client_credentials.py "$@"
