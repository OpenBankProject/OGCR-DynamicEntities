#!/usr/bin/env bash
#
# setup_venv.sh
#
# Create the project virtualenv (.venv) and install requirements.txt into it.
# The .sh wrappers use .venv/bin/python when it exists, so run this once after cloning.
# Safe to re-run: an existing .venv is kept and its packages brought up to date.
#
# Usage:
#   ./setup_venv.sh            # create or update .venv
#   ./setup_venv.sh --fresh    # delete .venv first and start again
#
# requirements.txt pins numpy<2, which has no wheels for Python 3.13 and newer (nor
# does pandas 2.2). On those Pythons this installs numpy 2 and pandas 2.3.3+ instead;
# the scripts only use numpy through pandas, which supports both.

set -euo pipefail

# Run from the directory this script lives in, so relative paths resolve.
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
VENV=".venv"

FRESH=false
for arg in "$@"; do
  case "$arg" in
    --fresh) FRESH=true ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

PY_VERSION="$("$PYTHON" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
echo "Python: $("$PYTHON" --version) ($(command -v "$PYTHON"))"

if [ "$FRESH" = true ] && [ -d "$VENV" ]; then
  echo "Removing ${VENV} (--fresh)"
  rm -rf "$VENV"
fi

if [ ! -x "${VENV}/bin/python" ]; then
  # Debian / Ubuntu ship venv's pip bootstrap (ensurepip) in a separate package.
  if ! "$PYTHON" -c 'import ensurepip' 2>/dev/null; then
    echo "Python ${PY_VERSION} can't create a virtualenv: ensurepip is missing." >&2
    echo "Install it, then run this again:" >&2
    echo "  sudo apt install python${PY_VERSION}-venv" >&2
    exit 1
  fi
  echo "Creating ${VENV}"
  rm -rf "$VENV"  # a half-made one from an earlier failed attempt
  "$PYTHON" -m venv "$VENV"
else
  echo "Using existing ${VENV}"
fi

"${VENV}/bin/python" -m pip install --quiet --upgrade pip

REQUIREMENTS="requirements.txt"
if "${VENV}/bin/python" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 13) else 1)'; then
  REQUIREMENTS="$(mktemp)"
  trap 'rm -f "$REQUIREMENTS"' EXIT
  sed -E \
    -e 's/^numpy[^#]*/numpy>=2.3,<3/' \
    -e 's/^pandas[^#]*/pandas>=2.3.3,<3/' \
    requirements.txt > "$REQUIREMENTS"
  echo "Python ${PY_VERSION}: installing requirements.txt with numpy>=2.3,<3 and pandas>=2.3.3,<3"
else
  echo "Installing requirements.txt"
fi
"${VENV}/bin/python" -m pip install --quiet -r "$REQUIREMENTS"

# Fail here, not halfway through a pipeline run, if something didn't install.
"${VENV}/bin/python" -c 'import requests, dotenv, yaml, pandas, openpyxl, numpy; print(f"OK: pandas {pandas.__version__}, numpy {numpy.__version__}, openpyxl {openpyxl.__version__}")'

echo
echo "Done. The .sh wrappers will use ${VENV}/bin/python."
echo "To run a .py directly: ${VENV}/bin/python <script>.py, or source ${VENV}/bin/activate first."
