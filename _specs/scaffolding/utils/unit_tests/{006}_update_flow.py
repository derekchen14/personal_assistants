import sys
import json
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

# Custom send_message function for update flow that handles the frame part
def send_update_message(websocket, message:str, gold_dax:str, parts:list=[]):
  websocket.send_json({'currentMessage': message, 'dialogueAct': gold_dax, 'lastAction': None}, mode='binary')
  store_query = 'query' in parts
  store_code = 'code' in parts
  store_frame = 'frame' in parts
  results = {}

  while True:
    try:
      raw_output = websocket.receive_json()
      
      # Check what parts are available in the response
      has_query, has_code, has_frame = False, False, False
      
      if 'interaction' in raw_output:
        if raw_output['interaction'] and 'content' in raw_output['interaction']:
          if 'SQL Query' in raw_output['interaction']['content']:
            has_query = True
          if 'Pandas Code' in raw_output['interaction']['content']:
            has_code = True
      if 'frame' in raw_output and len(raw_output.get('frame', '')) > 0:
        has_frame = True

      # Store requested parts
      if store_query and has_query:
        results['query'] = raw_output['interaction']['content'][19:]
      if store_code and has_code:
        results['code'] = raw_output['interaction']['content'][21:]
      if store_frame and has_frame:
        results['frame'] = json.loads(raw_output['frame'])
      if 'message' in raw_output:
        results['message'] = raw_output['message']
        return results

    except json.JSONDecodeError as e:
      return f"Failed to decode JSON: {e}"

  return 'Error'

@pytest.mark.timeout(30)
def test_change_single_value(websocket, select_shoe_store_sheet):
    turn_one = send_update_message(websocket, "What are the names of all the unique channels?", '001', ['frame'])
    print("Turn 1 message:", turn_one)
    assert 'frame' in turn_one, 'Missing frame'
    assert len(turn_one['frame']) == 22, 'Wrong number of unique channels'

    if 'however' in turn_one['message'].lower():
      ignore_turn = send_update_message(websocket, "That is not an issue", '00F')

    turn_two = send_update_message(websocket, "Please update Yahoo to search_yahoo", '006', ['code'])
    print("Turn 2 message:", turn_two)
    assert 'code' in turn_two, 'Missing update code'
    assert 'search_yahoo' in turn_two['code'], 'Wrong update code'

@pytest.mark.timeout(30)
def test_change_multiple_values(websocket):
    turn_three = send_update_message(websocket, 
      "I want to change both Google and google_search into 'search_google' for consistency", '006', ['code'])
    print("Turn 3 message:", turn_three)
    assert 'code' in turn_three, 'Missing update code'
    assert all([word in turn_three['code'] for word in ['search_google', 'google_search']]), 'Wrong update code'

    turn_four = send_update_message(websocket, "How many unique channels are there now?", '001')
    print("Turn 4 message:", turn_four)
    assert any(word in turn_four['message'] for word in ['19', 'nineteen']), 'Wrong number of unique channels'

@pytest.mark.timeout(30)
def test_follow_up_query(websocket):
  turn_five = send_update_message(websocket, "What is the average shoe size ordered in 2023?", '001')
  print("Turn 5 message:", turn_five)
  assert '8.8' in turn_five['message'], 'Wrong average shoe size'

  turn_six = send_update_message(websocket, "Ok, please show me", '46C')
  print("Turn 6 message:", turn_six)
  assert 'outliers' in turn_six['message'], 'Missing outliers detection'

  turn_seven = send_update_message(websocket, "Please fix the 100 to 10 and the 34 to size 9", '006')
  print("Turn 7 message:", turn_seven)
  assert all([word in turn_seven['message'] for word in ['row', 'updating', '8.7']]), 'Should pro-actively answer query'