import os
import google.generativeai as genai
from dotenv import load_dotenv
import sys

# Redirect stdout to a file
sys.stdout = open("models_output.txt", "w", encoding="utf-8")

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("Error: GOOGLE_API_KEY not found in .env")
    exit(1)

genai.configure(api_key=api_key)

print(f"Checking models for API key: {api_key[:5]}...{api_key[-5:]}")

try:
    print("\nListing available models:")
    for m in genai.list_models():
        methods = m.supported_generation_methods
        if 'embedContent' in methods:
            print(f"EMBEDDING MODEL: {m.name}")
        elif 'generateContent' in methods:
            print(f"CHAT MODEL: {m.name}")
        else:
            print(f"OTHER MODEL: {m.name}")
except Exception as e:
    print(f"\nError listing models: {e}")
