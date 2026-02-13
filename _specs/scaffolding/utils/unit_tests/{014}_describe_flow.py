import sys
import pytest
from pathlib import Path

# Add the project root directory to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# Import shared fixtures and helper functions from conftest
from utils.unit_tests.conftest import (
    test_client,
    websocket,
    send_message,
    TEST_TOKEN,
)

@pytest.fixture(scope="module")
def select_shoe_store_sheet(test_client):
  spreadsheet_data = {
    "ssName": "Shoe Store Sales",
    "tabNames": ["orders", "customers", "products"],
  }
  response = test_client.post("/api/v1/sheets/select", json=spreadsheet_data, cookies={"auth_token": TEST_TOKEN})
  assert response.status_code == 200, f"Failed to select spreadsheet: {response.text}"

@pytest.mark.timeout(30)
def test_basic_describe(websocket, select_shoe_store_sheet):
  turn_one = send_message(websocket, "How big is the customers table?", '014')
  print("Turn 1:", turn_one)
  assert '584' in turn_one['message'] and '6' in turn_one['message'], 'Wrong table size'

  turn_two = send_message(websocket, "How many unique channels are there?", '014', ['query', 'thought'])
  print("Turn 2:", turn_two)
  assert '22' in turn_two['message'], 'Wrong number of channels'

@pytest.mark.timeout(30)
def test_multi_fact_request(websocket):
  turn_three = send_message(websocket, "What is the mean, median, min and max shoe size?", '014')
  print("Turn 3:", turn_three)
  assert '8.8' in turn_three['message'] and '100' in turn_three['message'], 'Wrong shoe size stats'

@pytest.mark.timeout(30)
def test_existence_request(websocket):
  turn_four = send_message(websocket, "Are there any columns related to customer names?", '14C')
  print("Turn 4:", turn_four)
  assert 'first' in turn_four['message'] and 'last' in turn_four['message'], 'Missing column names'

@pytest.mark.timeout(30)
def test_preview_request(websocket):
  turn_five = send_message(websocket, "What sort of data is in the products table?", '014')
  print("Turn 5:", turn_five)
  lowered = turn_five['message'].lower()
  assert all(word in lowered for word in ['brand', 'style', 'cost']), 'Missing column details'