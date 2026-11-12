#!/usr/bin/env bash
# With OGCR_CHAIN_SETUP set, recreate_dynamic_entities.sh creates the chain entities
# (OGCR-chain-cache's setup-entities.sh) right after the sheet's entities, and before
# the index check and the Dynamic Resource Docs: the registry Queries join
# activity_on_chain, which in turn references activity.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(dirname "$HERE")"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cp "$REPO"/recreate_dynamic_entities.sh "$REPO"/recreate_dynamic_resource_docs.sh "$REPO"/check_indexing.sh \
  "$REPO"/create_registry_demo_data.sh "$REPO"/target.sh "$WORK"/
export PYTHON="$HERE/fake_python.sh" FAKE_LOG="$WORK/calls.log" FAKE_DOCS="ok_doc" _OBP_TARGET_INNER=1 OBP_TARGET=LOCAL
printf '#!/usr/bin/env bash\necho "CHAIN SETUP" >> "%s"\n' "$FAKE_LOG" > "$WORK/fake_chain_setup.sh"
chmod +x "$WORK/fake_chain_setup.sh"
export OGCR_CHAIN_SETUP="$WORK/fake_chain_setup.sh"

out="$(cd "$WORK" && ./recreate_dynamic_entities.sh --yes 2>&1)"
rc=$?
line_of() { grep -n -m1 -e "$1" "$FAKE_LOG" | cut -d: -f1; }
create=$(line_of "parse_minimum_fields.py .* --create")
chain=$(line_of "CHAIN SETUP")
index=$(line_of "check_indexing.py")
docs=$(line_of "dynamic_resource_docs.py create ok_doc")

fail=0
check() { if eval "$1"; then echo "  ok   $2"; else echo "  FAIL $2"; fail=1; fi; }
check '[ "$rc" -eq 0 ]' "the run succeeds (got $rc)"
check '[ -n "$chain" ]' "the chain setup runs"
check '[ -n "$chain" ] && [ -n "$create" ] && [ "$create" -lt "$chain" ]' "after the sheet's entities are created"
check '[ -n "$chain" ] && [ -n "$index" ] && [ "$chain" -lt "$index" ]' "before the index check"
check '[ -n "$chain" ] && [ -n "$docs" ] && [ "$chain" -lt "$docs" ]' "before the Dynamic Resource Docs"
if [ "$fail" -ne 0 ]; then
  echo "--- calls ---"; cat "$FAKE_LOG"; echo "--- output ---"; echo "$out" | tail -30
fi
exit "$fail"
