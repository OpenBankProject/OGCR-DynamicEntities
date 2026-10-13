#!/usr/bin/env bash
#
# domain_api.sh
#
# Manage the Domain API of the space (OBP_ENTITY_SPACE_ID), which publishes its
# entities and Dynamic Resource Docs under a base path of its own (default
# crcf/<space>/v1), by running domain_api.py. All arguments are passed through.
#
# Usage:
#   ./domain_api.sh list
#   ./domain_api.sh create --title "..." [--base-path crcf/ogcr/v1] [--version 1.0.0] [--description ...] [--publicly-discoverable true|false]
#   ./domain_api.sh update [--version 1.1.0] [--title ...] [--description ...] [--publicly-discoverable true|false]
#   ./domain_api.sh delete
#   ./domain_api.sh verify        # is the base path served?
#
# Notes:
#   - Credentials/host/OBP_ENTITY_SPACE_ID come from your .env.
#   - Needs CanCreateDomainApi / CanGetDomainApis / CanUpdateDomainApi /
#     CanDeleteDomainApi at the space's bank id.

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

exec "$PYTHON" domain_api.py "$@"
