"""Check that DirectLogin works, and nothing else.

Read-only: it logs in with the credentials from `.env` / the environment
(OBP_HOSTNAME, OBP_USERNAME, OBP_PASSWORD, OBP_CONSUMER_KEY) and fetches the
current user. It doesn't check Roles or the space's bank: for those, run
check_login_and_roles.py.

Usage:
    python3 check_login.py

Exits 0 if the login worked, 1 if it didn't.
"""

import argparse
import os
import sys

import obp_target  # loads .env and picks LOCAL or PROD settings

from check_login_and_roles import direct_login, get_current_user, logger, mask_credential


def main():
	argparse.ArgumentParser(description="Check that DirectLogin works.").parse_args()

	if os.getenv('OBP_AUTH_MODE', 'user').strip().lower() != 'user':
		logger.error("✗ This checks DirectLogin, so it needs OBP_AUTH_MODE=user. "
		             "As a Platform App, run ./check_client_credentials.sh instead.")
		return 1
	host = os.getenv('OBP_HOSTNAME', "http://obp-api-internal-route-obp.apps-crc.testing")
	missing_env = [k for k in ('OBP_USERNAME', 'OBP_PASSWORD', 'OBP_CONSUMER_KEY') if not os.getenv(k)]
	if missing_env:
		logger.error(f"✗ Not set in environment or .env: {', '.join(missing_env)}")
		return 1
	username = os.environ['OBP_USERNAME']

	logger.info(f"OBP_HOSTNAME: {host}")
	logger.info(f"OBP_USERNAME: {mask_credential(username)}")

	token = direct_login(host, username, os.environ['OBP_PASSWORD'], os.environ['OBP_CONSUMER_KEY'])
	if not token:
		return 1
	logger.info("✓ DirectLogin OK")

	user = get_current_user(host, token)
	if user is None:
		return 1
	logger.info(f"✓ Logged in as {user.get('username')} (user_id {user.get('user_id')}, provider {user.get('provider')})")
	return 0


if __name__ == "__main__":
	sys.exit(main())
