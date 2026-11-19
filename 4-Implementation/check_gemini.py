"""Quick check that GEMINI_API_KEY and GEMINI_MODEL in .env work. Run this file in PyCharm (right-click > Run)."""
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")   # always reads the .env next to this file

key = os.environ.get("GEMINI_API_KEY", "")
model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
print("Model:", model, "| key set:", bool(key), "| key length:", len(key))

if not key:
    raise SystemExit("GEMINI_API_KEY is empty in .env")

r = requests.post(
    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
    headers={"x-goog-api-key": key, "Content-Type": "application/json"},
    json={"contents": [{"parts": [{"text": "Reply with the single word OK"}]}]},
    timeout=30,
)
print("HTTP status:", r.status_code)
print(r.text[:400])
print("\nRESULT:", "WORKS" if r.status_code == 200 else "NOT WORKING (see message above)")
