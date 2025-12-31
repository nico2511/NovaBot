import google.generativeai as genai
import os
from dotenv import load_dotenv
import time

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

models_to_test = [
    'gemini-2.0-flash',
    'gemini-2.5-flash',
    'gemini-flash-latest',
    'gemini-1.5-flash'
]

print(f"Testing generation with key: {api_key[:5]}...")

for model_name in models_to_test:
    print(f"\nTesting {model_name}...")
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content("Say 'Hello'")
        print(f"✅ SUCCESS: {response.text}")
        break
    except Exception as e:
        print(f"❌ FAIL: {e}")
