"""Publish the architecture page (architecture_page.html) as an App Studio page on OBP.

App Studio (in the API Manager) keeps its pages as records of the system level dynamic
entity `obp_portal_page`, and the Portal shows the published ones at /pages/<slug>. This
script writes the same record App Studio would (through the v7.0.0 endpoints, at bank id SYS, the
system space), so the page can be edited further in App Studio afterwards.

Because someone may have edited the page in App Studio since it was last published, the
script never overwrites a page whose source differs from the file unless given
--overwrite. Use --pull to copy the App Studio version into the file instead, so the
edits are kept in this repo.

Reports only (missing / up to date / differs, with a diff), unless given --yes:

    python3 publish_architecture_page.py                      # report
    python3 publish_architecture_page.py --yes                # create it as a draft if missing
    python3 publish_architecture_page.py --yes --publish      # create or switch it to published
    python3 publish_architecture_page.py --yes --overwrite    # replace edits made in App Studio
    python3 publish_architecture_page.py --pull               # save the App Studio source to the file

The same script publishes architecture_glossary_app.html, an App that loads the Glossary Item
written by publish_architecture_glossary_item.py:

    python3 publish_architecture_page.py --kind app --source architecture_glossary_app.html \
        --slug ogcr-architecture-glossary --title "OGCR Architecture" --yes --publish

A new page is a draft (only visible in App Studio) unless --publish is given; an existing
page keeps its status unless --publish or --draft is given.

Needs the Roles CanGetDynamicEntityRecord_obp_portal_page, and to write,
CanCreateDynamicEntityRecord_obp_portal_page / CanUpdateDynamicEntityRecord_obp_portal_page,
all at bank id SYS. The entity itself is created by the API Manager when it starts.

Exit code 0 on success (or when there is nothing to do), 1 otherwise.
"""

import argparse
import datetime
import difflib
import sys
from pathlib import Path

from obp_client import obp_host, session, token, username

HERE = Path(__file__).parent
ENTITY = "obp_portal_page"
ID_FIELD = f"{ENTITY}_id"
# The system space: v7.0.0 addresses it as bank id SYS, and checks the Roles at SYS.
RECORDS_URL = f"{obp_host}/obp/v7.0.0/banks/SYS/dynamic-entities/{ENTITY}"
FIELDS = ["slug", "title", "kind", "status", "summary", "source", "author", "updated_at"]

DEFAULT_SOURCE = HERE / "architecture_page.html"
DEFAULT_SLUG = "ogcr-architecture"
DEFAULT_TITLE = "How the OGCR components work together"


def headers():
	return {"Authorization": f"DirectLogin token={token}", "Content-Type": "application/json"}


def refused(response, action):
	role = f"Can{action}DynamicEntityRecord_{ENTITY}"
	print(f"OBP refused to {action.lower()} {ENTITY} records: {response.status_code} {response.text}")
	if response.status_code == 404:
		print(f"The entity {ENTITY} doesn't exist yet. The API Manager creates it when it starts "
		      "(its consumer needs CanCreateDynamicEntityDefinition at SYS); see its App Studio Help page.")
	elif response.status_code in (401, 403):
		print(f"The user needs the Role {role} at bank id SYS.")
	return 1


def find_page(slug):
	"""(record or None, error exit code or None). The newest record with this slug, as the Portal picks it."""
	response = session.get(RECORDS_URL, headers=headers())
	if response.status_code != 200:
		return None, refused(response, "Get")
	body = response.json()
	list_key = next((k for k, v in body.items() if isinstance(v, list)), None)
	records = [r.get(ENTITY, r) for r in (body[list_key] if list_key else [])]
	matches = sorted((r for r in records if r.get("slug") == slug), key=lambda r: r.get("updated_at", ""), reverse=True)
	if len(matches) > 1:
		print(f"Note: {len(matches)} records have the slug {slug!r}; using the newest ({matches[0].get(ID_FIELD)}).")
	return (matches[0] if matches else None), None


