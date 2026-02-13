import json
from os import path
import sys

from fastapi.testclient import TestClient
# add backend to path
TEST_DIR = path.dirname(path.abspath(__file__))
PROJECT_DIR = path.dirname(path.dirname(TEST_DIR))

sys.path.append(PROJECT_DIR)

from backend.webserver import app
from backend.db import load_engine, get_db

from backend.test.dependencies import test_db, get_test_db, load_test_engine

app.dependency_overrides[get_db] = get_test_db
app.dependency_overrides[load_engine] = load_test_engine

client = TestClient(app)

def test_users():
    response = client.get("/api/v1/users")
    assert response.status_code == 200

    print('what methods were called on test_db?', test_db)
    print('calls', test_db.mock_calls)
    assert response.json() == []

def test_upload_sheet():
    file_path = path.join(TEST_DIR, 'fixtures', 'bpms.csv')

    with open(file_path, 'rb') as test_file:
        details = {
            'ssName': 'BPMs',
            'tab': 'Main',
            'description': 'Some description',
            'globalExtension': 'csv',
        }
        position = {'index': 0, 'total': 0}

        response = client.post(
            "/api/v1/sheets/upload",
            files={"file": ('bpms.csv', test_file, 'text/csv')},
            data={"details": json.dumps(details), "position": json.dumps(position) }
        )

        assert response.status_code == 200
        
        print('json', response.json())
        # Additional assertions as necessary
