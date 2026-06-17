"""
Test script — tries multiple OwnerRez endpoints to find private feedback.
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

def dump(label, resp):
    print(f"\n{'='*60}")
    print(f"{label}")
    print(f"Status: {resp.status_code}")
    try:
        print(json.dumps(resp.json(), indent=2))
    except Exception:
        print(f"Raw text: {resp.text[:500]}")

# Step 1: Get a recent review to find booking_id
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

review = reviews[0]
review_id  = review["id"]
booking_id = review["booking_id"]
print(f"Using review_id={review_id}, booking_id={booking_id}")

# Test 1: Booking detail — does it include review with private feedback?
dump(
    f"TEST 1: GET /bookings/{booking_id}",
    requests.get(f"{OWNERREZ_API}/bookings/{booking_id}", headers=OR_HEADERS, timeout=15)
)

# Test 2: Reviews on a specific booking
dump(
    f"TEST 2: GET /reviews?booking_id={booking_id}",
    requests.get(f"{OWNERREZ_API}/reviews", headers=OR_HEADERS, params={"booking_id": booking_id}, timeout=15)
)

# Test 3: Try v1 reviews endpoint — older API sometimes has more fields
dump(
    f"TEST 3: GET v1/reviews/{review_id}",
    requests.get(f"https://api.ownerrez.com/v1/reviews/{review_id}", headers=OR_HEADERS, timeout=15)
)

# Test 4: Try v1 reviews list with booking_id
dump(
    f"TEST 4: GET v1/reviews?booking_id={booking_id}",
    requests.get(f"https://api.ownerrez.com/v1/reviews", headers=OR_HEADERS, params={"booking_id": booking_id}, timeout=15)
)