def now():
	return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def show_diff(remote_source, local_source, source_path):
	diff = difflib.unified_diff(remote_source.splitlines(), local_source.splitlines(),
	                            fromfile="App Studio", tofile=str(source_path.name), lineterm="", n=2)
	print("\n".join(diff))


def main():
	parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
	parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="page source (default %(default)s)")
	parser.add_argument("--slug", default=DEFAULT_SLUG, help="URL segment under /pages/ (default %(default)s)")
	parser.add_argument("--title", default=DEFAULT_TITLE, help="page title, for a new page")
	parser.add_argument("--kind", choices=["page", "app"], default="page",
	                    help="page: HTML and CSS shown inline; app: a web app run in a sandboxed iframe (default %(default)s)")
	parser.add_argument("--yes", action="store_true", help="write to OBP; without it, only report")
	parser.add_argument("--overwrite", action="store_true", help="replace a page whose source differs from the file")
	parser.add_argument("--pull", action="store_true", help="save the App Studio source to --source and stop")
	status = parser.add_mutually_exclusive_group()
	status.add_argument("--publish", action="store_true", help="set status=published (shown on the Portal)")
	status.add_argument("--draft", action="store_true", help="set status=draft (hidden from the Portal)")
	args = parser.parse_args()

	print(f"OBP: {obp_host}   page: /pages/{args.slug}   source: {args.source.name}")
	page, error = find_page(args.slug)
	if error:
		return error

	if args.pull:
		if not page:
			print(f"No page with the slug {args.slug!r} on OBP: nothing to pull.")
			return 1
		args.source.write_text(page.get("source", ""))
		print(f"Saved the App Studio source (last edited by {page.get('author') or '?'} at {page.get('updated_at')}) to {args.source}.")
		return 0

	local_source = args.source.read_text()
	wanted_status = "published" if args.publish else "draft" if args.draft else None

	if not page:
		record = {"slug": args.slug, "title": args.title, "kind": args.kind, "status": wanted_status or "draft",
		          "source": local_source, "author": username, "updated_at": now()}
		if not args.yes:
			print(f"Missing: would create it as a {record['status']} {args.kind}. Run with --yes to create it.")
			return 0
		response = session.post(RECORDS_URL, headers=headers(), json=record)
		if response.status_code not in (200, 201):
			return refused(response, "Create")
		created = response.json().get(ENTITY, response.json())
		print(f"Created {created.get(ID_FIELD)} as a {record['status']} {args.kind}.")
		return 0

	page_id = page.get(ID_FIELD)
	print(f"Found {page_id}: {page.get('status')}, last edited by {page.get('author') or '?'} at {page.get('updated_at')}.")
	source_differs = page.get("source", "") != local_source
	status_differs = wanted_status is not None and page.get("status") != wanted_status

	if source_differs:
		print("Its source differs from the file (App Studio version first):")
		show_diff(page.get("source", ""), local_source, args.source)
	if not source_differs and not status_differs:
		print("Up to date.")
		return 0
	if source_differs and not args.overwrite:
		print("Not overwriting it. To keep the App Studio edits, run with --pull and commit the file; "
		      "to replace them with the file, run with --yes --overwrite.")
		if status_differs and args.yes:
			print("(The status was not changed either.)")
		return 0 if not args.yes else 1
	if not args.yes:
		changes = (["source"] if source_differs else []) + ([f"status to {wanted_status}"] if status_differs else [])
		print(f"Would update the {' and '.join(changes)}. Run with --yes to update it.")
		return 0

	# A PUT replaces the record: send every field, keeping App Studio's values for the ones we don't set.
	record = {f: page[f] for f in FIELDS if f in page}
	record.update({"source": local_source, "author": username, "updated_at": now()})
	if wanted_status:
		record["status"] = wanted_status
	response = session.put(f"{RECORDS_URL}/{page_id}", headers=headers(), json=record)
	if response.status_code != 200:
		return refused(response, "Update")
	print(f"Updated {page_id} ({record['status']}).")
	return 0


if __name__ == "__main__":
	sys.exit(main())
