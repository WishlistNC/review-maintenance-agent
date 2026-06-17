import os
import json
import requests
from datetime import datetime, timedelta
from anthropic import Anthropic

# ── Clients ──────────────────────────────────────────────────────────────────
anthropic = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

OWNERREZ_API   = "https://api.ownerrez.com/v2"
OWNERREZ_TOKEN = os.environ["OWNERREZ_TOKEN"]
SLACK_TOKEN    = os.environ["SLACK_BOT_TOKEN"]
SLACK_CHANNEL  = os.environ.get("SLACK_CHANNEL", "maintenance-rufus")

OR_HEADERS = {
    "Authorization": f"Bearer {OWNERREZ_TOKEN}",
    "Content-Type": "application/json",
    "User-Agent": "ReviewMaintenanceAgent/1.0",
}

# ── OwnerRez ─────────────────────────────────────────────────────────────────

def get_recent_reviews(days_back: int = 1) -> list[dict]:
    """Fetch reviews submitted in the last `days_back` days."""
    from datetime import timezone
    since = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%dT00:00:00Z")
    resp = requests.get(
        f"{OWNERREZ_API}/reviews",
        headers=OR_HEADERS,
        params={"since_utc": since, "limit": 100},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    reviews = data.get("items", data) if isinstance(data, dict) else data
    print(f"[OwnerRez] Fetched {len(reviews)} review(s) since {since}")
    return reviews


def get_property_name(property_id: int) -> str:
    """Look up a property's nickname/name by ID."""
    try:
        resp = requests.get(
            f"{OWNERREZ_API}/properties/{property_id}",
            headers=OR_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("name") or data.get("nickname") or f"Property {property_id}"
    except Exception:
        return f"Property {property_id}"

# ── Claude analysis ───────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a property maintenance analyst for a short-term rental company.

Your job: read guest reviews (public and/or private) and extract ONLY maintenance issues or home improvement needs.

Private feedback is often more candid and detailed — treat it with equal importance to the public review.

For EACH issue found, return a JSON object with:
- issue: short description (e.g. "Dripping kitchen faucet")
- location: where in the property (e.g. "Kitchen", "Master bathroom", "Backyard")
- urgency: one of RECOMMENDATION / LOW / MEDIUM / HIGH
- detail: the relevant quote or paraphrase from the review
- suggested_task: a clear task title a maintenance tech would understand
- source: either "public" or "private" — where the issue was mentioned

Urgency guide:
- RECOMMENDATION: nice-to-have improvement, no impact on guest experience
- LOW: minor annoyance, fix within 30 days
- MEDIUM: noticeable problem, fix within 7 days
- HIGH: affects safety, habitability, or next guest's stay — fix ASAP

Return ONLY a JSON array. If no maintenance issues exist, return [].
No preamble, no markdown, no explanation — just the JSON array."""


def analyze_review(review_text: str) -> list[dict]:
    """Send review to Claude, get back list of maintenance issues."""
    if not review_text or not review_text.strip():
        return []

    response = anthropic.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Review:\n{review_text}"}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"[Claude] Failed to parse JSON: {raw[:200]}")
        return []

# ── Slack ─────────────────────────────────────────────────────────────────────

URGENCY_EMOJI = {
    "HIGH":           "🔴",
    "MEDIUM":         "🟡",
    "LOW":            "🔵",
    "RECOMMENDATION": "⚪",
}

URGENCY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "RECOMMENDATION": 3}


def post_to_slack(property_name: str, review: dict, issues: list[dict]) -> None:
    """Post a formatted maintenance summary to Slack."""
    reviewer   = review.get("reviewer_name") or review.get("guest_name") or "Guest"
    rating     = review.get("rating") or review.get("overall_rating", "?")
    review_url = review.get("url") or ""

    issues = sorted(issues, key=lambda x: URGENCY_ORDER.get(x.get("urgency", "LOW"), 99))

    bullets = []
    for i in issues:
        emoji   = URGENCY_EMOJI.get(i.get("urgency", "LOW"), "⚪")
        urgency = i.get("urgency", "LOW")
        task    = i.get("suggested_task", i.get("issue", "Unknown issue"))
        loc     = i.get("location", "")
        detail  = i.get("detail", "")
        source  = i.get("source", "")
        source_tag = " 🔒 _private_" if source == "private" else ""
        line = f"{emoji} *[{urgency}]* {task}{source_tag}"
        if loc:
            line += f" _({loc})_"
        if detail:
            line += f"\n   > _{detail}_"
        bullets.append(line)

    bullet_text = "\n\n".join(bullets)
    link_text   = f" | <{review_url}|View review>" if review_url else ""

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"🏠 Maintenance Items — {property_name}"},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Guest:* {reviewer}  |  *Rating:* {'⭐' * int(rating) if str(rating).isdigit() else rating}{link_text}",
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": bullet_text},
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "🔧 Tasks below — create manually in Breezeway until API is connected. 🔒 = from private feedback only.",
                }
            ],
        },
    ]

    resp = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={
            "Authorization": f"Bearer {SLACK_TOKEN}",
            "Content-Type": "application/json",
        },
        json={"channel": SLACK_CHANNEL, "blocks": blocks, "text": f"Maintenance items found for {property_name}"},
        timeout=15,
    )
    data = resp.json()
    if not data.get("ok"):
        print(f"[Slack] Error posting: {data.get('error')}")
    else:
        print(f"[Slack] Posted {len(issues)} issue(s) for {property_name}")


def post_no_issues_summary(count: int) -> None:
    """Post a brief all-clear if no maintenance items were found."""
    from datetime import timezone
    today = datetime.now(timezone.utc).strftime("%b %d, %Y")
    print(f"[Slack] Posting all-clear to #{SLACK_CHANNEL}...")
    resp = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={
            "Authorization": f"Bearer {SLACK_TOKEN}",
            "Content-Type": "application/json",
        },
        json={
            "channel": SLACK_CHANNEL,
            "text": f"✅ *Daily Review Scan — {today}*\nAnalyzed {count} review(s). No maintenance items found.",
        },
        timeout=15,
    )
    data = resp.json()
    if data.get("ok"):
        print(f"[Slack] ✅ All-clear posted successfully!")
    else:
        print(f"[Slack] ❌ Failed to post: {data.get('error')} | Full response: {data}")

# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    from datetime import timezone
    print(f"\n{'='*60}")
    print(f"Review Maintenance Agent — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}")

    reviews = get_recent_reviews(days_back=1)

    if not reviews:
        print("[Agent] No new reviews in the last 24 hours.")
        post_no_issues_summary(0)
        return

    total_issues = 0
    property_cache = {}

    for review in reviews:
        # Pull public review text
        public_fields = ["comments", "body", "review_text", "text", "public_review"]
        public_text = next((review.get(f) for f in public_fields if review.get(f)), None)

        # Pull private feedback — log all keys first run so we can confirm field name
        private_fields = ["private_feedback", "private_comments", "private_notes", "feedback"]
        private_text = next((review.get(f) for f in private_fields if review.get(f)), None)

        # Log keys to help identify private feedback field name in OwnerRez response
        print(f"[Agent] Review {review.get('id')} fields: {list(review.keys())}")
        if private_text:
            print(f"[Agent] ✅ Private feedback found for review {review.get('id')}")

        if not public_text and not private_text:
            print(f"[Agent] Review {review.get('id')} has no text — skipping")
            continue

        # Combine public and private for Claude, clearly labeled
        combined_text = ""
        if public_text:
            combined_text += f"PUBLIC REVIEW:\n{public_text}\n\n"
        if private_text:
            combined_text += f"PRIVATE FEEDBACK:\n{private_text}"

        # Get property name
        prop_id = review.get("property_id") or review.get("home_id")
        if prop_id not in property_cache:
            property_cache[prop_id] = get_property_name(prop_id)
        prop_name = property_cache[prop_id]

        print(f"\n[Agent] Analyzing review for {prop_name}...")
        issues = analyze_review(combined_text)

        if issues:
            print(f"[Agent] Found {len(issues)} maintenance item(s)")
            post_to_slack(prop_name, review, issues)
            total_issues += len(issues)
        else:
            print(f"[Agent] No maintenance items in this review")

    if total_issues == 0:
        post_no_issues_summary(len(reviews))

    print(f"\n[Agent] Done. {len(reviews)} review(s) scanned, {total_issues} total issue(s) found.")


if __name__ == "__main__":
    run()
