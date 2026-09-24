#!/usr/bin/env python3
"""
dynamic_resource_docs.py — manage OGCR Dynamic Resource Docs on OBP.

A Dynamic Resource Doc is Scala compiled at runtime inside OBP and served under
/obp/dynamic-endpoint/<request_url>. The API stores the code URL-encoded inside a
JSON column, which is unreviewable in that form, so this repo keeps the real Scala
in a .scala file and encodes it only at push time. Edit the .scala, not the stored
value.

Usage:
  python3 dynamic_resource_docs.py compile registry_activities     # dry run, nothing stored
  python3 dynamic_resource_docs.py list
  python3 dynamic_resource_docs.py create registry_activities
  python3 dynamic_resource_docs.py update registry_activities
  python3 dynamic_resource_docs.py delete registry_activities
  python3 dynamic_resource_docs.py verify registry_activities     # anonymous call, checks it is public

`compile` is a true dry run: it returns compiler diagnostics with line numbers
relative to the method body you wrote, and stores nothing. Always run it first.

Prerequisites on the target OBP instance:
  * allow_user_generated_scala_code=true — the master kill switch. Without it,
    creating or running any user-supplied Scala fails.
  * The caller needs the CanCreateDynamicResourceDoc role (and CanUpdate.../CanDelete...).
  * If dynamic_code_compile_validate_enable=true, every OBP method the body calls
    must appear in dynamic_code_compile_validate_dependencies, or creation is
    rejected with a 400 naming the offending method. The registry body calls
    code.DynamicData.DynamicDataProvider, which is NOT in the shipped default list.
  * If dynamic_code_requires_approval=true, a create/update is queued as a
    DynamicChangeRequest (202) and a different user must approve it before it runs.

Auth is DirectLogin via obp_client.py, the same as the other scripts here.
"""
import argparse
import json
import sys
from pathlib import Path
from urllib.parse import quote

import requests

from obp_client import token as DEFAULT_TOKEN, obp_host as DEFAULT_HOST

HERE = Path(__file__).parent

# Each doc: the readable Scala, plus the resource-doc metadata OBP stores alongside it.
# `request_url` is relative to /obp/dynamic-endpoint.
#
# `roles` is deliberately absent: OBP adds a Role guard to an endpoint only when the
# create body names one, so omitting it leaves the endpoint callable anonymously.
# That is the point for the registry — it is a public surface. The body is what keeps
# it safe: it projects only the registry columns rather than exposing whole entities.
DOCS = {
    "registry_activities": {
        "scala_file": "registry_activities_endpoint.scala",
        "request_verb": "GET",
        "request_url": "/registry/activities",
        # Identifies the generated partial function inside OBP; required on create.
        "partial_function_name": "getRegistryActivities",
        # Comma-separated, as OBP stores it. No auth/role errors are listed: the doc is
        # created without `roles`, so the endpoint is callable anonymously.
        "error_response_bodies": "OBP-50000: Unknown Error.",
        # `roles` is a REQUIRED string on this endpoint, so it cannot simply be omitted.
        # Empty means "no Role guard", which is what makes the registry endpoint public.
        "roles": "",
        "summary": "Get OGCR registry activities",
        "description": (
            "Public registry listing: one row per certified activity, joined to its "
            "operator, country, certificate of compliance and verification status. "
            "Reads system-level dynamic entities. Authentication is not required."
        ),
        "tags": "OGCR-Registry",
        "example_request_body": {},
        "success_response_body": {
            "activities": [
                {
                    "activity_id": "string",
                    "name": "string",
                    "summary": "string",
                    "activity_type": "string",
                    "country_id": "string",
                    "country_name": "string",
                    "city": "string",
                    "start_date": "string",
                    "end_date": "string",
                    "monitoring_period_start_date": "string",
                    "monitoring_period_end_date": "string",
                    "operator_id": "string",
                    "operator_legal_name": "string",
                    "verification_status": "string",
                    "certificate_of_compliance_id": "string",
                    "certification_status": "string",
                    "certificate_issue_date": "string",
                    "certificate_expiry_date": "string",
                }
            ],
            "count": 1,
        },
    }
}


# Resource-doc endpoints are served under an extra path segment that the Dynamic
# Endpoint glossary entry does not mention: the docs describe
# /obp/dynamic-endpoint + <request_url>, but a Dynamic *Resource Doc* actually lands at
# /obp/dynamic-endpoint/dynamic-resource-doc + <request_url>. Confirm the real path for
# any doc with:
#   GET /obp/v6.0.0/resource-docs/v6.0.0/obp?content=dynamic  -> specified_url
SERVED_PREFIX = "/obp/dynamic-endpoint/dynamic-resource-doc"


def served_url(host, doc):
    return f"{host}{SERVED_PREFIX}{doc['request_url']}"


def _headers(token):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"DirectLogin token={token}"
    return headers


def _raise_with_body(resp):
    """requests' own message drops the response body, which is where OBP puts the reason."""
    if resp.status_code >= 400:
        raise SystemExit(f"HTTP {resp.status_code} from {resp.url}\n{resp.text}")


def read_method_body(doc):
    """Return the Scala body, with the leading block comment stripped.

    The .scala file opens with a /* ... */ header explaining the endpoint. That is for
    readers of this repo; sending it would only pad the stored code, and the wrapper
    counts lines when reporting compiler positions.
    """
    text = (HERE / doc["scala_file"]).read_text()
    if text.lstrip().startswith("/*"):
        text = text.split("*/", 1)[1]
    return text.strip("\n")


