"""Publish the architecture overview (architecture_glossary_item.md) as a Dynamic Glossary Item on OBP.

A Glossary Item's description is Markdown. OBP serves it, rendered, in the Glossary
(GET /obp/v7.0.0/api/glossary/TITLE, the API Explorer and the API Manager), and other
descriptions can embed it: another Glossary Item, or a Resource Doc description, with
<!--OBP-GLOSSARY:FULL:OGCR Architecture--> (collapsible), SIMPLE (the text only) or LINK.
OBP's renderer keeps headings, lists, tables, code blocks and <details>; it drops <style>,
class attributes and scripts.

Because someone may have edited the item in the API Manager since it was last published,
the script never replaces a description that differs from the file unless given
--overwrite. Use --pull to copy the stored description into the file instead, so the
edits are kept in this repo.

Reports only (missing / up to date / differs, with a diff), unless given --yes:

    python3 publish_architecture_glossary_item.py                     # report
    python3 publish_architecture_glossary_item.py --yes               # create it if missing
    python3 publish_architecture_glossary_item.py --yes --overwrite   # replace a differing description
    python3 publish_architecture_glossary_item.py --pull              # save the stored description to the file

Needs the Role CanCreateGlossaryItem to create and CanUpdateGlossaryItem to update
(both system level). Reading needs no Role unless OBP's apiOptions.glossaryDocsRequireRole is set.

Exit code 0 on success (or when there is nothing to do), 1 otherwise.
"""

import argparse
import difflib
import sys
import urllib.parse
from pathlib import Path

from obp_client import obp_host, session, token

HERE = Path(__file__).parent
GLOSSARY_URL = f"{obp_host}/obp/v7.0.0/api/glossary"

DEFAULT_SOURCE = HERE / "architecture_glossary_item.md"
DEFAULT_TITLE = "OGCR Architecture"


def headers():
	return {"Authorization": f"DirectLogin token={token}", "Content-Type": "application/json"}


def item_url(title):
	return f"{GLOSSARY_URL}/{urllib.parse.quote(title, safe='')}"


def refused(response, action, role=None):
	print(f"OBP refused to {action} the Glossary Item: {response.status_code} {response.text}")
	if role and response.status_code in (401, 403):
		print(f"The user needs the Role {role}.")
	return 1


def find_item(title):
	"""(item or None, error exit code or None). The item as authored, placeholders not expanded."""
	response = session.get(item_url(title), headers=headers(), params={"expanded": "false"})
	if response.status_code == 404:
		return None, None
	if response.status_code != 200:
		return None, refused(response, "read")
	return response.json(), None


def show_diff(stored, local, source_path):
	diff = difflib.unified_diff(stored.splitlines(), local.splitlines(),
	                            fromfile="OBP", tofile=source_path.name, lineterm="", n=2)
	print("\n".join(diff))


def main():
	parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
	parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="Markdown description (default %(default)s)")
	parser.add_argument("--title", default=DEFAULT_TITLE, help="Glossary Item title (default %(default)s)")
	parser.add_argument("--yes", action="store_true", help="write to OBP; without it, only report")
	parser.add_argument("--overwrite", action="store_true", help="replace a description that differs from the file")
	parser.add_argument("--pull", action="store_true", help="save the stored description to --source and stop")
	args = parser.parse_args()

	print(f"OBP: {obp_host}   Glossary Item: {args.title!r}   source: {args.source.name}")
	item, error = find_item(args.title)
	if error:
		return error

	if item and not item.get("is_dynamic"):
		print(f"{args.title!r} is a static Glossary Item shipped with OBP. Choose another --title.")
		return 1

	if args.pull:
		if not item:
			print("No such Glossary Item on OBP: nothing to pull.")
			return 1
		args.source.write_text(item["description"]["markdown"])
		print(f"Saved the stored description (updated at {item.get('updated_at')}) to {args.source}.")
		return 0

	local = args.source.read_text()

	if not item:
		if not args.yes:
			print("Missing: would create it. Run with --yes to create it.")
			return 0
		response = session.post(GLOSSARY_URL, headers=headers(), json={"title": args.title, "description": local})
		if response.status_code not in (200, 201):
			return refused(response, "create", "CanCreateGlossaryItem")
		print(f"Created {response.json().get('glossary_item_id')}. "
		      f"See it at {item_url(args.title)}, or embed it with <!--OBP-GLOSSARY:FULL:{args.title}-->.")
		return 0

	stored = item["description"]["markdown"]
	print(f"Found {item.get('glossary_item_id')}, last updated at {item.get('updated_at')}.")
	if stored == local:
		print("Up to date.")
		return 0
	print("Its description differs from the file (OBP version first):")
	show_diff(stored, local, args.source)
	if not args.overwrite:
		print("Not overwriting it. To keep the edits made on OBP, run with --pull and commit the file; "
		      "to replace them with the file, run with --yes --overwrite.")
		return 1 if args.yes else 0
	if not args.yes:
		print("Would update the description. Run with --yes --overwrite to update it.")
		return 0
	response = session.put(item_url(args.title), headers=headers(), json={"description": local})
	if response.status_code != 200:
		return refused(response, "update", "CanUpdateGlossaryItem")
	print("Updated the description.")
	return 0


if __name__ == "__main__":
	sys.exit(main())
