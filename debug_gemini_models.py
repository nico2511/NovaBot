import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ API Key not found in .env")
    exit(1)

genai.configure(api_key=api_key)

print(f"Checking models for key: {api_key[:5]}...")

try:
    print("Available Models:")
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"- {m.name}")
            # print(dir(m)) # Debug if needed
except Exception as e:
    print(f"❌ Error listing models: {e}")
