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
def test_remove_column(websocket, select_shoe_store_sheet):
  turn_one = send_message(websocket, "Please remove the channel column", '007', ['thought', 'code'])
  print("Turn 1 message:", turn_one)
  assert 'code' in turn_one, 'Missing deletion code'
  assert all([word in turn_one['code'] for word in ['channel', 'orders', 'drop']]), 'Wrong column deletion code'

  turn_two = send_message(websocket, "What columns are available in the orders table?", '14C')
  print("Turn 2 message:", turn_two)
  assert 'channel' not in turn_two['message'], 'Column should have been removed'

@pytest.mark.timeout(30)
def test_remove_row_by_id(websocket):
  turn_three = send_message(websocket, "How many people are there in the customers table?", '014')
  print("Turn 3 message:", turn_three)
  assert '584' in turn_three['message'], 'Wrong number of rows'

  turn_four = send_message(websocket, "Can we delete customer with ID 1403094", '007', ['code'])
  print("Turn 4 message:", turn_four)
  assert 'code' in turn_four, 'Missing insertion code'
  assert '1403094' in turn_four['code'], 'Wrong row deletion code'

@pytest.mark.timeout(30)
def test_remove_group_of_rows(websocket):
  turn_five = send_message(websocket, 
      "Now let's get rid of customers who are from Ontario, British Columbia, Quebec, or Alberta", '007')
  print("Turn 5 message:", turn_five)

  turn_six = send_message(websocket, "How many rows are in the customers table now?", '014')
  print("Turn 6 message:", turn_six)
  assert '528' in turn_six['message'], 'Wrong number of rows'
