
from fastapi.testclient import TestClient
from main import app
import sys

# Redirect stderr to stdout so we can capture traceback
sys.stderr = sys.stdout

client = TestClient(app)

def test_error_message():
    print("Sending query to /api/query to trigger error...")
    # I will mock the handle_query to raise an exception to test the handler
    # specific to the route logic, but since I can't easily mock inside the running app from outside
    # without complex patching, I will rely on the fact that my previous attempt
    # triggered *some* error (even if not the NoneType one).
    #
    # Wait, the previous reproduction attempt actually returned 200 OK with a valid response!
    # "Status Code: 200" and prompt result.
    # To truly test the exception handler, I need to force an error.
    #
    # I'll create a new route temporarily in main.py that raises an exception,
    # OR I can mock the `genai_client` to raise an exception.
    pass

    # Let's try to mock the authenticate_user or something that is called.
    # Actually, the easiest way is to modify main.py to raise an exception for a specific query
    # "FORCE_ERROR".
    
    response = client.post(
        "/api/query",
        json={
            "question": "FORCE_ERROR",
            "history": [],
            "mode": "analytics"
        }
    )
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    
    expected_msg = "⚠️ **System Error:** Something went wrong. I have logged the error for the developers to fix."
    if response.json().get("reply") == expected_msg:
        print("SUCCESS: Generic error message verified.")
    else:
        print(f"FAILURE: Expected '{expected_msg}', got '{response.json().get('reply')}'")

if __name__ == "__main__":
    test_error_message()
