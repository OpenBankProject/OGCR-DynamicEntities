"""Time the registry Dynamic Query endpoint: how long each call takes and how many records it returns.

Calls GET /obp/dynamic-endpoint/banks/<space>/dynamic-resource-doc/registry/activities-query
(the registry_activities_query doc in dynamic_resource_docs.py) anonymously, as the
public registry pages do, a number of times in a row. Each call is logged with its
time in ms, its HTTP status, the number of records returned and the query's `count`.
The lines are printed and appended to logs/time_registry_query.log, so runs can be
compared over time (e.g. before and after the indexes are built: ./check_indexing.sh).

The first call is often slower (connection set-up, OBP's caches), so it is reported
but left out of the summary when there is more than one run.

Usage:
    python3 time_registry_query.py [--runs N] [--params "obp_limit=10&obp_sort_by=name"] [--auth]

Exits 0 when every call answered 200, 1 otherwise.
"""

import argparse
import datetime
import statistics
import sys
import time
from pathlib import Path

from dynamic_resource_docs import DOCS
from obp_client import obp_host, session, token
from obp_space import SPACE_ID

LOG_FILE = Path(__file__).parent / "logs" / "time_registry_query.log"
DOC = DOCS["registry_activities_query"]


def query_url():
	return f"{obp_host}/obp/dynamic-endpoint/banks/{SPACE_ID or 'SYS'}/dynamic-resource-doc{DOC['request_url']}"


def main():
	parser = argparse.ArgumentParser(description="Time the registry Dynamic Query endpoint.")
	parser.add_argument("--runs", type=int, default=5, help="Number of calls (default 5)")
	parser.add_argument("--params", default="", help="Query string to add, e.g. \"obp_limit=10\"")
	parser.add_argument("--auth", action="store_true", help="Call as the logged in user instead of anonymously")
	args = parser.parse_args()

	url = query_url() + (f"?{args.params}" if args.params else "")
	headers = {"Authorization": f"DirectLogin token={token}"} if args.auth else {}
	who = "logged in" if args.auth else "anonymous"
	LOG_FILE.parent.mkdir(exist_ok=True)

	def log(line):
		print(line)
		with LOG_FILE.open("a") as f:
			f.write(line + "\n")

	log(f"# {datetime.datetime.now().isoformat(timespec='seconds')}  {who} GET {url}  runs={args.runs}")
	times, ok = [], True
	for run in range(1, args.runs + 1):
		start = time.perf_counter()
		resp = session.get(url, headers=headers, timeout=120)
		ms = (time.perf_counter() - start) * 1000
		records = count = "-"
		if resp.ok:
			body = resp.json()
			records = len(body.get("activities", []))
			count = body.get("count", "-")
			times.append(ms)
		else:
			ok = False
		log(f"run {run}: {ms:8.1f} ms  HTTP {resp.status_code}  records={records}  count={count}")
		if not resp.ok:
			log(f"  {resp.text[:300]}")

	measured = times[1:] if len(times) > 1 else times
	if measured:
		log(f"summary ({len(measured)} call(s){', first left out' if len(times) > 1 else ''}): "
			f"min {min(measured):.1f} ms, median {statistics.median(measured):.1f} ms, max {max(measured):.1f} ms")
	return 0 if ok else 1


if __name__ == "__main__":
	sys.exit(main())
