"""Check that OBP actually uses the dynamic entity indexes, not just that they are declared.

Declaring a field `"indexed": true` (parse_minimum_fields.py, update_dynamic_entities.py)
only asks OBP for an index. OBP serves filters, sorts and joins from it only when:

  * `dynamic_entity.indexing.backend=auto` is set in its props, and its db.url is Postgres
    (or SQL Server). Otherwise every read is filtered in memory, and obp_exists /
    obp_not_exists joins are refused with OBP-09022;
  * the index (OBP calls it the projection) has been built for that entity in this space.
    Until then a filter or sort on the field answers 409 OBP-09019, and a Dynamic Query
    quietly reads every record instead. Definitions saved before the prop was switched
    on are never built: re-save them (./update_dynamic_entities.sh --yes, or recreate).

Read-only. Three checks, all against the space in OBP_ENTITY_SPACE_ID:

  1. Props: each reverse join with a `where` in a *_query.json is run as an obp_exists
     query. 400 OBP-09022 means the prop is off (or the database isn't supported).
  2. Built: each entity the queries read is sorted on a field they index (its
     `<entity>_id` when it has one); 409 means its index isn't built. With --wait, retried until built or the time is up.
  3. Used: OBP's explain endpoint says how each *_query.json is answered; any page read or
     reverse join not served by the index is reported with OBP's reason. Needs the Role
     CanCreateDynamicResourceDoc; skipped with a warning without it.

Exit code 0 when every check passes, 1 otherwise.

Usage:
    python3 check_indexing.py [--wait SECONDS]
"""

import argparse
import json
import sys
import time
import urllib.parse
from pathlib import Path

from obp_client import token as TOKEN, obp_host as HOST, session
from obp_space import SPACE_ID, describe, record_path
from query_indexes import QUERY_FILES_GLOB, QUERY_INDEXED_FIELDS

HERE = Path(__file__).parent
EXPLAIN_URL = "/obp/v7.0.0/management/dynamic-resource-docs/explain"
PROP_OFF = "OBP-09022"
NOT_BUILT = "OBP-09019"
PROP_HELP = ("Set dynamic_entity.indexing.backend=auto in OBP's props (db.url must be Postgres), "
             "restart OBP, then re-save the definitions: ./update_dynamic_entities.sh --yes")
BUILD_HELP = ("If this persists, re-save the definitions so OBP builds the indexes: "
              "./update_dynamic_entities.sh --yes")


def headers():
	return {"Authorization": f"DirectLogin token={TOKEN}", "Content-Type": "application/json"}


def declarations():
	"""[(file name, declaration)] for every *_query.json."""
	return [(p.name, json.loads(p.read_text())) for p in sorted(HERE.glob(QUERY_FILES_GLOB))]


def is_reverse(join):
	"""A reverse join is linked by a field of the joined entity other than its own id."""
	return join.get("on") != f"{join.get('entity')}_id"


def get(entity, params):
	"""(status, OBP message or row count) of a list read."""
	resp = session.get(f"{HOST}{record_path(entity)}", params=params, headers=headers())
	try:
		body = resp.json()
	except ValueError:
		return resp.status_code, resp.text[:200]
	if resp.ok:
		return resp.status_code, f"{len(body.get(f'{entity}_list', []))} row(s)"
	return resp.status_code, body.get("message", resp.text[:200])


def check_props(decls):
	"""1. The prop: run each reverse join with a where as an obp_exists query."""
	print("1. Is the index backend on? (dynamic_entity.indexing.backend=auto)")
	probes = []
	for name, d in decls:
		for join in d.get("join") or []:
			if is_reverse(join) and join.get("where"):
				filters = ";".join(f"filter[{f}]={v}" for f, v in join["where"].items())
				probes.append((name, d["from"], join["entity"], f"via:{join['on']};{filters}"))
	if not probes:
		print("   no reverse join with a where in the queries; can't tell from here (see check 3)")
		return None
	ok = True
	for name, parent, child, clause in probes:
		status, message = get(parent, {f"obp_exists[{child}]": clause, "obp_limit": "1"})
		label = f"{parent} obp_exists[{child}]={clause}  ({name})"
		if status == 200:
			print(f"   ✓ {label}")
		elif PROP_OFF in message:
			print(f"   ✗ {label}\n     {message}\n     {PROP_HELP}")
			return False
		elif NOT_BUILT in message:
			# The backend is on (it would have refused with OBP-09022 otherwise); check 2 says what isn't built.
			print(f"   ✓ backend is on, but the join isn't served yet: {label}")
		else:
			print(f"   ✗ {label}\n     HTTP {status}: {message}")
			ok = False
	return ok


