"""dynamic_resource_docs.missing_entities: which entities a Query doc reads that the
space does not have, so the doc is skipped (and an existing one left in place) instead
of failing on create with OBP-40065.

Runs offline: obp_client, which logs in to OBP on import, is replaced by a stub.

    python3 -m unittest tests/test_dynamic_resource_docs_entities.py
"""

import json
import sys
import types
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))


class _Response:
	def __init__(self, payload, status=200):
		self._payload = payload
		self.status_code = status
		self.text = json.dumps(payload)
		self.url = "http://fake"

	def json(self):
		return self._payload


class _Session:
	def __init__(self):
		self.entity_names = []
		self.urls = []

	def get(self, url, headers=None, **_):
		self.urls.append(url)
		return _Response({"dynamic_entities": [{"entity_name": n} for n in self.entity_names]})


SESSION = _Session()
sys.modules["obp_client"] = types.SimpleNamespace(
	token="tok", obp_host="http://fake", session=SESSION, authorization=lambda t: f"DirectLogin token={t}")

import dynamic_resource_docs as drd  # noqa: E402  (after the stub)


class MissingEntities(unittest.TestCase):
	def doc(self):
		return drd.DOCS["registry_activity_query"]

	def test_reports_the_chain_entity_when_it_is_missing(self):
		declaration = json.loads((REPO / self.doc()["query_file"]).read_text())
		read = {declaration["from"]} | {j["entity"] for j in declaration["join"]}
		SESSION.entity_names = sorted(read - {"activity_on_chain"})
		self.assertEqual(drd.missing_entities(self.doc(), "tok", "http://fake"), ["activity_on_chain"])
		self.assertIn("/management/banks/", SESSION.urls[-1])

	def test_nothing_missing_when_every_entity_exists(self):
		declaration = json.loads((REPO / self.doc()["query_file"]).read_text())
		SESSION.entity_names = [declaration["from"]] + [j["entity"] for j in declaration["join"]]
		self.assertEqual(drd.missing_entities(self.doc(), "tok", "http://fake"), [])

	def test_scala_doc_is_not_checked(self):
		SESSION.entity_names = []
		self.assertEqual(drd.missing_entities(drd.DOCS["registry_activities"], "tok", "http://fake"), [])

	def test_message_says_where_a_chain_entity_comes_from(self):
		message = drd.missing_entities_message("registry_activity_query", ["activity_on_chain"])
		self.assertIn("activity_on_chain", message)
		self.assertIn("OGCR-chain-cache", message)


if __name__ == "__main__":
	unittest.main()