def build_payload(doc, include_body=True):
    payload = {
        "request_verb": doc["request_verb"],
        "request_url": doc["request_url"],
        "partial_function_name": doc["partial_function_name"],
        "error_response_bodies": doc["error_response_bodies"],
        "roles": doc["roles"],
        "summary": doc["summary"],
        "description": doc["description"],
        "tags": doc["tags"],
        "success_response_body": doc["success_response_body"],
    }
    # OBP rejects a non-blank example_request_body on GET/DELETE — those verbs carry no
    # payload. The compile endpoint is laxer than create here, so a body that dry-runs
    # clean can still be refused on create.
    if doc["request_verb"] not in ("GET", "DELETE"):
        payload["example_request_body"] = doc["example_request_body"]
    if include_body:
        # OBP expects method_body URL-encoded.
        payload["method_body"] = quote(read_method_body(doc))
    return payload


def find_existing(doc, token, host):
    """Return the stored doc whose request_verb + request_url match, or None."""
    url = f"{host}/obp/v4.0.0/management/dynamic-resource-docs"
    resp = requests.get(url, headers=_headers(token))
    _raise_with_body(resp)
    for existing in resp.json().get("dynamic-resource-docs", []):
        if (
            existing.get("request_url") == doc["request_url"]
            and existing.get("request_verb") == doc["request_verb"]
        ):
            return existing
    return None


def cmd_compile(name, doc, token, host):
    """Dry run. Returns compiler problems; stores nothing."""
    url = f"{host}/obp/v7.0.0/management/dynamic-resource-docs/compile"
    resp = requests.post(url, headers=_headers(token), json=build_payload(doc))
    _raise_with_body(resp)
    result = resp.json()
    # Response shape: {"compiles": bool, "errors": [...], "duration_ms": int}.
    # Error positions are relative to the method body, not the generated wrapper.
    errors = result.get("errors") or []
    if result.get("compiles") and not errors:
        print(f"{name}: compiles cleanly ({result.get('duration_ms', '?')} ms)")
        return 0
    print(f"{name}: compiler reported problems")
    print(json.dumps(result, indent=2))
    return 1


def cmd_verify(name, doc, token, host):
    """Call the endpoint with no credentials — the registry surface must be public."""
    url = served_url(host, doc)
    resp = requests.get(url, timeout=60)
    print(f"{name}: anonymous GET {url} -> HTTP {resp.status_code}")
    if resp.status_code != 200:
        print(resp.text[:500])
        return 1
    body = resp.json()
    print(f"  count={body.get('count')}")
    return 0


def cmd_list(_name, _doc, token, host):
    url = f"{host}/obp/v4.0.0/management/dynamic-resource-docs"
    resp = requests.get(url, headers=_headers(token))
    _raise_with_body(resp)
    docs = resp.json().get("dynamic-resource-docs", [])
    print(f"{len(docs)} dynamic resource doc(s) on {host}")
    for d in docs:
        print(
            f"  {d.get('request_verb','?'):6} {d.get('request_url','?'):40} "
            f"{d.get('dynamic_resource_doc_id','')}"
        )
    return 0


def cmd_create(name, doc, token, host):
    if find_existing(doc, token, host):
        raise SystemExit(
            f"{name}: a doc already exists for {doc['request_verb']} {doc['request_url']}. "
            "Use `update`."
        )
    url = f"{host}/obp/v4.0.0/management/dynamic-resource-docs"
    resp = requests.post(url, headers=_headers(token), json=build_payload(doc))
    _raise_with_body(resp)
    created = resp.json()
    print(f"{name}: created {created.get('dynamic_resource_doc_id')}")
    print(f"  served at {served_url(host, doc)}")
    return 0


def cmd_update(name, doc, token, host):
    existing = find_existing(doc, token, host)
    if not existing:
        raise SystemExit(f"{name}: nothing to update — no doc for {doc['request_url']}. Use `create`.")
    doc_id = existing["dynamic_resource_doc_id"]
    url = f"{host}/obp/v4.0.0/management/dynamic-resource-docs/{doc_id}"
    resp = requests.put(url, headers=_headers(token), json=build_payload(doc))
    _raise_with_body(resp)
    print(f"{name}: updated {doc_id}")
    return 0


def cmd_delete(name, doc, token, host):
    existing = find_existing(doc, token, host)
    if not existing:
        print(f"{name}: nothing to delete")
        return 0
    doc_id = existing["dynamic_resource_doc_id"]
    url = f"{host}/obp/v4.0.0/management/dynamic-resource-docs/{doc_id}"
    resp = requests.delete(url, headers=_headers(token))
    _raise_with_body(resp)
    print(f"{name}: deleted {doc_id}")
    return 0


COMMANDS = {
    "compile": cmd_compile,
    "verify": cmd_verify,
    "list": cmd_list,
    "create": cmd_create,
    "update": cmd_update,
    "delete": cmd_delete,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=sorted(COMMANDS))
    parser.add_argument("doc", nargs="?", default="registry_activities", choices=sorted(DOCS) + [None])
    parser.add_argument("--token", default=None, help="DirectLogin token (overrides obp_client)")
    parser.add_argument("--host", default=None, help="OBP base URL (overrides OBP_HOSTNAME)")
    args = parser.parse_args()

    token = args.token or DEFAULT_TOKEN
    host = (args.host or DEFAULT_HOST).rstrip("/")
    if not token:
        raise SystemExit("No DirectLogin token. Check OBP_USERNAME / OBP_PASSWORD / OBP_CONSUMER_KEY in .env")

    return COMMANDS[args.command](args.doc, DOCS[args.doc], token, host)


if __name__ == "__main__":
    sys.exit(main())
