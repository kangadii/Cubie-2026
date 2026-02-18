import requests
import json
import time

BASE_URL = "http://127.0.0.1:5000/api/query"

def print_response(r):
    try:
        data = r.json()
        print(f"Reply: {data.get('reply', 'No reply field')}")
        if data.get('error'):
            print(f"Error: {data.get('error')}")
    except Exception as e:
        print(f"Failed to parse JSON: {e}")
        print(r.text)

def test_help_quality():
    print(f"\n{'='*20}\nTesting Help Quality")
    
    # Question about deep content in Rate Maintenance
    # Assuming RateMaintenance.html has detailed steps
    query = "What are the specific steps to add a new rate in rate maintenance?"
    
    payload = {
        "question": query,
        "mode": "help",
        "history": []
    }
    
    print(f"User: {query}")
    try:
        r = requests.post(BASE_URL, json=payload, timeout=60)
        print_response(r)
        
        data = r.json()
        reply = data.get('reply', '')
        
        # Simple heuristic check
        if len(reply) > 200:
            print("\n✅ Response seems detailed enough.")
        else:
            print("\n❌ Response might be too short.")
            
        if "rate maintenance" in reply.lower():
            print("✅ Response mentions the topic.")
        
    except Exception as e:
        print(f"Error hitting API: {e}")

if __name__ == "__main__":
    # Wait for server to start if needed
    time.sleep(2)
    test_help_quality()
