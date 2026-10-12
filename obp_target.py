"""Which OBP instance the scripts work on: LOCAL or PROD, picked by OBP_TARGET.

`.env` holds one set of settings per target, each prefixed with its name:

    LOCAL_OBP_HOSTNAME=http://localhost:8080
    PROD_OBP_HOSTNAME=https://dcr.ogcr.tesobe.com
    LOCAL_OBP_USERNAME=...    PROD_OBP_USERNAME=...    (and so on)

On import this loads `.env` and copies every `<TARGET>_X` to `X`, so the rest of
the code keeps reading the plain names (OBP_HOSTNAME, OBP_USERNAME, ...). A setting
with no prefixed version for the target (e.g. OBP_LOG_LEVEL) is used as it is,
shared by both targets.

OBP_TARGET defaults to LOCAL, so PROD is only ever used when asked for. Once a
`.env` uses prefixes, `<TARGET>_OBP_HOSTNAME` must be set, so a missing PROD setting
can't silently fall back to the plain (or LOCAL) one. A `.env` without any
prefixed settings works as before, with the plain names, as LOCAL; PROD is then
refused.

To run a script on both, use its .sh wrapper with --target=BOTH or OBP_TARGET=BOTH
(see target.sh); a .py run directly refuses BOTH.

No side effects on import beyond the environment (no login), so offline scripts can use it too.
"""
import os
import sys

from dotenv import load_dotenv

load_dotenv()

TARGETS = ("LOCAL", "PROD")

TARGET = os.getenv("OBP_TARGET", "LOCAL").strip().upper()
if TARGET == "BOTH":
	sys.exit("OBP_TARGET=BOTH only works with the .sh wrappers, which run once per target; "
		"run the .py with OBP_TARGET=LOCAL, then OBP_TARGET=PROD")
if TARGET not in TARGETS:
	sys.exit(f"OBP_TARGET must be one of {', '.join(TARGETS)}, not '{TARGET}'")

PREFIXED = any(name.startswith(f"{t}_") for name in os.environ for t in TARGETS)

if PREFIXED:
	if not os.getenv(f"{TARGET}_OBP_HOSTNAME"):
		sys.exit(f"OBP_TARGET is {TARGET} but {TARGET}_OBP_HOSTNAME is not set in .env or the environment")
	prefix = f"{TARGET}_"
	for name, value in list(os.environ.items()):
		if name.startswith(prefix):
			os.environ[name[len(prefix):]] = value
elif TARGET != "LOCAL":
	sys.exit(f"OBP_TARGET is {TARGET} but .env has no {TARGET}_ settings (only the plain OBP_* ones, used as LOCAL)")


def describe():
	"""The target and its host, for log messages, e.g. 'PROD (https://dcr.ogcr.tesobe.com)'."""
	host = os.getenv("OBP_HOSTNAME", "http://obp-api-internal-route-obp.apps-crc.testing")
	return f"{TARGET} ({host})" if PREFIXED else host
