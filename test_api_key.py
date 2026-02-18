import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

def test_key():
    print("Testing API Key...")
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    
    if not api_key:
        print("❌ GOOGLE_API_KEY not found in environment!")
        return

    print(f"Key repr: {repr(api_key)}")
    print(f"Key found: {api_key[:5]}...{api_key[-5:]}")
    
    client = genai.Client(api_key=api_key)
    
    try:
        print("Attempting to generate content...")
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Hello, suggest a name for a robot."
        )
        print(f"✅ Success! Response: {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_key()
