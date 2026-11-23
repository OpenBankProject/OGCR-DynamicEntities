"""The contract between the scripts and OBP-API, checked without a server.

obp-api-contract/contract.json lists every OBP-API call the scripts make, with the response fields they read.
obp-api-contract/snapshot.json is what an OBP-API documents for those calls. snapshot.py writes it.

    python3 -m unittest tests/test_obp_api_contract.py
"""

import ast
import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONTRACT_DIR = REPO / "obp-api-contract"
# A line of code that sends a request, or names an OBP-API path.
HTTP_CALL = re.compile(r"\b(session|requests)\.(get|post|put|delete|patch)\(")
OBP_PATH = re.compile(r"/obp/|/my/logins/direct")
SKIPPED = {".git", "__pycache__", "logs", "tests", "node_modules", ".venv"}


def load(name):
	return json.loads((CONTRACT_DIR / name).read_text(encoding="utf-8"))


def calls():
	return load("contract.json")["calls"]


def key(entry):
	return f"{entry['verb']} {entry['path']}"


def snapshot_of(call):
	return next((e for e in load("snapshot.json")["endpoints"] if key(e) == key(call)), None)


def docstring_lines(text):
	"""Line numbers of the module, class and function docstrings of Python source."""
	lines = set()
	try:
		tree = ast.parse(text)
	except SyntaxError:
		return lines
	for node in ast.walk(tree):
		if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
			body = node.body
			if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
					and isinstance(body[0].value.value, str):
				lines.update(range(body[0].lineno, body[0].end_lineno + 1))
	return lines


def is_documented(read, documented):
	"""A read written a|b is documented when either name is."""
	return any(name in documented for name in read.split("|"))


def request_lines_in(text, python=True):
	"""Lines of source that send a request or name an OBP-API path, skipping comments and docstrings:
	(line number, line)."""
	skip = docstring_lines(text) if python else set()
	found = []
	for number, line in enumerate(text.splitlines(), 1):
		code = line.strip()
		if number in skip or code.startswith("#"):
			continue
		if HTTP_CALL.search(code) or OBP_PATH.search(code):
			found.append((number, line))
	return found


def request_lines():
	"""Lines of the scripts that send a request or name an OBP-API path: (file, line number, line)."""
	found = []
	for path in sorted(REPO.glob("*")):
		if path.suffix not in (".py", ".sh") or not path.is_file():
			continue
		text = path.read_text(encoding="utf-8")
		for number, line in request_lines_in(text, python=path.suffix == ".py"):
			found.append((path.name, number, line))
	return found


class ObpApiContractTest(unittest.TestCase):
	def test_every_call_in_the_contract_is_in_its_source_file(self):
		gone = []
		for call in calls():
			text = (REPO / call["source"]).read_text(encoding="utf-8")
			gone += [f"{key(call)}: {needle}" for needle in call["needles"] if needle not in text]
		self.assertEqual([], gone)

	def test_every_request_in_the_scripts_is_a_listed_call_or_a_listed_non_call(self):
		# So a new call cannot reach OBP-API without its fields being recorded.
		contract = load("contract.json")
		listed = [(c["source"], n) for c in contract["calls"] for n in c["needles"]]
		listed += [(c["source"], c["fragment"]) for c in contract.get("path_builders", [])]
		listed += [(c["source"], c["fragment"]) for c in contract.get("not_calls", [])]
		unlisted = [
			f"{name}:{number} {line.strip()}"
			for name, number, line in request_lines()
			if not any(source == name and needle in line for source, needle in listed)
		]
		self.assertEqual([], unlisted)

	def test_every_listed_path_builder_and_non_call_is_still_in_its_file(self):
		contract = load("contract.json")
		gone = []
		for entry in contract.get("path_builders", []) + contract.get("not_calls", []):
			if entry["fragment"] not in (REPO / entry["source"]).read_text(encoding="utf-8"):
				gone.append(f"{entry['source']}: {entry['fragment']}")
		self.assertEqual([], gone)

	def test_the_snapshot_was_taken_for_this_contract(self):
		# snapshot.json must hold exactly the calls of contract.json; otherwise run snapshot.py again.
		self.assertEqual({key(c) for c in calls()}, {key(e) for e in load("snapshot.json")["endpoints"]})

	def test_every_call_reaches_an_endpoint_obp_api_documents_unless_the_contract_says_it_does_not(self):
		undocumented = []
		for call in calls():
			entry = snapshot_of(call)
			missing = entry is None or entry.get("missing")
			if missing and not call.get("undocumented_endpoint"):
				undocumented.append(key(call))
		self.assertEqual([], undocumented)

	def test_a_call_is_left_out_of_undocumented_endpoint_once_obp_api_documents_it(self):
		documented_now = []
		for call in calls():
			entry = snapshot_of(call)
			if call.get("undocumented_endpoint") and entry is not None and not entry.get("missing"):
				documented_now.append(f"{key(call)} is documented now; remove undocumented_endpoint")
		self.assertEqual([], documented_now)

	def test_every_field_the_scripts_read_is_documented_unless_the_contract_says_it_is_not(self):
		problems = []
		for call in calls():
			entry = snapshot_of(call)
			if entry is None or entry.get("missing"):
				continue
			documented = set(entry.get("fields", []))
			accepted = call.get("undocumented_fields", [])
			for read in call["reads"]:
				if not is_documented(read, documented) and read not in accepted:
					problems.append(f"{key(call)}: {read} is not documented")
		self.assertEqual([], problems)

	def test_a_field_is_left_out_of_undocumented_fields_once_obp_api_documents_it(self):
		documented_now = []
		for call in calls():
			entry = snapshot_of(call)
			if entry is None or entry.get("missing"):
				continue
			documented = set(entry.get("fields", []))
			for field in call.get("undocumented_fields", []):
				if is_documented(field, documented):
					documented_now.append(f"{key(call)}: {field} is documented now; remove it from undocumented_fields")
		self.assertEqual([], documented_now)

	def test_every_call_names_a_source_that_exists_and_a_verb_and_a_path(self):
		for call in calls():
			self.assertTrue((REPO / call["source"]).is_file(), call["source"])
			self.assertIn(call["verb"], ("GET", "POST", "PUT", "PATCH", "DELETE"), key(call))
			self.assertTrue(call["path"].startswith("/"), key(call))


class ScanTest(unittest.TestCase):
	def test_the_scan_finds_a_request_and_a_path_and_skips_comments_and_docstrings(self):
		text = (
			'"""Calls GET /obp/v6.0.0/users in the docstring."""\n'
			"# GET /obp/v6.0.0/banks in a comment\n"
			"def f():\n"
			'\t"""Docstring with session.get(x)."""\n'
			'\tresponse = session.get(f"{host}/obp/v6.0.0/users")\n'
			"\tpath = '/obp/dynamic-entity'\n"
			"\tx = 1\n"
		)
		self.assertEqual([5, 6], [number for number, _ in request_lines_in(text)])

	def test_a_read_with_alternatives_needs_only_one_of_them_documented(self):
		self.assertTrue(is_documented("first_name|firstname", {"first_name"}))
		self.assertFalse(is_documented("last_name|lastname", {"first_name"}))

	def test_a_renamed_or_removed_field_is_reported(self):
		documented = {"user_id", "username"}
		self.assertEqual(["usernme"], [r for r in ("user_id", "usernme") if not is_documented(r, documented)])


if __name__ == "__main__":
	unittest.main()
