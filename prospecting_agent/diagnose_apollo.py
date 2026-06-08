"""Diagnostic: tries every known Apollo auth method and reports which works.

Run from prospecting_agent/ directory:
    python diagnose_apollo.py
"""
import os
import sys
from dotenv import load_dotenv
import requests

load_dotenv()
KEY = os.getenv("APOLLO_API_KEY", "").strip()

if not KEY:
    print("ERROR: APOLLO_API_KEY not set in .env")
    sys.exit(1)

print(f"Testing Apollo key: {KEY[:6]}...{KEY[-4:]} (length={len(KEY)})")
print()

# Minimal valid payload for /mixed_people/search
TEST_PAYLOAD = {
    "page": 1,
    "per_page": 1,
    "person_titles": ["CEO"],
    "person_locations": ["Canada"],
}

variants = [
    ("Header X-Api-Key",
     "https://api.apollo.io/v1/mixed_people/search",
     {"X-Api-Key": KEY, "Content-Type": "application/json", "Cache-Control": "no-cache"},
     TEST_PAYLOAD),

    ("Body api_key",
     "https://api.apollo.io/v1/mixed_people/search",
     {"Content-Type": "application/json", "Cache-Control": "no-cache"},
     {**TEST_PAYLOAD, "api_key": KEY}),

    ("Authorization Bearer",
     "https://api.apollo.io/v1/mixed_people/search",
     {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json", "Cache-Control": "no-cache"},
     TEST_PAYLOAD),

    ("Query param api_key",
     f"https://api.apollo.io/v1/mixed_people/search?api_key={KEY}",
     {"Content-Type": "application/json", "Cache-Control": "no-cache"},
     TEST_PAYLOAD),

    ("Header X-Api-Key on /people/search",
     "https://api.apollo.io/v1/people/search",
     {"X-Api-Key": KEY, "Content-Type": "application/json", "Cache-Control": "no-cache"},
     TEST_PAYLOAD),

    ("Body api_key on /people/search",
     "https://api.apollo.io/v1/people/search",
     {"Content-Type": "application/json", "Cache-Control": "no-cache"},
     {**TEST_PAYLOAD, "api_key": KEY}),

    ("api.apollo.io/api/v1/mixed_people/search w/ Bearer",
     "https://api.apollo.io/api/v1/mixed_people/search",
     {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
     TEST_PAYLOAD),
]

print("=" * 70)
for name, url, headers, payload in variants:
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        snippet = r.text[:180].replace("\n", " ")
        status = f"{r.status_code} {'OK' if r.ok else 'FAIL'}"
        print(f"[{status}] {name}")
        print(f"        URL: {url.split('?')[0]}")
        print(f"        Body: {snippet}")
    except Exception as e:
        print(f"[ERROR] {name}: {e}")
    print()
print("=" * 70)
print("Look for the first line that says '200 OK' — that's the auth method that works.")
