
from fastapi.testclient import TestClient
from main import app
import sys
import traceback

client = TestClient(app)

def test_error():
    print("Sending query to /api/query...")
    try:
        response = client.post(
            "/api/query",
            json={
                "question": "what are the top 5 carriers based on shipment count",
                "history": [],
                "mode": "analytics"
            }
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception:
        with open('error_trace.txt', 'w', encoding='utf-8') as f:
            traceback.print_exc(file=f)
        print("Exception caught and written to error_trace.txt")

if __name__ == "__main__":
    test_error()
