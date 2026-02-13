import sys
import pytest
from pathlib import Path

# Add the project root directory to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# Import shared fixtures and helper functions from conftest
from utils.unit_tests.conftest import (
    send_message,
    load_shoe_store_data,
)

@pytest.mark.timeout(30)
def test_filter_and_follow_up(websocket, load_shoe_store_data):
    # Explicitly load test data and verify it loaded correctly
    test_data = load_shoe_store_data
    assert test_data['spreadsheet'] == "Shoe Store Sales", "Wrong test data loaded"
    
    try:
        turn_one = send_message(websocket, "How much revenue did we make in March", '001')
        print("Turn 1:", turn_one)
        assert '7,350' in turn_one['message'] or '7350' in turn_one['message'], 'Wrong revenue in March'

        turn_two = send_message(websocket, "What about the month before that?", '001', ['query', 'thought'])
        print("Turn 2:", turn_two)
        assert '= 2025' in turn_two['query'] and 'EXTRACT' in turn_two['query'], 'Must extract a month from the date'
        if 'eb' in turn_two['message']:
            assert 'feb' in turn_two['message'].lower(), 'Wrong month for calculating revenue'
        else:
            assert 'feb' in turn_two['thought'].lower(), 'Wrong month for calculating revenue'

    except Exception as e:
        pytest.fail(f"Unexpected error in Query test: {str(e)}")


@pytest.mark.timeout(30)
def test_group_sort_values(websocket):
    try:
        turn_three = send_message(websocket, "Which shoe brand had the most number of orders?", '001')
        print("Turn 3:", turn_three)
        assert 'new balance' in turn_three['message'].lower(), 'Wrong shoe brand'

        turn_four = send_message(websocket, "What style of shoes does that come in?", '001', ['query'])
        print("Turn 4:", turn_four)
        assert 'new balance' in turn_four['query'].lower(), 'Missing shoe brand'

    except Exception as e:
        pytest.fail(f"Unexpected error in Query test: {str(e)}")

@pytest.mark.timeout(30)
def test_follow_up_query(websocket):
    try:
        turn_five = send_message(websocket, "Which customer from California bought the most last year?", '001')
        print("Turn 5:", turn_five)
        lowered = turn_five['message'].lower()
        assert any(word in lowered for word in ['joseph', 'thomas', '1402759']), 'Wrong customer name'

    except Exception as e:
        pytest.fail(f"Unexpected error in Query test: {str(e)}")