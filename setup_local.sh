#!/usr/bin/env bash
#
# setup_local.sh
#
# Set up the OGCR dynamic entities on a fresh LOCAL OBP-API, from start to finish:
#   1. Check DirectLogin works (.env: LOCAL_OBP_USERNAME / _PASSWORD / _CONSUMER_KEY).
#   2. Grant the logged in user CanCreateBank, if they don't hold it. OBP only allows
#      this to a user who may grant Roles, e.g. one in super_admin_user_ids.
#   3. Create the space bank (OBP_ENTITY_SPACE_ID, default ogcr) if it doesn't exist.
#   4. Regenerate entities_output.txt from the sheet and grant the user the definition,
#      Domain API and group Roles (create_entitlements.sh).
#   5. Check login and those Roles (check_login_and_roles.sh --no-entities). The record
#      Roles can't be checked yet: OBP grants them to whoever creates an entity, in step 6.
#   6. Recreate the entities, example data, Role Groups and resource docs
#      (recreate_dynamic_entities.sh, which asks for confirmation unless --yes), then
#      grant any record Roles still missing and check all the Roles.
#   7. Create the chain entities with OGCR-chain-cache's setup-entities.sh, if it's there.
#
# Usage:
#   ./setup_local.sh [--yes] [--no-recreate] [--no-chain]
#
# --yes          pass --yes to recreate_dynamic_entities.sh (no confirmation)
# --no-recreate  stop after step 5 (Roles in place, nothing recreated)
# --no-chain     skip step 7
#
# Always LOCAL: it refuses to run with OBP_TARGET / --target set to anything else.
# Every step is safe to re-run; Roles and the bank are only created when missing.
# Run ./setup_venv.sh first.

set -euo pipefail

# Run from the directory this script lives in, so relative paths resolve.
cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
  echo "No .venv; run ./setup_venv.sh first." >&2
  exit 1
fi
PYTHON=".venv/bin/python"
export PYTHON

ASSUME_YES=false
RECREATE=true
CHAIN=true
for arg in "$@"; do
  case "$arg" in
    --yes) ASSUME_YES=true ;;
    --no-recreate) RECREATE=false ;;
    --no-chain) CHAIN=false ;;
    --target=*|-*) echo "Unknown option: $arg (this script is LOCAL only)" >&2; exit 2 ;;
    *) echo "Unknown argument: $arg" >&2; exit 2 ;;
  esac
done

if [ -n "${OBP_TARGET:-}" ] && [ "$(echo "$OBP_TARGET" | tr '[:lower:]' '[:upper:]')" != "LOCAL" ]; then
  echo "setup_local.sh only works on LOCAL, not OBP_TARGET=${OBP_TARGET}." >&2
  exit 2
fi
export OBP_TARGET=LOCAL

CHAIN_SETUP="../OGCR-chain-cache/scripts/setup-entities.sh"

step() {
  echo
  echo "=================================================="
  echo " $1"
  echo "=================================================="
}

step "STEP 1-2: Log in, and make sure the user holds CanCreateBank"
# Logs in through obp_client.py (which also checks OBP is reachable) and prints
# what it did; never prints the token.
OBP_LOG_LEVEL="${OBP_LOG_LEVEL:-WARNING}" "$PYTHON" - <<'EOF'
import sys
import obp_target
from obp_client import token, obp_host, session, authorization, require_user_mode

require_user_mode("setup_local.sh")
if not token:
	sys.exit("✗ DirectLogin failed; check LOCAL_OBP_USERNAME, LOCAL_OBP_PASSWORD and LOCAL_OBP_CONSUMER_KEY in .env")
headers = {"Authorization": authorization(token), "Content-Type": "application/json"}

print(f"Host: {obp_host}  ({obp_target.describe()})")
me = session.get(f"{obp_host}/obp/v6.0.0/users/current", headers=headers)
if me.status_code != 200:
	sys.exit(f"✗ Could not read the current user ({me.status_code}): {me.text[:300]}")
user = me.json()
user_id = user["user_id"]
print(f"✓ Logged in as {user.get('username')} (user_id {user_id})")

held = {(e.get("role_name"), e.get("bank_id", "")) for e in user.get("entitlements", {}).get("list", [])}
if ("CanCreateBank", "") in held:
	print("✓ Already holds CanCreateBank")
else:
	r = session.post(f"{obp_host}/obp/v7.0.0/users/{user_id}/entitlements", headers=headers,
		json={"bank_id": "", "role_name": "CanCreateBank"})
	if r.status_code not in (200, 201):
		sys.exit(f"✗ Could not grant CanCreateBank ({r.status_code}): {r.text[:300]}\n"
			"  Granting Roles needs CanCreateEntitlementAtAnyBank, or the user's id in super_admin_user_ids in OBP-API's props.")
	print("✓ Granted CanCreateBank")
EOF

step "STEP 3: Space bank"
./create_space_bank.sh

step "STEP 4: Roles for the entities"
"$PYTHON" parse_minimum_fields.py --save
./create_entitlements.sh

step "STEP 5: Check login and the Roles needed to create the entities"
./check_login_and_roles.sh --no-entities

if [ "$RECREATE" = true ]; then
  step "STEP 6: Recreate the dynamic entities"
  if [ "$ASSUME_YES" = true ]; then
    ./recreate_dynamic_entities.sh --yes
  else
    ./recreate_dynamic_entities.sh
  fi
  step "STEP 6: Record Roles for the entities"
  ./create_entitlements.sh
  ./check_login_and_roles.sh
else
  echo
  echo "Skipping the recreate (--no-recreate). Run ./recreate_dynamic_entities.sh when ready."
fi

if [ "$CHAIN" = true ] && [ "$RECREATE" = true ]; then
  step "STEP 7: Chain entities (OGCR-chain-cache)"
  if [ -x "$CHAIN_SETUP" ]; then
    "$CHAIN_SETUP"
  else
    echo "No ${CHAIN_SETUP}; skipping. Clone OGCR-chain-cache next to this repo and run its scripts/setup-entities.sh."
  fi
fi

echo
echo "Done."
