# Review Maintenance Agent

Scans OwnerRez guest reviews daily, uses Claude AI to detect maintenance issues, 
and posts prioritized task lists to Slack's `#maintenance-rufus` channel.

## How it works

1. Every day at 8 AM UTC, the agent pulls reviews from the last 24 hours via OwnerRez API
2. Each review is analyzed by Claude, which extracts maintenance issues and classifies urgency
3. Findings are posted to `#maintenance-rufus` in Slack as a prioritized task list
4. Your team creates the tasks manually in Breezeway (for now)

## Urgency levels

| Level | Meaning | Target fix time |
|-------|---------|-----------------|
| 🔴 HIGH | Safety/habitability risk | Before next guest |
| 🟡 MEDIUM | Noticeable problem | Within 7 days |
| 🔵 LOW | Minor annoyance | Within 30 days |
| ⚪ RECOMMENDATION | Nice-to-have | Whenever |

## Setup

### 1. Environment variables (set these in Railway)

| Variable | Where to get it |
|----------|----------------|
| `ANTHROPIC_API_KEY` | console.anthropic.com |
| `OWNERREZ_TOKEN` | Same token from Night Shift agent |
| `SLACK_BOT_TOKEN` | Same Slack bot from Night Shift agent |
| `SLACK_CHANNEL` | `maintenance-rufus` (already defaulted) |

### 2. Deploy to Railway

```bash
# Create a new repo, push this code, connect to Railway
git init
git add .
git commit -m "Initial review maintenance agent"
# Connect repo in Railway dashboard → New Project → Deploy from GitHub
```

### 3. Set the cron schedule in Railway

In your Railway service settings, the `railway.toml` sets this to run daily at 8 AM UTC.
Adjust `cronSchedule` if you want a different time:
- `"0 8 * * *"` = 8 AM UTC daily (4 AM Eastern)
- `"0 12 * * *"` = 12 PM UTC daily (8 AM Eastern)
- `"0 14 * * *"` = 2 PM UTC daily (10 AM Eastern)  ← recommended

## Connecting Breezeway (when API is ready)

When you get Breezeway API access, only ONE file needs to change: `agent.py`

Find this function at the bottom of the file:

```python
def post_to_slack(property_name, review, issues):
    ...
    # 🔧 Tasks below — create manually in Breezeway until API is connected.
```

Add a call to a new `create_breezeway_task()` function for each issue. The data 
is already structured perfectly — `suggested_task`, `urgency`, `location`, and 
`detail` map directly to Breezeway's API fields:

| Our field | Breezeway field |
|-----------|----------------|
| `suggested_task` | `name` |
| `urgency` | `type_priority` (HIGH→high, MEDIUM→normal, LOW→low, RECOMMENDATION→watch) |
| `location` | part of `description` |
| `detail` | part of `description` |
| property_id | `home_id` |
| (hardcoded) | `type_department: "maintenance"` |
| (hardcoded) | `requested_by: "review"` |

That's it. Slack posting stays, Breezeway tasks get added alongside it.

## File structure

```
review-agent/
├── agent.py          # main logic — OwnerRez fetch, Claude analysis, Slack post
├── requirements.txt  # python dependencies
├── railway.toml      # Railway deployment + cron config
└── README.md         # this file
```
