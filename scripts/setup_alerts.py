"""
Set up GCP Cloud Monitoring alerts for suspicious traffic.

Creates log-based metrics and alert policies for the Agentic Traveler
webhook.  Reads ALERTING_EMAIL from .env and GOOGLE_PROJECT_ID.

Usage:
    python scripts/setup_alerts.py

Prerequisites:
    - gcloud CLI installed and authenticated
    - ALERTING_EMAIL set in .env
    - GOOGLE_PROJECT_ID set in .env

Idempotent: safe to re-run (skips existing resources).
"""

import json
import os
import subprocess
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

PROJECT_ID = os.getenv("GOOGLE_PROJECT_ID", "")
ALERTING_EMAIL = os.getenv("ALERTING_EMAIL", "")

# ── Metric definitions ──
# Each tuple: (metric_id, description, log_filter)

LOG_METRICS = [
    (
        "non_telegram_ip",
        "Requests from non-Telegram IPs",
        'resource.type="cloud_run_revision"'
        ' resource.labels.service_name="agentic-traveler"'
        ' textPayload=~"Rejected request from non-Telegram IP"',
    ),
    (
        "auth_failure",
        "Invalid or missing secret token",
        'resource.type="cloud_run_revision"'
        ' resource.labels.service_name="agentic-traveler"'
        ' textPayload=~"Rejected: wrong"',
    ),
    (
        "rate_limit_hit",
        "User rate limit exceeded",
        'resource.type="cloud_run_revision"'
        ' resource.labels.service_name="agentic-traveler"'
        ' textPayload=~"Rate limit.*hit for user"',
    ),
    (
        "high_error_rate",
        "Cloud Run 5xx errors",
        'resource.type="cloud_run_revision"'
        ' resource.labels.service_name="agentic-traveler"'
        ' httpRequest.status>=500',
    ),
    (
        "user_restricted",
        "User access restricted (off-topic)",
        'resource.type="cloud_run_revision"'
        ' resource.labels.service_name="agentic-traveler"'
        ' textPayload=~"User restricted until"',
    ),
    (
        "high_token_usage",
        "High LLM token consumption",
        'resource.type="cloud_run_revision"'
        ' resource.labels.service_name="agentic-traveler"'
        ' textPayload=~"LLM usage"'
        ' textPayload=~"total_tokens="',
    ),
]

# ── Alert policy definitions ──
# Each tuple: (metric_id, display_name, threshold_value, period_seconds,
#              duration_seconds)

ALERT_POLICIES = [
    ("non_telegram_ip", "Non-Telegram IP requests", 5, 300, 0),
    ("auth_failure", "Auth failures (invalid secret)", 3, 300, 0),
    ("rate_limit_hit", "Rate limit abuse", 10, 600, 0),
    ("high_error_rate", "High 5xx error rate", 5, 300, 0),
    ("user_restricted", "Users restricted (off-topic)", 5, 3600, 0),
    ("high_token_usage", "High token consumption", 50, 3600, 0),
]


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a gcloud command and return the result."""
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    if check and result.returncode != 0:
        # Don't fail on "already exists" errors
        if "already exists" in result.stderr.lower():
            return result
        print(f"  ⚠ stderr: {result.stderr.strip()}")
    return result


def create_notification_channel() -> str:
    """Create an email notification channel and return its ID."""
    print(f"\n📧 Setting up email notification channel: {ALERTING_EMAIL}")

    # Check if channel already exists
    result = run([
        "gcloud", "beta", "monitoring", "channels", "list",
        f"--project={PROJECT_ID}",
        "--format=json",
    ])
    if result.returncode == 0 and result.stdout.strip():
        channels = json.loads(result.stdout)
        for ch in channels:
            labels = ch.get("labels", {})
            if labels.get("email_address") == ALERTING_EMAIL:
                channel_id = ch["name"]
                print(f"  ✅ Already exists: {channel_id}")
                return channel_id

    # Create new channel
    result = run([
        "gcloud", "beta", "monitoring", "channels", "create",
        f"--project={PROJECT_ID}",
        "--display-name=Agentic Traveler Alerts",
        "--type=email",
        f"--channel-labels=email_address={ALERTING_EMAIL}",
        "--format=value(name)",
    ])
    if result.returncode != 0:
        print("  ❌ Failed to create notification channel")
        print(f"     {result.stderr.strip()}")
        sys.exit(1)

    channel_id = result.stdout.strip()
    print(f"  ✅ Created: {channel_id}")
    return channel_id


def create_log_metrics():
    """Create log-based metrics."""
    print("\n📊 Creating log-based metrics...")

    for metric_id, description, log_filter in LOG_METRICS:
        print(f"  • {metric_id}: ", end="")

        result = run([
            "gcloud", "logging", "metrics", "create", metric_id,
            f"--project={PROJECT_ID}",
            f"--description={description}",
            f"--log-filter={log_filter}",
        ], check=False)

        if result.returncode == 0:
            print("✅ created")
        elif "already exists" in result.stderr.lower():
            print("✅ already exists")
        else:
            print(f"❌ {result.stderr.strip()}")


def _get_access_token() -> str:
    """Get an access token from gcloud for REST API calls."""
    result = run([
        "gcloud", "auth", "print-access-token",
    ])
    token = result.stdout.strip()
    if not token:
        print("  ❌ Failed to get access token from gcloud")
        sys.exit(1)
    return token


def create_alert_policies(channel_id: str):
    """Create alert policies via the Cloud Monitoring REST API."""
    print("\n🚨 Creating alert policies...")

    token = _get_access_token()
    api_url = (
        f"https://monitoring.googleapis.com/v3"
        f"/projects/{PROJECT_ID}/alertPolicies"
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    for metric_id, display_name, threshold, period, duration in ALERT_POLICIES:
        print(f"  • {display_name}: ", end="")

        policy = {
            "displayName": f"[Agentic Traveler] {display_name}",
            "conditions": [
                {
                    "displayName": display_name,
                    "conditionThreshold": {
                        "filter": (
                            f'metric.type="logging.googleapis.com/user/{metric_id}"'
                            f' AND resource.type="cloud_run_revision"'
                        ),
                        "comparison": "COMPARISON_GT",
                        "thresholdValue": threshold,
                        "duration": f"{duration}s",
                        "aggregations": [
                            {
                                "alignmentPeriod": f"{period}s",
                                "perSeriesAligner": "ALIGN_SUM",
                            }
                        ],
                    },
                }
            ],
            "notificationChannels": [channel_id],
            "combiner": "OR",
            "enabled": True,
        }

        try:
            resp = requests.post(api_url, headers=headers, json=policy, timeout=15)
            if resp.status_code in (200, 201):
                print("✅ created")
            elif resp.status_code == 409:
                print("✅ already exists")
            else:
                print(f"❌ {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"❌ {e}")


def main():
    if not PROJECT_ID:
        print("ERROR: GOOGLE_PROJECT_ID not set in .env")
        sys.exit(1)
    if not ALERTING_EMAIL:
        print("ERROR: ALERTING_EMAIL not set in .env")
        sys.exit(1)

    print(f"🔧 Setting up alerts for project: {PROJECT_ID}")
    print(f"   Email: {ALERTING_EMAIL}")

    channel_id = create_notification_channel()
    create_log_metrics()
    create_alert_policies(channel_id)

    print("\n✅ All done! Check your alerts at:")
    print(
        f"   https://console.cloud.google.com/monitoring/alerting"
        f"?project={PROJECT_ID}"
    )


if __name__ == "__main__":
    main()
