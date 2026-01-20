import os
from dotenv import load_dotenv
import requests
from json import loads
import logging

load_dotenv()
obp_log_level = os.getenv('OBP_LOG_LEVEL', 'INFO')

logging.basicConfig(level=obp_log_level)
logger = logging.getLogger("obp")
logger.propagate = True


def create_direct_login_token(username, user_password, consumer_key, obp_api_host, verify=True):
	authorization = f"DirectLogin username={username},password={user_password},consumer_key={consumer_key}"
	headers = {'Content-Type': 'application/json', 'Authorization': authorization}

	payload = None
	url = obp_api_host + "/my/logins/direct"
	try:
		req = requests.post(url, headers=headers, json=payload, verify=verify)
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
	"""Check if the OBP API is reachable by calling /obp/v5.1.0/root"""
	url = f"{base_url}/obp/v5.1.0/root"
	logger.info(f"Checking OBP API health at: {url}")
	try:
		response = requests.get(url, timeout=10)
		response.raise_for_status()
		logger.info("OBP API is reachable")
	except requests.exceptions.ConnectionError:
		raise RuntimeError(f"Cannot connect to OBP API at {base_url}. Is the server running?")
	except requests.exceptions.Timeout:
		raise RuntimeError(f"Connection to OBP API at {base_url} timed out")
	except requests.exceptions.HTTPError as e:
		raise RuntimeError(f"OBP API returned an error: {e}")

check_obp_api_health(obp_host)

try:
	username = os.environ['OBP_USERNAME']
except KeyError:
	logger.exception('OBP_USERNAME not set in os environment or .env file! Exiting now.')
	exit(1)
try:
	password = os.environ['OBP_PASSWORD']
except KeyError:
	logger.exception('OBP_PASSWORD not set in os environment or .env file! Exiting now.')
	exit(1)
try:
	consumer_key = os.environ['OBP_CONSUMER_KEY']
except KeyError:
	logger.exception('OBP_CONSUMER_KEY not set in os environment or .env file! Exiting now.')
	exit(1)

def mask_credential(value):
	"""Mask a credential showing first 3 and last 2 characters"""
	if len(value) <= 5:
		return value[:1] + '*' * (len(value) - 1)
	return value[:3] + '*' * (len(value) - 5) + value[-2:]

logger.info(f"OBP_HOSTNAME: {obp_host}")
logger.info(f"OBP_USERNAME: {mask_credential(username)}")
logger.info(f"OBP_PASSWORD: {mask_credential(password)}")
logger.info(f"OBP_CONSUMER_KEY: {mask_credential(consumer_key)}")

token = create_direct_login_token(username, password, consumer_key, obp_host)



