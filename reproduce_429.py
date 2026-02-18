
import asyncio
import sys
from unittest.mock import MagicMock, patch
from fastapi import Request
from google.api_core.exceptions import ResourceExhausted

# Mock the environment variables before importing main
import os
os.environ["GOOGLE_API_KEY"] = "fake_key"
os.environ["GEMINI_MODEL"] = "gemini-1.5-flash"

# Patch google.genai.Client to avoid real API calls during import
with patch('google.genai.Client'):
    import main

# Function to simulate the request
async def test_429_error():
    print("Starting test...")
    
    # Mock the chat object and its send_message method
    mock_chat = MagicMock()
    mock_chat.send_message.side_effect = ResourceExhausted("429 Resource Exhausted")
    
    # Mock the genai_client.chats.create to return our mock_chat
    # main.genai_client is already a mock due to the patch above?
    # No, we need to patch the instance on main
    main.genai_client.chats = MagicMock()
    main.genai_client.chats.create.return_value = mock_chat

    # Create a mock request
    mock_request = MagicMock(spec=Request)
    mock_request.json.return_value = {
        "question": "What is the capital of France?",
        "mode": "help",
        "history": []
    }
    
    # We need to manually invoke the exception handler because direct call doesn't use it
    try:
        response = await main.handle_query(mock_request)
        print("Response received (no exception raised):")
        if isinstance(response, main.JSONResponse):
            body = json.loads(response.body)
            print(f"Reply: {body.get('reply')}")
            return body.get('reply')
    except Exception as e:
        print(f"Exception caught in test: {e}")
        # Build a mock request for the exception handler
        # global_exception_handler expects (request, exc)
        handler_response = await main.global_exception_handler(mock_request, e)
        body = json.loads(handler_response.body)
        print(f"Handler Reply: {body.get('reply')}")
        return body.get('reply')

if __name__ == "__main__":
    import json
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    reply = loop.run_until_complete(test_429_error())
    
    expected_msg = "Oops. I am out of fuel! Tell your Developer to refuel me!"
    
    if expected_msg in reply:
        print("\nSUCCESS: Custom error message found.")
    else:
        print(f"\nFAILURE: Expected '{expected_msg}', got '{reply}'") 
