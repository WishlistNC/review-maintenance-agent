"""
One-time test script — run this manually to see all fields on a single review.
Delete after use.
"""
import os
import json
import requests

OWNERREZ_API   = "https://api.ownerrez.com/v2"
OWNERREZ_TOKEN = os.environ["OWNERREZ_TOKEN"]

OR_HEADERS = {
    "Authorization": f"Bearer {OWNERREZ_TOKEN}",
    "Content-Type": "application/json",
    "User-Agent": "ReviewMaintenanceAgent/1.0",
}

REVIEW_ID = "1708695037598240133"

print(f"\n=== Fetching single review: {REVIEW_ID} ===\n")

# Try the individual review endpoint
resp = requests.get(
    f"{OWNERREZ_API}/reviews/{REVIEW_ID}",
    headers=OR_HEADERS,
    timeout=15,
)

print(f"Status code: {resp.status_code}")
print(f"Raw response:\n{json.dumps(resp.json(), indent=2)}")
