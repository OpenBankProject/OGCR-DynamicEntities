#!/usr/bin/env bash
#
# check_login.sh
#
# Check that DirectLogin works (read-only) by running check_login.py.
# It doesn't check Roles: for those, run check_login_and_roles.sh.
#
# Usage:
#   ./check_login.sh [--target=LOCAL|PROD|BOTH]
#
# Exit code is the Python script's: 0 login OK, 1 login failed.

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

exec "$PYTHON" check_login.py "$@"
