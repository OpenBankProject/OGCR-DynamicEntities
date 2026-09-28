"""Timing logs, to see which operations take a while.

    with timed("create entity parcel"):
        ...
    print_slowest()

Each `timed` block that takes longer than SHOW_ABOVE_SECONDS prints
`⏱ <seconds>s  <label>` when it ends (even if it raises). `print_slowest`
lists the slowest of those at the end of a script (the total still counts them all).

When OGCR_LOG_FILE is set (recreate_ogcr_entities.sh sets it to its log), the
faster blocks are written there too, so the log has every timing while the
console only shows the slow ones.
"""

import os
import time
from contextlib import contextmanager

SHOW_ABOVE_SECONDS = 1.0

_timings = []  # (seconds, label)


@contextmanager
def timed(label):
	start = time.monotonic()
	try:
		yield
	finally:
		seconds = time.monotonic() - start
		_timings.append((seconds, label))
		line = f"⏱ {seconds:7.2f}s  {label}"
		if seconds > SHOW_ABOVE_SECONDS:
			print(line, flush=True)
		elif os.getenv("OGCR_LOG_FILE"):
			try:
				with open(os.environ["OGCR_LOG_FILE"], "a", encoding="utf-8") as f:
					f.write(line + "\n")
			except OSError:
				pass  # the log is a convenience; never fail the operation over it


def print_slowest(n=5, title="Slowest"):
	"""List up to `n` of the slowest operations, only those over SHOW_ABOVE_SECONDS."""
	if not _timings:
		return
	total = sum(s for s, _ in _timings)
	slow = sorted((t for t in _timings if t[0] > SHOW_ABOVE_SECONDS), reverse=True)
	if not slow:
		print(f"⏱ None of {len(_timings)} timed operations took over {SHOW_ABOVE_SECONDS}s ({total:.1f}s in all)")
		return
	print(f"⏱ {title} {min(n, len(slow))} of {len(_timings)} timed operations ({total:.1f}s in all):")
	for seconds, label in slow[:n]:
		print(f"⏱ {seconds:7.2f}s  {label}")
