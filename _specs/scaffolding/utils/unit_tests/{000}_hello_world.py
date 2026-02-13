import sys
import pytest
from pathlib import Path
import json

# Add the project root directory to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# Import shared fixtures and helper functions from conftest
from utils.unit_tests.conftest import (
    test_client,
    websocket,
    message_history,
    load_shoe_store_data,
    send_message,
    TEST_TOKEN,
)

def test_root(test_client):
  try:
    response = test_client.get("/api/v1/")
    print(f"Root response status: {response.status_code}")
    assert response.status_code == 200
    assert "Soleda AI" in response.text
  except Exception as e:
    pytest.fail(f"Root endpoint test failed: {str(e)}")

def test_health(test_client):
  try:
    response = test_client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
  except Exception as e:
    pytest.fail(f"Health endpoint test failed: {str(e)}")

def test_select_sheet(test_client, load_shoe_store_data):
  spreadsheet_data = {
    "ssName": "Shoe Store Sales",
    "tabNames": ["orders", "customers", "products"],
  }
  response = test_client.post("/api/v1/sheets/select", json=spreadsheet_data)
  assert response.status_code == 200, f"Failed to select spreadsheet: {response.text}"

  orders_sheet = response.json()
  assert len(orders_sheet['content']) == 256

def test_basic_hello(websocket):
  try:
      turn_one = send_message(websocket, "Hello, how are you?", '000')
      print("Turn 1 message:", turn_one)
      assert any(word in turn_one['message'].lower() for word in ['hi', 'hello', 'hey'])
      
      turn_two = send_message(websocket, "How many rows are in the orders table?", '014')
      print("Turn 2 message:", turn_two)
      tokens = turn_two['message'].split()
      assert '1712' in tokens or '1,712' in tokens, 'Wrong number of rows'

  except Exception as e:
    pytest.fail(f"Unexpected error in WebSocket test: {str(e)}")