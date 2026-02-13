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
    select_sheet,
    TEST_TOKEN,
)

# Custom send_message function for plot flow since it needs different part handling
def send_message(websocket, message:str, gold_dax:str, parts:list=[]):
  websocket.send_json({'currentMessage': message, 'dialogueAct': gold_dax, 'lastAction': None}, mode='binary')
  store_query = 'query' in parts
  store_frame = 'frame' in parts
  store_graph = 'graph' in parts
  results = {}

  while True:
    try:
      raw_output = websocket.receive_json()
      
      # Check what parts are available in the response
      has_query, has_frame, has_graph = False, False, False
      
      if 'interaction' in raw_output:
        if raw_output['interaction']:
          if 'content' in raw_output['interaction']:
            if 'SQL Query' in raw_output['interaction']['content']:
              has_query = True
          if 'data' in raw_output['interaction']:
            if len(raw_output['interaction']['data']) > 0:
              has_graph = True
      
      if 'frame' in raw_output and len(raw_output.get('frame', '')) > 0:
        has_frame = True

      # Store requested parts
      if store_query and has_query:
        results['query'] = raw_output['interaction']['content'][19:]
      if store_graph and has_graph:
        results['graph'] = raw_output['interaction']['data'][0]['type']
      if store_frame and has_frame:
        results['frame'] = json.loads(raw_output['frame'])
      if 'message' in raw_output:
        results['message'] = raw_output['message']
        return results

    except json.JSONDecodeError as e:
      return f"Failed to decode JSON: {e}"

  return 'Error'

@pytest.fixture(scope="module")
def select_shoe_store_sheet(test_client):
  spreadsheet_data = {
    "ssName": "Shoe Store Sales",
    "tabNames": ["orders", "customers", "products"],
  }
  response = test_client.post("/api/v1/sheets/select", json=spreadsheet_data, cookies={"auth_token": TEST_TOKEN})
  assert response.status_code == 200, f"Failed to select spreadsheet: {response.text}"

@pytest.mark.timeout(30)
def test_plot_a_chart(websocket, select_shoe_store_sheet):
  try:
    turn_one = send_message(websocket, "What's the breakdown of sales per state as a pie chart?", '003', ['graph'])
    print("Turn 1 message:", turn_one)
    assert 'graph' in turn_one, 'Missing visualization'
    assert turn_one['graph'] == 'pie', 'Wrong chart type'

  except Exception as e:
    pytest.fail(f"Unexpected error in Visualize test: {str(e)}")

@pytest.mark.timeout(30)
def test_change_chart_type(websocket):
  try:
    turn_two = send_message(websocket, "Can I get that as a bar graph?", '003', ['graph', 'frame'])
    print("Turn 2 message:", turn_two)
    assert 'graph' in turn_two, 'Missing visualization'
    assert turn_two['graph'] == 'bar', 'Wrong chart type'

  except Exception as e:
    pytest.fail(f"Unexpected error in Visualize test: {str(e)}")

@pytest.mark.timeout(30)
def test_group_and_graph(websocket):
  try:
    turn_three = send_message(websocket, "How much money did we make each month in 2023?", '001', ['frame'])
    print("Turn 3 message:", turn_three)
    assert 'frame' in turn_three, 'Missing frame'
    assert len(turn_three['frame']) == 12, 'Wrong number of months'

    turn_four = send_message(websocket, "Actually, I would like to see that visually", '003', ['graph'])
    print("Turn 4 message:", turn_four)
    assert 'graph' in turn_four, 'Missing visualization'

  except Exception as e:
    pytest.fail(f"Unexpected error in Visualize test: {str(e)}")