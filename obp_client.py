import http.cookiejar
import os
import obp_target  # loads .env and picks LOCAL or PROD settings
import requests
from json import loads
import logging

obp_log_level = os.getenv('OBP_LOG_LEVEL', 'INFO')

logging.basicConfig(level=obp_log_level)
logger = logging.getLogger("obp")
logger.propagate = True

# One HTTP session for every call to OBP, so connections are reused rather than
# reopened for each request (saves ~60 ms a request against a remote HTTPS host).
# It only pools connections: callers still pass their own headers (and token) on
# each call, and cookies are not kept, so one call never affects the next.
session = requests.Session()
session.cookies.set_policy(http.cookiejar.DefaultCookiePolicy(allowed_domains=[]))


def create_direct_login_token(username, user_password, consumer_key, obp_api_host, verify=True):
	authorization = f"DirectLogin username={username},password={user_password},consumer_key={consumer_key}"
	headers = {'Content-Type': 'application/json', 'Authorization': authorization}

	payload = None
	url = obp_api_host + "/my/logins/direct"
	try:
		req = session.post(url, headers=headers, json=payload, verify=verify)
		response_json = loads(req.text)
		if "token" not in response_json:
			logger.error(f"DirectLogin failed for user '{username}' at {url}")
			logger.error(f"API response: {req.text}")
			return None
		token = response_json["token"]
	except Exception as e:
		logger.exception(f'Error during DirectLogin for user {username}: {e}')
		token = None
	return token
obp_host = os.getenv('OBP_HOSTNAME', "http://obp-api-internal-route-obp.apps-crc.testing")

# Check OBP API is reachable before attempting authentication
def check_obp_api_health(base_url):
	"""Check if the OBP API is reachable by calling /obp/v6.0.0/root"""
	url = f"{base_url}/obp/v6.0.0/root"
	logger.info(f"Checking OBP API health at: {url}")
	try:
		response = session.get(url, timeout=10)
		response.raise_for_status()
		logger.info("OBP API is reachable")
	except requests.exceptions.ConnectionError:
		raise RuntimeError(f"Cannot connect to OBP API at {base_url}. Is the server running?")
	except requests.exceptions.Timeout:
		raise RuntimeError(f"Connection to OBP API at {base_url} timed out")
	except requests.exceptions.HTTPError as e:
		raise RuntimeError(f"OBP API returned an error: {e}")

check_obp_api_health(obp_host)

def mask_credential(value):
	"""Mask a credential showing first 3 and last 2 characters"""
	if len(value) <= 5:
		return value[:1] + '*' * (len(value) - 1)
	return value[:3] + '*' * (len(value) - 5) + value[-2:]


def required_env(name):
	try:
		return os.environ[name]
	except KeyError:
		logger.error(f'{name} not set in os environment or .env file! Exiting now.')
		exit(1)


def create_client_credentials_token(issuer, client_id, client_secret):
	"""An access token for this app itself (OAuth2 client credentials), or None (with the reason logged).
	The token endpoint is discovered from the issuer, as OGCR-chain-cache does."""
	try:
		discovery = session.get(f"{issuer.rstrip('/')}/.well-known/openid-configuration", timeout=10)
		discovery.raise_for_status()
		response = session.post(discovery.json()["token_endpoint"], timeout=10,
		                        data={"grant_type": "client_credentials"}, auth=(client_id, client_secret))
		if response.status_code != 200:
			logger.error(f"The client credentials token request was refused: {response.status_code} {response.text}")
			return None
		return response.json()["access_token"]
	except Exception as e:
		logger.exception(f"Error getting a client credentials token from {issuer}: {e}")
		return None


# How the scripts log in to OBP (OBP_AUTH_MODE):
#   user      (default) DirectLogin as OBP_USERNAME; the Roles are that user's Entitlements.
#   platform  as this app itself, a Platform App: an OAuth2 client credentials token from
#             OIDC_ISSUER for OIDC_CLIENT_ID / OIDC_CLIENT_SECRET; the Roles are Scopes of its
#             Consumer. OBP accepts this only on endpoints whose authMode is UserOrApplication
#             (and on records of entities whose auth_mode is): check_client_credentials.sh shows which.
auth_mode = os.getenv('OBP_AUTH_MODE', 'user').strip().lower()
if auth_mode not in ('user', 'platform'):
	logger.error(f"OBP_AUTH_MODE must be user or platform, not {auth_mode!r}. Exiting now.")
	exit(1)

logger.info(f"OBP_HOSTNAME: {obp_host}")
logger.info(f"OBP_AUTH_MODE: {auth_mode}")
if auth_mode == 'user':
	username = required_env('OBP_USERNAME')
	password = required_env('OBP_PASSWORD')
	consumer_key = required_env('OBP_CONSUMER_KEY')
	logger.info(f"OBP_USERNAME: {mask_credential(username)}")
	logger.info(f"OBP_PASSWORD: {mask_credential(password)}")
	logger.info(f"OBP_CONSUMER_KEY: {mask_credential(consumer_key)}")
	token = create_direct_login_token(username, password, consumer_key, obp_host)
else:
	oidc_issuer = required_env('OIDC_ISSUER')
	client_id = required_env('OIDC_CLIENT_ID')
	client_secret = required_env('OIDC_CLIENT_SECRET')
	# OBP knows the app as the User it creates for the client id, so that is the name recorded as author.
	username = client_id
	logger.info(f"OIDC_ISSUER: {oidc_issuer}")
	logger.info(f"OIDC_CLIENT_ID: {mask_credential(client_id)}")
	logger.info(f"OIDC_CLIENT_SECRET: {mask_credential(client_secret)}")
	token = create_client_credentials_token(oidc_issuer, client_id, client_secret)


def authorization(token):
	"""The Authorization header value for `token` in this auth mode."""
	return f"DirectLogin token={token}" if auth_mode == 'user' else f"Bearer {token}"


def require_user_mode(what):
	"""Stop a script that only makes sense for a logged-in user when running as a Platform App."""
	if auth_mode != 'user':
		logger.error(f"{what} acts for the logged-in user, so it needs OBP_AUTH_MODE=user (DirectLogin): "
		             "a Platform App has no user of its own.")
		exit(1)
