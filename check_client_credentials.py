"""Check which of the endpoints these scripts use accept an application token (OAuth2 client
credentials, the way a Platform App calls OBP) instead of a DirectLogin user.

Gets a token from the OIDC issuer with the client credentials grant, then calls one read (GET)
from each group of endpoints the scripts use, and prints the status OBP answers next to what
reading OBP-API's code predicts. Read-only: nothing is created, changed or deleted.

A client credentials token is not user-less in OBP: OBP creates a User from the token's sub (the
client id), so endpoints that only need "a user" let it through, and Role checks look at that
User's Entitlements unless the endpoint's authMode is UserOrApplication, in which case the
Consumer's Scopes count. 200 means the endpoint accepted the app; 403 usually means it looked
for Entitlements (or a Scope the Consumer doesn't hold yet); 401 means it wanted a real user.

Needs, in the environment or .env:
    OIDC_ISSUER          e.g. http://localhost:9000/obp-oidc
    OIDC_CLIENT_ID
    OIDC_CLIENT_SECRET
    OBP_HOSTNAME         the OBP to check (as for the other scripts)
    OBP_ENTITY_SPACE_ID  optional, default ogcr

Usage:
    python3 check_client_credentials.py [--entity activity]
"""

import argparse
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()


def env(name, default=None):
	value = os.getenv(name, default)
	if value is None:
		sys.exit(f"{name} is not set (environment or .env).")
	return value


def client_credentials_token(issuer, client_id, client_secret):
	discovery = requests.get(f"{issuer.rstrip('/')}/.well-known/openid-configuration", timeout=10)
	discovery.raise_for_status()
	token_endpoint = discovery.json()["token_endpoint"]
	response = requests.post(token_endpoint, timeout=10,
	                         data={"grant_type": "client_credentials"}, auth=(client_id, client_secret))
	if response.status_code != 200:
		sys.exit(f"The token request was refused: {response.status_code} {response.text}")
	return response.json()["access_token"]


def main():
	parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
	parser.add_argument("--entity", default="activity", help="a registry entity to read records of (default %(default)s)")
	args = parser.parse_args()

	host = env("OBP_HOSTNAME").rstrip("/")
	space = os.getenv("OBP_ENTITY_SPACE_ID", "ogcr").strip()
	bank = space or "SYS"
	token = client_credentials_token(env("OIDC_ISSUER"), env("OIDC_CLIENT_ID"), env("OIDC_CLIENT_SECRET"))
	headers = {"Authorization": f"Bearer {token}"}
	print(f"OBP: {host}   space: {bank}   entity: {args.entity}\n")

	# Who OBP thinks is calling.
	scopes = requests.get(f"{host}/obp/v7.0.0/consumers/current/scopes", headers=headers, timeout=20)
	me = requests.get(f"{host}/obp/v6.0.0/users/current", headers=headers, timeout=20)
	print(f"Consumer Scopes: {scopes.status_code} "
	      f"{[s.get('role_name') for s in scopes.json().get('scopes', [])] if scopes.ok else scopes.text[:150]}")
	print(f"/users/current:  {me.status_code} {me.json().get('username') if me.ok else me.text[:150]}\n")

	definitions = f"management/banks/{space}/dynamic-entities" if space else "management/system-dynamic-entities"
	records = f"/obp/dynamic-entity/banks/{space}/{args.entity}" if space else f"/obp/dynamic-entity/{args.entity}"
	checks = [
		# (what, path, what the code predicts)
		("Glossary Item (public)", "/obp/v7.0.0/api/glossary/OGCR-Architecture", "200"),
		("Bank (public)", f"/obp/v6.0.0/banks/{space or 'SYS'}", "200 (404 at system level)"),
		("Entity definitions v7.0.0", f"/obp/v7.0.0/{definitions}", "200 with the Scope CanGetDynamicEntityDefinitions"),
		("Entity definitions v6.0.0", f"/obp/v6.0.0/{definitions}", "403: UserOnly"),
		("Entity records (unversioned)", records, f"403 unless {args.entity} has auth_mode UserOrApplication and the Scope"),
		("Entity records v7.0.0", f"/obp/v7.0.0/banks/{bank}/dynamic-entities/{args.entity}", "same as above"),
		("Users", "/obp/v6.0.0/users?limit=1", "403: UserOnly"),
		("Groups", "/obp/v6.0.0/management/groups", "403: checked against Entitlements"),
		("Dynamic Resource Docs", "/obp/v4.0.0/management/dynamic-resource-docs", "403: UserOnly"),
	]
	width = max(len(c[0]) for c in checks)
	for what, path, predicted in checks:
		response = requests.get(f"{host}{path}", headers=headers, timeout=30)
		detail = "" if response.ok else "  " + response.text.replace("\n", " ")[:120]
		print(f"{what:<{width}}  {response.status_code}   predicted {predicted}{detail}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
