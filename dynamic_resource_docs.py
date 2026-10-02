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
  python3 dynamic_resource_docs.py verify registry_activities --wait 90   # retry a 404 while OBP's cache catches up
  python3 dynamic_resource_docs.py create registry_activities_query   # the registry as a Dynamic Query, at the space's bank

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
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote


from obp_client import token as DEFAULT_TOKEN, obp_host as DEFAULT_HOST, session
from obp_space import SPACE_ID

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
            "Reads the dynamic entities of the ogcr space. Authentication is not required."
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
    },
}

# The same registry as a Dynamic Query (programming_lang "Query", see OBP's "Dynamic Query"
# glossary entry): a JSON declaration instead of Scala, which OBP runs without compiling
# anything. A Query reads the entities of the space its doc belongs to, so this doc is
# created at the bank of the space (OBP_ENTITY_SPACE_ID). It needs an OBP that has the
# "Dynamic Query" commit (fd8f70691); older ones refuse programming_lang Query (OBP-40049).
#
# This script does not decide who may call it. OBP does, per caller, from the access
# settings of the entities the Query reads: a caller who can't read one of them gets a
# 403, and a field hidden from that caller comes back null. So whether the registry is
# public, and which of its columns are, is set on the entity definitions. `verify` calls
# it anonymously, as the app's public registry pages do. Its own URL keeps it from
# clashing with the Scala doc at /registry/activities.
DOCS["registry_activities_query"] = {
    "query_file": "registry_activities_query.json",
    "programming_lang": "Query",
    "bank_id": SPACE_ID or None,
    "request_verb": "GET",
    "request_url": "/registry/activities-query",
    "partial_function_name": "getRegistryActivitiesQuery",
    "error_response_bodies": "OBP-50000: Unknown Error.",
    "roles": "",
    "summary": DOCS["registry_activities"]["summary"],
    "description": "",
    "tags": DOCS["registry_activities"]["tags"],
    "example_request_body": {},
    # The Scala doc's rows, plus the fields only the Query returns.
    "success_response_body": {
        "activities": [
            {
                **DOCS["registry_activities"]["success_response_body"]["activities"][0],
                "internal_note": "string",
                "minted_at": 1779280448,
                "token_uri": "string",
            }
        ],
        "count": 1,
    },
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
    """Return the method body: a Query's JSON declaration, or the Scala.

    A Query's .json is parsed here, so a syntax error is reported before anything is
    sent, and sent compact. The .scala file opens with a /* ... */ header explaining the endpoint. That is for
    readers of this repo; sending it would only pad the stored code, and the wrapper
    counts lines when reporting compiler positions.
    """
    if "query_file" in doc:
        try:
            return json.dumps(json.loads((HERE / doc["query_file"]).read_text()), separators=(",", ":"))
        except ValueError as e:
            raise SystemExit(f"{doc['query_file']}: not valid JSON: {e}")
    text = (HERE / doc["scala_file"]).read_text()
    if text.lstrip().startswith("/*"):
        text = text.split("*/", 1)[1]
    check_space(doc, text)
    return text.strip("\n")


SPACE_BANK_ID_RE = re.compile(r'val SPACE_BANK_ID: Option\[String\] = (None|Some\("([^"]*)"\))')


def check_space(doc, text):
    """The Scala reads its entities from SPACE_BANK_ID, which must be the space the other scripts
    create them in (OBP_ENTITY_SPACE_ID, see obp_space.py), or the endpoint would read another space."""
    match = SPACE_BANK_ID_RE.search(text)
    if not match:
        raise SystemExit(f"{doc['scala_file']}: no `val SPACE_BANK_ID: Option[String] = ...` line found")
    in_scala = match.group(2) or ""
    if in_scala != SPACE_ID:
        raise SystemExit(
            f"{doc['scala_file']} reads bank id {in_scala or '(system level)'!r}, but OBP_ENTITY_SPACE_ID is "
            f"{SPACE_ID or '(system level)'!r}. Change SPACE_BANK_ID in the .scala to match.")


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
    if "programming_lang" in doc:
        payload["programming_lang"] = doc["programming_lang"]
    # OBP rejects a non-blank example_request_body on GET/DELETE — those verbs carry no
    # payload. The compile endpoint is laxer than create here, so a body that dry-runs
    # clean can still be refused on create.
    if doc["request_verb"] not in ("GET", "DELETE"):
        payload["example_request_body"] = doc["example_request_body"]
    if include_body:
        # OBP expects method_body URL-encoded.
        payload["method_body"] = quote(read_method_body(doc))
    return payload


def management_url(host, doc):
    """The doc's management endpoint: at its bank when it has one, else system level."""
    if doc.get("bank_id"):
        return f"{host}/obp/v4.0.0/management/banks/{doc['bank_id']}/dynamic-resource-docs"
    return f"{host}/obp/v4.0.0/management/dynamic-resource-docs"


def find_existing(doc, token, host):
    """Return the stored doc whose request_verb + request_url match, or None."""
    url = management_url(host, doc)
    resp = session.get(url, headers=_headers(token))
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
    if doc.get("programming_lang") == "Query" and doc.get("bank_id"):
        # OBP's compile endpoint checks a Query against the system-level entities, not the
        # doc's bank, so it would judge this one against the wrong entities. Only the JSON
        # is checked here; OBP checks the declaration against the bank's entities on create.
        read_method_body(doc)
        print(f"{name}: {doc['query_file']} is valid JSON; OBP checks it against bank "
              f"{doc['bank_id']}'s entities when it is created")
        return 0
    url = f"{host}/obp/v7.0.0/management/dynamic-resource-docs/compile"
    resp = session.post(url, headers=_headers(token), json=build_payload(doc))
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


def cmd_verify(name, doc, token, host, wait=0):
    """Call the endpoint with no credentials — the registry surface must be public.

    OBP caches its list of resource docs (dynamicResourceDoc.cache.ttl.seconds,
    40 by default), so a doc just created 404s until that cache expires. `wait`
    keeps retrying a 404 for up to that many seconds."""
    url = served_url(host, doc)
    # A doc that isn't public is called as the logged in user instead.
    public = doc.get("public", True)
    headers = {} if public else _headers(token)
    who = "anonymous" if public else "logged in"
    deadline = time.monotonic() + wait
    resp = session.get(url, headers=headers, timeout=60)
    if resp.status_code == 404 and wait:
        print(f"{name}: 404 at first; OBP caches resource docs, retrying for up to {wait}s ...")
    while resp.status_code == 404 and time.monotonic() < deadline:
        time.sleep(5)
        resp = session.get(url, headers=headers, timeout=60)
    print(f"{name}: {who} GET {url} -> HTTP {resp.status_code}")
    if resp.status_code != 200:
        print(resp.text[:500])
        return 1
    body = resp.json()
    print(f"  count={body.get('count')}")
    return 0


def cmd_list(_name, _doc, token, host):
    """The docs at system level, and at each bank a doc in DOCS lives at."""
    banks = [None] + sorted({d["bank_id"] for d in DOCS.values() if d.get("bank_id")})
    for bank in banks:
        resp = session.get(management_url(host, {"bank_id": bank}), headers=_headers(token))
        _raise_with_body(resp)
        docs = resp.json().get("dynamic-resource-docs", [])
        print(f"{len(docs)} dynamic resource doc(s) on {host} at {f'bank {bank}' if bank else 'system level'}")
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
    resp = session.post(management_url(host, doc), headers=_headers(token), json=build_payload(doc))
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
    url = f"{management_url(host, doc)}/{doc_id}"
    resp = session.put(url, headers=_headers(token), json=build_payload(doc))
    _raise_with_body(resp)
    print(f"{name}: updated {doc_id}")
    return 0


def cmd_delete(name, doc, token, host):
    existing = find_existing(doc, token, host)
    if not existing:
        print(f"{name}: nothing to delete")
        return 0
    doc_id = existing["dynamic_resource_doc_id"]
    url = f"{management_url(host, doc)}/{doc_id}"
    resp = session.delete(url, headers=_headers(token))
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
    parser.add_argument("--wait", type=int, default=0, metavar="SECONDS",
                        help="verify: keep retrying a 404 for up to SECONDS (OBP caches resource docs, 40s by default)")
    args = parser.parse_args()

    token = args.token or DEFAULT_TOKEN
    host = (args.host or DEFAULT_HOST).rstrip("/")
    if not token:
        raise SystemExit("No DirectLogin token. Check OBP_USERNAME / OBP_PASSWORD / OBP_CONSUMER_KEY in .env")

    if args.command == "verify":
        return cmd_verify(args.doc, DOCS[args.doc], token, host, wait=args.wait)
    return COMMANDS[args.command](args.doc, DOCS[args.doc], token, host)


if __name__ == "__main__":
    sys.exit(main())