def sort_field(entity):
	"""`<entity>_id`, or for an entity without one (e.g. activity_verification) a field the queries index."""
	needed = QUERY_INDEXED_FIELDS.get(entity, set())
	own = f"{entity}_id"
	return own if own in needed or not needed else sorted(needed)[0]


def check_built(decls, wait):
	"""2. Each entity the queries read has its index built: sort on a field the queries index."""
	print("\n2. Are the indexes built?")
	entities = []
	for _, d in decls:
		for e in [d.get("from")] + [j.get("entity") for j in d.get("join") or []]:
			if e and e not in entities:
				entities.append(e)
	deadline = time.time() + wait
	pending = list(entities)
	while True:
		results = {e: get(e, {"obp_sort_by": sort_field(e), "obp_limit": "1"}) for e in pending}
		pending = [e for e, (status, _) in results.items() if status == 409]
		if not pending or time.time() >= deadline:
			break
		print(f"   {len(pending)} not built yet; retrying ({int(deadline - time.time())}s left)")
		time.sleep(min(10, max(1, deadline - time.time())))
	ok = True
	for e in entities:
		status, message = results.get(e, (200, ""))
		if status == 200:
			print(f"   ✓ {e} (sorted on {sort_field(e)})")
		else:
			ok = False
			print(f"   ✗ {e} (sorted on {sort_field(e)}): HTTP {status}: {message}")
	if not ok and any(results[e][0] == 409 for e in pending):
		print(f"     {BUILD_HELP}")
	return ok


def check_used(decls):
	"""3. OBP's explanation of each Dynamic Query: is every page read and reverse join indexed?"""
	print("\n3. Do the Dynamic Queries use the indexes? (OBP's explain)")
	ok = True
	for name, d in decls:
		body = {
			"method_body": urllib.parse.quote(json.dumps(d, separators=(",", ":"))),
			"bank_id": SPACE_ID or "SYS",
			# Sorting on an indexed field makes the page read eligible for the index.
			"caller_parameters": f"obp_sort_by={d['from']}_id",
		}
		resp = session.post(f"{HOST}{EXPLAIN_URL}", headers=headers(), json=body)
		if resp.status_code == 403:
			print(f"   ! {name}: skipped, needs the Role CanCreateDynamicResourceDoc")
			continue
		if not resp.ok:
			print(f"   ✗ {name}: HTTP {resp.status_code}: {resp.text[:300]}")
			ok = False
			continue
		for step in resp.json().get("steps", []):
			purpose = step.get("purpose", "")
			# Forward joins read by id and are never served by the index, by design.
			if "(forward)" in purpose:
				continue
			if step.get("backend") == "projection":
				print(f"   ✓ {name}: {purpose}")
			else:
				ok = False
				note = (step.get("notes") or [""])[0]
				print(f"   ✗ {name}: {purpose}\n     {note}")
	return ok


def main():
	parser = argparse.ArgumentParser(description="Check that OBP uses the dynamic entity indexes (read-only).")
	parser.add_argument("--wait", type=int, default=0, metavar="SECONDS",
	                    help="Keep retrying indexes that aren't built yet for up to this long (e.g. after a recreate).")
	args = parser.parse_args()

	if not TOKEN:
		sys.exit(f"Could not log in to {HOST} (see the error above); check the credentials in .env.")
	decls = declarations()
	print(f"Checking indexing on {HOST}, {describe()}, for {len(decls)} query file(s) ({QUERY_FILES_GLOB}).\n")
	props = check_props(decls)
	if props is False:
		sys.exit(1)
	built = check_built(decls, args.wait)
	used = check_used(decls)
	if props is not False and built and used:
		print("\n✓ OBP is using the indexes.")
		sys.exit(0)
	print("\n✗ OBP is not using every index; see above.")
	sys.exit(1)


if __name__ == "__main__":
	main()
