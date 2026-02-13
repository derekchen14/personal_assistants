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
    message_history,
    load_ecommerce_data,
    send_message,
    TEST_TOKEN,
)

@pytest.mark.timeout(30)
def test_ambiguous_analysis(websocket, message_history, load_ecommerce_data):
  turn_one = send_message(websocket, 
    "What is the conversion rate for users from Google?", '002', ['query', 'actions', 'thought'])
  print("Turn 1:", turn_one)
  message_history.append(turn_one['message'])
  assert 'CLARIFY' in turn_one['actions'], 'Missing clarification action'

@pytest.mark.timeout(30)
def test_resolve_clarification(websocket, message_history):
  # Resolve the issue
  turn_two = send_message(websocket, "Consider the 'visit_site' activity type as a visit. Then count how many unique device ID from google ended up with a purchase. There is no need to join with the Purchases table. Use unique visitors (by DeviceID), and express as a percentage and no more questions", '002', ['actions', 'thought'])
  print("Turn 2:", turn_two)
  message_history.append(turn_two['message'])
  assert not turn_two['message'].startswith('Sorry'), 'Should not start interactive mode yet'

@pytest.mark.timeout(30)
def test_analyze_metric(websocket, message_history, test_client):
  most_recent_msg = message_history[-1]
  print("************")
  print(most_recent_msg)
  question_answered = False
  retry_count = 0

  while not question_answered and retry_count < 3:
    retry_count += 1
    if '?' not in most_recent_msg:
      user_text = ""
      question_answered = True
      break
    elif 'time frame' in most_recent_msg:
      user_text = "No need to restrict time frame, please use all available data"
    elif 'correct' in most_recent_msg:
      user_text = "Yes, go ahead and use your best judgement"
    elif 'checkout' in most_recent_msg:
      user_text = "Use 'purchase' as the conversion event"
    else:
      user_text = "Use the ActivityType column to find 'purchase' and 'visit_site' events"

    if len(user_text) > 0:
      turn_three = send_message(websocket, user_text, '002')
      print("Turn 3:", turn_three)
    
  assert any([token in most_recent_msg for token in ['33']]), 'Incorrect conversion rate'  # hard
