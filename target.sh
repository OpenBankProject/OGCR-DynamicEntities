# target.sh -- sourced by the .sh wrappers, right after they pick $PYTHON.
#
# Runs the wrapper on one or both OBP targets (see obp_target.py):
#
#   ./some_script.sh ...                   LOCAL (the default)
#   ./some_script.sh --target=PROD ...     PROD only
#   ./some_script.sh --target=BOTH ...     LOCAL, then PROD if LOCAL succeeded
#   OBP_TARGET=BOTH ./some_script.sh ...   the same, from the environment
#
# It re-runs the calling script once per target with OBP_TARGET set to LOCAL or
# PROD, then exits with the first failure's code (or 0). Wrappers called from such
# a run (as recreate_dynamic_entities.sh calls others) inherit its target and run
# just once, so they don't loop again.

_target_args=()
for _target_arg in "$@"; do
  case "$_target_arg" in
    --target=*) OBP_TARGET="${_target_arg#--target=}" ;;
    *) _target_args+=("$_target_arg") ;;
  esac
done
set -- ${_target_args[@]+"${_target_args[@]}"}

if [ -z "${_OBP_TARGET_INNER:-}" ]; then
  case "$(echo "${OBP_TARGET:-LOCAL}" | tr '[:lower:]' '[:upper:]')" in
    LOCAL) _target_list=(LOCAL) ;;
    PROD) _target_list=(PROD) ;;
    BOTH) _target_list=(LOCAL PROD) ;;
    *) echo "--target / OBP_TARGET must be LOCAL, PROD or BOTH, not '${OBP_TARGET}'" >&2; exit 2 ;;
  esac
  # Check every target's settings before running on any of them.
  _target_where=()
  for _target in "${_target_list[@]}"; do
    _target_desc="$(OBP_TARGET="$_target" "$PYTHON" -c 'import obp_target; print(obp_target.describe())')" || exit 1
    _target_where+=("$_target_desc")
  done
  _target_i=0
  for _target in "${_target_list[@]}"; do
    echo "=== ${_target_where[$_target_i]} ==="
    _target_i=$((_target_i + 1))
    _target_status=0
    OBP_TARGET="$_target" _OBP_TARGET_INNER=1 bash "$(pwd)/$(basename "$0")" "$@" || _target_status=$?
    if [ "$_target_status" -ne 0 ]; then
      if [ "${#_target_list[@]}" -gt 1 ]; then
        echo "=== ${_target} failed (exit ${_target_status}); stopping before the next target ===" >&2
      fi
      exit "$_target_status"
    fi
  done
  exit 0
fi
export OBP_TARGET _OBP_TARGET_INNER
