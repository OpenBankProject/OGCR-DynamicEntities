#!/usr/bin/env bash
# Stand-in for $PYTHON in the shell script tests: records every call in $FAKE_LOG and
# answers without touching OBP.
#
#   FAKE_LOG    file each call is appended to, one line per call
#   FAKE_DOCS   what `python -c '... DOCS ...'` prints (the doc names)
#   FAKE_FAIL   space separated <command>:<doc> pairs to fail, e.g. "compile:registry_activities"
echo "$*" >> "$FAKE_LOG"
if [ "${1:-}" = "-c" ]; then
  case "$2" in
    *describe*SPACE_ID*) printf 'http://fake\nbank ogcr\nogcr\n' ;;
    *obp_target*) echo "LOCAL (http://fake)" ;;
    *DOCS*) echo "${FAKE_DOCS:-}" ;;
    *obp_host*) echo "http://fake" ;;
  esac
  exit 0
fi
for rule in ${FAKE_FAIL:-}; do
  if [ "$rule" = "${2:-}:${3:-}" ]; then
    echo "fake failure: $2 $3" >&2
    exit 1
  fi
done
exit 0
