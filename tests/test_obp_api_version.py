"""Every OBP-API path the scripts and their documents name uses version v5.1.0 or newer.

A deployment can switch the older versions off. The scripts then keep working, and no reader is sent to a
URL that no longer answers. The test reads the Python and shell scripts and the documents, and fails on any
`obp/vX.Y.Z` below v5.1.0.

    python3 -m unittest tests/test_obp_api_version.py
"""

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VERSION = re.compile(r"obp/v(\d+)\.(\d+)\.(\d+)(?![\w.])")
EXTENSIONS = {".py", ".sh", ".md", ".txt", ".yml", ".yaml"}
NAMES = {"env_example"}
SKIPPED = {".git", "__pycache__", "logs", "node_modules", ".venv"}


def versions_below_510(line):
	"""The versions below v5.1.0 that a line names in an OBP-API path, as vX.Y.Z."""
	return [
		"v%s.%s.%s" % m.groups()
		for m in VERSION.finditer(line)
		if tuple(int(g) for g in m.groups()) < (5, 1, 0)
	]


def files():
	found = []
	for path in sorted(REPO.rglob("*")):
		relative = path.relative_to(REPO)
		if not path.is_file() or SKIPPED & set(relative.parts):
			continue
		if path.suffix not in EXTENSIONS and path.name not in NAMES:
			continue
		# This file spells old versions out on purpose, to test the check.
		if relative.as_posix() == "tests/test_obp_api_version.py":
			continue
		found.append(path)
	return found


class ObpApiVersionTest(unittest.TestCase):
	def test_the_files_are_found(self):
		# So an empty result below means "no old version", not "no files".
		self.assertGreater(len(files()), 20)

	def test_every_obp_api_path_uses_v510_or_newer(self):
		old = []
		for path in files():
			text = path.read_text(encoding="utf-8", errors="replace")
			for number, line in enumerate(text.splitlines(), 1):
				for version in versions_below_510(line):
					old.append("%s:%d %s" % (path.relative_to(REPO), number, version))
		self.assertEqual([], old)

	def test_the_check_sees_a_version_below_v510_however_the_path_is_written(self):
		self.assertEqual(["v2.2.0"], versions_below_510("GET /obp/v2.2.0/message-docs/x"))
		self.assertEqual(["v5.0.0"], versions_below_510("url = f\"{host}/obp/v5.0.0/banks\""))
		self.assertEqual(["v4.0.0", "v1.2.1"], versions_below_510("a /obp/v4.0.0/x and /obp/v1.2.1/y"))

	def test_the_check_leaves_v510_and_newer_alone(self):
		self.assertEqual([], versions_below_510("/obp/v5.1.0/root"))
		self.assertEqual([], versions_below_510("/obp/v6.0.0/users"))
		self.assertEqual([], versions_below_510("/obp/v10.0.0/x"))
		self.assertEqual([], versions_below_510("/obp/dynamic-entity/banks/ogcr/x"))
		self.assertEqual([], versions_below_510("version 4.0.0 of the sheet"))


if __name__ == "__main__":
	unittest.main()
