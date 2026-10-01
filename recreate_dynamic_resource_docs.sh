#!/usr/bin/env bash
#
# recreate_dynamic_resource_docs.sh
#
# Recreate the OGCR Dynamic Resource Docs (the DOCS in dynamic_resource_docs.py,
# e.g. registry_activities) from their .scala files. For each doc:
#   1. Compile it (dry run, nothing stored); stop if it doesn't compile, so the
#      doc already on OBP is left in place.
#   2. Delete the doc on OBP, if there is one.
#   3. Create it again.
#   4. Call it anonymously to check it is served and public. OBP caches its list
#      of resource docs (40s by default), so a 404 is retried for up to 90s.
#
# Usage:
#   ./recreate_dynamic_resource_docs.sh [DOC ...] [--yes] [--dry-run]
#
# Without DOC names, every doc in dynamic_resource_docs.py is recreated.
#
# --dry-run only compiles each doc (OBP's compile endpoint stores nothing) and
# lists the docs on OBP, so you can see which would be deleted; it changes
# nothing and asks no question.
#
# It first shows the host it will work on and asks for confirmation; --yes skips
# the question (for automation). Without a terminal to ask on and without --yes,
# it stops.
#
# Notes:
#   - Token/host come from obp_client.py (or your .env), same as the Python scripts.
#   - The .scala reads its entities from SPACE_BANK_ID, which must match
#     OBP_ENTITY_SPACE_ID; dynamic_resource_docs.py refuses to push it otherwise.
#   - See dynamic_resource_docs.py for the OBP props and Roles this needs.

set -euo pipefail

# Run from the directory this script lives in, so relative paths resolve.
cd "$(dirname "$0")"

# Prefer the project virtualenv if it exists (has requests installed).
if [ -z "${PYTHON:-}" ] && [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
fi
PYTHON="${PYTHON:-python3}"

ASSUME_YES=false
DRY_RUN=false
DOC_NAMES=()
for arg in "$@"; do
  case "$arg" in
    --yes) ASSUME_YES=true ;;
    --dry-run) DRY_RUN=true ;;
    -*) echo "Unknown option: $arg" >&2; exit 2 ;;
    *) DOC_NAMES+=("$arg") ;;
  esac
done
if [ ${#DOC_NAMES[@]} -eq 0 ]; then
  read -r -a DOC_NAMES <<< "$("$PYTHON" -c 'from dynamic_resource_docs import DOCS; print(*DOCS)')"
fi

TARGET_HOST="$("$PYTHON" -c 'from obp_client import obp_host; print(obp_host)')"

if [ "$DRY_RUN" = true ]; then
  echo "[DRY RUN] Nothing will be changed on ${TARGET_HOST}"
  echo "[DRY RUN] Would delete and recreate: ${DOC_NAMES[*]}"
  echo "[DRY RUN] Docs on OBP now (any of the above listed here would be deleted first):"
  "$PYTHON" dynamic_resource_docs.py list
  COMPILE_FAILED=false
  for doc in "${DOC_NAMES[@]}"; do
    echo "[DRY RUN] Compiling ${doc}"
    "$PYTHON" dynamic_resource_docs.py compile "$doc" || COMPILE_FAILED=true
  done
  if [ "$COMPILE_FAILED" = true ]; then
    echo "✗ Some docs don't compile; a real run would stop before deleting them." >&2
    exit 1
  fi
  echo "[DRY RUN] Done. Nothing was changed."
  exit 0
fi

echo "=================================================="
echo " About to DELETE and RECREATE the Dynamic Resource Docs"
echo "   Host: ${TARGET_HOST}"
echo "   Docs: ${DOC_NAMES[*]}"
echo "=================================================="
if [ "$ASSUME_YES" != true ]; then
  if [ ! -t 0 ]; then
    echo "No terminal to confirm on; re-run with --yes to proceed." >&2
    exit 1
  fi
  read -r -p "Type 'yes' to continue: " ANSWER
  if [ "$ANSWER" != "yes" ]; then
    echo "Aborted. Nothing was changed."
    exit 1
  fi
fi

VERIFY_FAILED=false
for doc in "${DOC_NAMES[@]}"; do
  echo
  echo "=================================================="
  echo " ${doc}"
  echo "=================================================="
  "$PYTHON" dynamic_resource_docs.py compile "$doc"
  "$PYTHON" dynamic_resource_docs.py delete "$doc"
  "$PYTHON" dynamic_resource_docs.py create "$doc"
  # Report a failed check (e.g. the create is waiting for approval) but still do the other docs.
  "$PYTHON" dynamic_resource_docs.py verify "$doc" --wait 90 || VERIFY_FAILED=true
done

echo
echo "Done. Dynamic Resource Docs recreated: ${DOC_NAMES[*]}"
if [ "$VERIFY_FAILED" = true ]; then
  echo "✗ Some docs failed the anonymous check; see above." >&2
  exit 1
fi
