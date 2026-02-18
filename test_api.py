import requests
import json
import time

BASE_URL = "http://127.0.0.1:5000/api/query"

def print_response(r):
    try:
        data = r.json()
        print(f"Reply: {data.get('reply', 'No reply field')}")
        if data.get('reply') and 'NAVIGATE_TO' in data['reply']:
            print("Status: NAVIGATION DETECTED")
    except:
        print(f"Raw: {r.text}")

def test_navigation():
    print(f"\n{'='*20}\nTesting Navigation: 'check rates'")
    try:
        r = requests.post(BASE_URL, json={"question": "check rates", "mode": "help"})
        print_response(r)
    except Exception as e:
        print(f"Error: {e}")

def test_email_flow():
    print(f"\n{'='*20}\nTesting Email Flow")
    history = []
    
    # 1. Ask for some data first (to give context)
    q1 = "give me a summary of shipment rates"
    print(f"\nUser: {q1}")
    r1 = requests.post(BASE_URL, json={"question": q1, "history": history})
    print_response(r1)
    history.append({"role": "user", "content": q1})
    history.append({"role": "assistant", "content": r1.json().get('reply', '')})
    
    # 2. Ask to email
    q2 = "email this to me"
    print(f"\nUser: {q2}")
    r2 = requests.post(BASE_URL, json={"question": q2, "history": history})
    print_response(r2)
    history.append({"role": "user", "content": q2})
    history.append({"role": "assistant", "content": r2.json().get('reply', '')})
    
    # 3. Confirm
    q3 = "yes, send the summary"
    print(f"\nUser: {q3}")
    # We need to act as a logged in user for email to work? 
    # The code says `draft_email_tool` takes `to_usernames`. 
    # If not logged in, `to_usernames` might be empty or default?
    # Actually, main.py passes `to_usernames=["current_user"]` or similar? 
    # No, the tool definition has `to_usernames` as argument. The LLM populates it.
    # The system prompt says: "If they provide an email address... use that... If not... ASK for their email".
    # So I should probably say "yes, send to test@example.com" used in this test.
    
    q3 = "yes, send the summary to test@example.com"
    print(f"(Updating User input to provide email): {q3}")
    
    r3 = requests.post(BASE_URL, json={"question": q3, "history": history})
    print_response(r3)

if __name__ == "__main__":
    test_navigation()
    test_email_flow()
