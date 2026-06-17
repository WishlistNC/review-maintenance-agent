"""
One-time test script — fetches the most recent review individually and dumps all fields.
Delete after use.
"""
import os
import json
import requests
from datetime import datetime, timedelta, timezone

OWNERREZ_API   = "https://api.ownerrez.com/v2"
OWNERREZ_TOKEN = os.environ["OWNERREZ_TOKEN"]

OR_HEADERS = {
    "Authorization": f"Bearer {OWNERREZ_TOKEN}",
    "Content-Type": "application/json",
    "User-Agent": "ReviewMaintenanceAgent/1.0",
}

# Step 1: Get recent reviews to find a valid OwnerRez review ID
since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00Z")
resp = requests.get(
    f"{OWNERREZ_API}/reviews",
    headers=OR_HEADERS,
    params={"since_utc": since, "limit": 5},
    timeout=30,
)
data = resp.json()
reviews = data.get("items", data) if isinstance(data, dict) else data

if not reviews:
    print("No reviews found in last 7 days")
    exit()

# Step 2: Print list-level fields for first review
first = reviews[0]
print(f"\n=== LIST endpoint fields for review {first['id']} ===")
print(json.dumps(first, indent=2))

# Step 3: Fetch same review individually
print(f"\n=== DETAIL endpoint: /reviews/{first['id']} ===")
detail_resp = requests.get(
    f"{OWNERREZ_API}/reviews/{first['id']}",
    headers=OR_HEADERS,
    timeout=15,
)
print(f"Status code: {detail_resp.status_code}")
if detail_resp.status_code == 200:
    print(json.dumps(detail_resp.json(), indent=2))
else:
    print(f"Response text: {detail_resp.text}")
