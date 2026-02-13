from dotenv import load_dotenv
from urllib.parse import urlencode
import os
from backend.utilities.oauth_config import PROVIDER_CONFIG

load_dotenv()

OAUTH_CALLBACK_URL = os.getenv("OAUTH_CALLBACK_URL")


def get_client_credentials(data_source: str):
  """Retrieve client_id and client_secret from environment for a given provider."""
  prefix = data_source.upper()
  client_id = os.getenv(f"{prefix}_CLIENT_ID")
  client_secret = os.getenv(f"{prefix}_CLIENT_SECRET")
  if not client_id or not client_secret:
    raise ValueError(f"Missing client credentials for {data_source}")
  return client_id, client_secret


def create_oauth_url(data_source: str, state: str = None):
  """Generate an OAuth authorization URL for any configured provider."""
  if data_source not in PROVIDER_CONFIG:
    raise ValueError(f"Unsupported data source: {data_source}")

  config = PROVIDER_CONFIG[data_source]
  client_id, _ = get_client_credentials(data_source)

  params = {
    "client_id": client_id,
    "redirect_uri": OAUTH_CALLBACK_URL,
    "response_type": "code",
    "scope": " ".join(config["scopes"]),
  }
  if state:
    params["state"] = state

  return config["auth_url"] + "?" + urlencode(params)


def create_token_request(data_source: str, code: str, code_verifier: str = None):
  """Build the token-exchange HTTP request for any configured provider."""
  if data_source not in PROVIDER_CONFIG:
    raise ValueError(f"Unsupported data source: {data_source}")

  config = PROVIDER_CONFIG[data_source]["token_request"]
  client_id, client_secret = get_client_credentials(data_source)

  payload = config["payload_template"].copy()
  payload["redirect_uri"] = OAUTH_CALLBACK_URL
  payload["code"] = code
  payload["client_id"] = client_id
  payload["client_secret"] = client_secret

  if code_verifier:
    payload["code_verifier"] = code_verifier

  return config["url"], payload, config["headers"]


def create_resource_request(data_source: str, config: dict, access_token: str, instance_url: str = None):
  """Build the resource-fetch HTTP request for a given provider.

  Provider-specific logic should be added here as needed.
  Returns (url, headers, payload) for the API call.
  """
  headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
  }
  payload = {}

  # Default: use a resource_url from the provider config if present
  provider = PROVIDER_CONFIG.get(data_source, {})
  url = provider.get("resource_url", "")
  if instance_url:
    url = instance_url + url

  return url, headers, payload
