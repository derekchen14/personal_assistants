import sys
import json
import time
import jwt
import pytest
from pathlib import Path
from collections import defaultdict

# Add the project root directory to the Python path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.assets.ontology import delay_responses
from fastapi.testclient import TestClient

from backend.webserver import app
from backend.db import get_db, load_engine
from backend.auth.credentials import get_auth_user_email
from backend.auth.JWT_helpers import decode_JWT
from utils.dependencies import get_test_db, load_test_engine

# JWT configuration
JWT_SECRET = "your-secret-key"
JWT_ALGORITHM = "HS256"

# Create payload
payload = {
  "email": "acromi@example.com",
  "userID": "test_user_123",
  "exp": int(time.time() + 3600)  # 1 hour expiry
}

# Sign the JWT token
TEST_TOKEN = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def get_test_user_email():
  return "acromi@example.com"

# Mock JWT decoder for testing
def mock_decode_jwt(token: str):
  # For testing, always return a valid payload with email
  return {
    "email": "acromi@example.com",
    "userID": "test_user_123",
    "exp": time.time() + 3600  # Expiry time is 1 hour from now
  }

@pytest.fixture(scope="module")
def test_client():
  app.dependency_overrides[get_db] = get_test_db
  app.dependency_overrides[load_engine] = load_test_engine
  app.dependency_overrides[get_auth_user_email] = get_test_user_email
  app.dependency_overrides[decode_JWT] = mock_decode_jwt
  
  client = TestClient(app)
  yield client
  
  app.dependency_overrides.clear()

@pytest.fixture(scope="module")
def websocket(test_client: TestClient):
  test_client.cookies.set("auth_token", TEST_TOKEN)
  with test_client.websocket_connect("/api/v1/ws") as ws:
    yield ws

@pytest.fixture(scope="module")
def message_history():
    messages = []
    yield messages

@pytest.fixture(scope="module")
def load_shoe_store_data(test_client):
  spreadsheet_data = {
    "ssName": "Shoe Store Sales",
    "tabNames": ["orders", "customers", "products"],
  }
  test_client.cookies.set("auth_token", TEST_TOKEN)
  response = test_client.post("/api/v1/sheets/select", json=spreadsheet_data)
  assert response.status_code == 200, f"Failed to load test data: {response.text}"
  return response.json()

@pytest.fixture(scope="module")
def load_ecommerce_data(test_client):
  spreadsheet_data = {
    "ssName": "E-commerce Web Traffic",
    "tabNames": ["activities", "purchases", "inventory"],
  }
  response = test_client.post("/api/v1/sheets/select", json=spreadsheet_data, cookies={"auth_token": TEST_TOKEN})
  assert response.status_code == 200, f"Failed to select spreadsheet: {response.text}"
  return response.json()

def decide_which_parts(parts):
  # determine which parts of the message to keep, returns boolean values
  store_query = 'query' in parts
  store_actions = 'actions' in parts
  store_code = 'code' in parts
  store_thought = 'thought' in parts
  return store_query, store_code, store_thought, store_actions

def decide_part_availability(parsed):
  # determine which parts are available in the message, returns boolean values
  has_query, has_code, has_thought, has_actions = False, False, False, False
  
  if 'interaction' in parsed.keys():
    if parsed['interaction'] and 'content' in parsed['interaction']:
      if 'SQL Query' in parsed['interaction'].get('content'):
        has_query = True
      if 'Pandas Code' in parsed['interaction'].get('content'):
        has_code = True
      if parsed['interaction'].get('flowType') == 'Default(thought)':
        has_thought = True
  if 'actions' in parsed.keys():
    has_actions = True
  return has_query, has_code, has_thought, has_actions

def send_message(websocket, message:str, gold_dax:str, parts:list=[]):
  websocket.send_json({'currentMessage': message, 'dialogueAct': gold_dax, 'lastAction': None}, mode='binary')
  store_query, store_code, store_thought, store_actions = decide_which_parts(parts)
  results = defaultdict(str)

  while True:
    try:
      raw_output = websocket.receive_json()

      if raw_output.get('message') in delay_responses:
        continue
      
      has_query, has_code, has_thought, has_actions = decide_part_availability(raw_output)
      if store_query and has_query:
        results['query'] = raw_output['interaction']['content'][19:]
      if store_code and has_code:
        results['code'] = raw_output['interaction']['content'][21:]
      if store_thought and has_thought:
        results['thought'] = raw_output['interaction']['content'][28:]
      if store_actions and has_actions:
        results['actions'] = raw_output['actions']
      if 'message' in raw_output.keys():
        results['message'] = raw_output['message']
        return results

    except json.JSONDecodeError as e:
      return f"Failed to decode JSON: {e}"