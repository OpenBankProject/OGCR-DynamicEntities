#!/usr/bin/env bash
# recreate_dynamic_resource_docs.sh must not stop at the first doc that fails: the
# others are still recreated, a doc that doesn't compile or whose entities are missing
# is left as it is on OBP (not deleted), and every failure is reported at the end.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(dirname "$HERE")"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cp "$REPO"/recreate_dynamic_resource_docs.sh "$REPO"/target.sh "$WORK"/
export PYTHON="$HERE/fake_python.sh" FAKE_LOG="$WORK/calls.log" _OBP_TARGET_INNER=1 OBP_TARGET=LOCAL
export FAKE_FAIL="compile:scala_doc check-entities:needs_chain"

out="$(cd "$WORK" && ./recreate_dynamic_resource_docs.sh scala_doc needs_chain ok_doc --yes 2>&1)"
rc=$?
calls="$(cat "$FAKE_LOG")"

fail=0
check() { if eval "$1"; then echo "  ok   $2"; else echo "  FAIL $2"; fail=1; fi; }
check '[ "$rc" -eq 1 ]' "exits 1 when a doc failed (got $rc)"
check 'grep -q "dynamic_resource_docs.py create ok_doc" <<< "$calls"' "ok_doc is still created after scala_doc fails"
check 'grep -q "dynamic_resource_docs.py verify ok_doc" <<< "$calls"' "ok_doc is verified"
check '! grep -q "dynamic_resource_docs.py delete scala_doc" <<< "$calls"' "a doc that doesn't compile is not deleted"
check '! grep -q "dynamic_resource_docs.py delete needs_chain" <<< "$calls"' "a doc whose entities are missing is not deleted"
check 'grep -q "scala_doc: compile" <<< "$out"' "the summary names scala_doc and the failed step"
check 'grep -q "needs_chain: check-entities" <<< "$out"' "the summary names needs_chain and the failed step"
if [ "$fail" -ne 0 ]; then
  echo "--- output ---"; echo "$out"
fi
exit "$fail"
