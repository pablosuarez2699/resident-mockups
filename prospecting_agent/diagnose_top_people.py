"""Diagnostic: find the working URL/method for organization_top_people.

Run from prospecting_agent/ directory:
    python diagnose_top_people.py
"""
import os
import sys
from dotenv import load_dotenv
import requests

load_dotenv()
KEY = os.getenv("APOLLO_API_KEY", "").strip()
if not KEY:
    print("ERROR: APOLLO_API_KEY not set in .env"); sys.exit(1)

HEADERS = {"X-Api-Key": KEY, "Content-Type": "application/json", "Cache-Control": "no-cache"}

# Step 1: get one real org id (we know orgs/search works)
print("Step 1: fetching one real org id from organizations/search...")
r = requests.post(
    "https://api.apollo.io/v1/organizations/search",
    json={"page": 1, "per_page": 1, "organization_locations": ["Canada"]},
    headers=HEADERS, timeout=15,
)
if not r.ok:
    print(f"orgs/search failed: {r.status_code} {r.text[:300]}"); sys.exit(1)

orgs = r.json().get("organizations", []) or r.json().get("accounts", [])
if not orgs:
    print("orgs/search returned no orgs"); sys.exit(1)

org = orgs[0]
ORG_ID = org["id"]
ORG_NAME = org.get("name", "?")
print(f"  Got org: {ORG_NAME} (id={ORG_ID})\n")

# Step 2: try every variant we can think of
variants = [
    ("POST body organization_id",
     "POST", "https://api.apollo.io/v1/mixed_people/organization_top_people",
     {"organization_id": ORG_ID}),

    ("POST body id",
     "POST", "https://api.apollo.io/v1/mixed_people/organization_top_people",
     {"id": ORG_ID}),

    ("POST body organization_ids (array)",
     "POST", "https://api.apollo.io/v1/mixed_people/organization_top_people",
     {"organization_ids": [ORG_ID]}),

    ("GET ?organization_id=",
     "GET", f"https://api.apollo.io/v1/mixed_people/organization_top_people?organization_id={ORG_ID}",
     None),

    ("GET ?organization_ids[]=",
     "GET", f"https://api.apollo.io/v1/mixed_people/organization_top_people?organization_ids[]={ORG_ID}",
     None),

    ("GET path /:id",
     "GET", f"https://api.apollo.io/v1/mixed_people/organization_top_people/{ORG_ID}",
     None),

    ("POST /v1/organizations/:id/top_people",
     "POST", f"https://api.apollo.io/v1/organizations/{ORG_ID}/top_people",
     {}),

    ("GET /v1/organizations/:id/top_people",
     "GET", f"https://api.apollo.io/v1/organizations/{ORG_ID}/top_people",
     None),

    ("POST /v1/mixed_people/search w/ org filter (fallback)",
     "POST", "https://api.apollo.io/v1/mixed_people/search",
     {"organization_ids": [ORG_ID], "per_page": 5}),
]

print("Step 2: testing variants...\n" + "=" * 70)
for name, method, url, body in variants:
    try:
        if method == "POST":
            r = requests.post(url, json=body or {}, headers=HEADERS, timeout=15)
        else:
            r = requests.get(url, headers=HEADERS, timeout=15)
        snippet = r.text[:200].replace("\n", " ")
        marker = "✓✓✓ SUCCESS" if r.ok else f"{r.status_code} fail"
        print(f"[{marker}] {name}")
        print(f"          {method} {url.split('?')[0]}")
        print(f"          body: {snippet}\n")
    except Exception as e:
        print(f"[ERROR] {name}: {e}\n")

print("=" * 70)
print("Look for SUCCESS — that's the variant we wire into the agent.")
