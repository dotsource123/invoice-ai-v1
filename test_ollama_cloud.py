import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("OLLAMA_API_KEY")
if not api_key:
    raise SystemExit("Set OLLAMA_API_KEY in your .env file first.")

response = requests.post(
    os.getenv("OLLAMA_URL", "https://ollama.com/api/chat"),
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    },
    json={
        "model": os.getenv("OLLAMA_MODEL", "gemma4:cloud"),
        "messages": [{"role": "user", "content": "Reply with exactly OK."}],
        "stream": False,
    },
    timeout=180,
)
response.raise_for_status()
print(response.json()["message"]["content"])
