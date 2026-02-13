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
def test_add_formula(websocket, select_shoe_store_sheet):
  turn_one = send_message(websocket, 
    "Let's make a column called 'is_luxury' which is true when the shoe type is 'Women' and the style is 'fashion'",
    '005', ['thought', 'code'])
  print("Turn 1:", turn_one)
  assert 'code' in turn_one, 'Missing insertion code'
  assert all([word in turn_one['code'] for word in ['is_luxury', 'type', 'style']]), 'Wrong column insertion code'

  turn_two = send_message(websocket, "How many luxury shoes were sold in 2023?", '001')
  print("Turn 2:", turn_two)
  assert '134' in turn_two['message'], 'Wrong number of luxury shoes sold'

@pytest.mark.timeout(30)
def test_calculated_value(websocket):
  turn_three = send_message(websocket, "How many columns are in the customers table?", '014')
  print("Turn 3:", turn_three)
  assert any(word in turn_three['message'] for word in ['six', '6', 'Six']), 'Wrong number of columns'

  turn_four = send_message(websocket,
      "Can we add a column to the customers table that shows how much each person spent in 2022?",
      '005', ['code'])
  print("Turn 4:", turn_four)
  assert 'code' in turn_four, 'Missing insertion code'

@pytest.mark.timeout(30)
def test_directly_assigned_value(websocket):
  turn_five = send_message(websocket, 
      "Please make a new column in the customers table called 'location' that simply contains 'home' in every row.", '005')
  print("Turn 5:", turn_five)

  turn_six = send_message(websocket, "How many columns does the customers table have now?", '014')
  print("Turn 6:", turn_six)
  assert any(word in turn_six['message'] for word in ['8', 'eight', 'Eight']), 'Wrong number of columns'