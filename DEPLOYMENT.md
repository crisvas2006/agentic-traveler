# Deployment Instructions

This guide explains how to deploy the Agentic Traveler to Google Cloud Run.

## Prerequisites

1. **Google Cloud Project** with billing enabled
2. **[gcloud CLI](https://cloud.google.com/sdk/docs/install)** installed and initialized
3. **APIs enabled**:
   ```bash
   gcloud services enable run.googleapis.com cloudbuild.googleapis.com firestore.googleapis.com
   ```
4. **Telegram Bot Token** from [@BotFather](https://t.me/BotFather)
5. **Gemini API Key** from [AI Studio](https://aistudio.google.com/)

## Environment Setup

Generate a webhook secret token:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Add all credentials to your `.env`:

```env
TELEGRAM_BOT_TOKEN=your-bot-token-from-botfather
TELEGRAM_SECRET_TOKEN=your-generated-secret
GOOGLE_API_KEY=your-gemini-api-key
GOOGLE_PROJECT_ID=your-gcp-project-id
GEMINI_REGION=europe-west1
```

## Deploy to Cloud Run

### Step 1: Set your project

```bash
gcloud config set project YOUR_PROJECT_ID
```

### Step 2: Build the Docker image

```bash
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/agentic-traveler
```

This builds the image in the cloud (no local Docker required) and pushes it to Container Registry.

### Step 3: Deploy

```bash
gcloud run deploy agentic-traveler \
  --image gcr.io/YOUR_PROJECT_ID/agentic-traveler \
  --region europe-west1 \
  --platform managed \
  --allow-unauthenticated \
  --max-instances 1 \
  --concurrency 10 \
  --set-env-vars "TELEGRAM_BOT_TOKEN=your-bot-token,TELEGRAM_SECRET_TOKEN=your-secret,GOOGLE_API_KEY=your-api-key,GOOGLE_PROJECT_ID=your-project-id,GEMINI_REGION=europe-west1" \
  --memory 512Mi \
  --timeout 60
```

> **Note:** `--allow-unauthenticated` is required because Telegram can't use Google IAM.
> All authentication happens at the application level (secret token + IP whitelist).

The command outputs a URL like `https://agentic-traveler-xxxxx.run.app`.

### Step 4: Register the Telegram webhook

```powershell
.\.venv\Scripts\python scripts/register_webhook.py --url https://agentic-traveler-xxxxx.run.app
```

This registers `https://your-url/webhook/<SECRET_TOKEN>` with Telegram.

### Step 5: Test

1. Open your bot in Telegram
2. Send `/start` — should get a welcome message
3. Send a travel question — should get an agent response

## Local Development with ngrok

For testing the webhook locally without deploying:

### 1. Start the Flask app

```powershell
$env:SKIP_IP_CHECK="1"
.\.venv\Scripts\python -m agentic_traveler.webhook
```

> `SKIP_IP_CHECK=1` disables the Telegram IP whitelist for local testing.

### 2. Start ngrok

```powershell
ngrok http 8080
```

Copy the `https://xxx.ngrok-free.app` URL.

### 3. Register webhook with ngrok

```powershell
.\.venv\Scripts\python scripts/register_webhook.py --url https://xxx.ngrok-free.app
```

### 4. Chat in Telegram

Messages flow: **Telegram → ngrok → local Flask → response**.

When done, re-register the webhook with your Cloud Run URL.

## Updating the deployment

After code changes:

```bash
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/agentic-traveler
gcloud run deploy agentic-traveler --image gcr.io/YOUR_PROJECT_ID/agentic-traveler --region europe-west1
```

## Security

The endpoint is protected by multiple layers:

| Layer | Protection |
|-------|-----------|
| Secret URL path | Webhook URL contains a random secret — not guessable |
| Secret token header | Telegram sends a secret header with every request |
| IP whitelist | Only accepts requests from Telegram's IP ranges |
| Rate limiting | 10 msgs/user/min, 60 msgs/user/hour |
| Payload validation | Rejects malformed or empty updates |
| Cloud Run limits | 1 instance, 10 concurrent, 60s timeout |

## Monitoring logs

### Real-time log tailing

```bash
gcloud beta run services logs tail agentic-traveler --region europe-west1
```

### Errors/warnings only

```bash
gcloud beta run services logs tail agentic-traveler --region europe-west1 --log-filter="severity>=WARNING"
```

### Cloud Logging console

Open in browser:

```
https://console.cloud.google.com/logs/query?project=YOUR_PROJECT_ID
```

Filter with:

```
resource.type="cloud_run_revision"
resource.labels.service_name="agentic-traveler"
```

## Alerting (suspicious traffic)

### Prerequisites

Add `ALERTING_EMAIL` to your `.env`:

```
ALERTING_EMAIL=your-email@example.com
```

### Setup alerts

```powershell
.\.venv\Scripts\python scripts/setup_alerts.py
```

This creates 6 log-based metrics and alert policies in Cloud Monitoring:

| Alert | Threshold |
|-------|-----------|
| Non-Telegram IP requests | ≥ 5 in 5 min |
| Auth failures (invalid secret) | ≥ 3 in 5 min |
| Rate limit abuse | ≥ 10 in 10 min |
| High 5xx error rate | ≥ 5 in 5 min |
| Users restricted (off-topic) | ≥ 5 in 1 hour |
| High token consumption | ≥ 50 events in 1 hour |
| High CPU utilization | > 80% (p95) for 5 min |
| High memory utilization | > 80% (p95) for 5 min |
| High request latency | > 15s (p95) for 5 min |

### Live resource monitoring

```
https://console.cloud.google.com/run/detail/europe-west1/agentic-traveler/metrics?project=YOUR_PROJECT_ID
```

### Test alerts

**Quick test (alerts 1-2, no setup needed):**

```powershell
.\.venv\Scripts\python scripts/test_alerts.py
```

**Full test (all 6 alerts):**

```powershell
# 1. Temporarily allow non-Telegram IPs
gcloud run services update agentic-traveler `
  --region europe-west1 `
  --update-env-vars SKIP_IP_CHECK=true

# 2. Run all tests
.\.venv\Scripts\python scripts/test_alerts.py --all

# 3. Wait 3-8 min, check email + GCP Console

# 4. IMPORTANT: Remove SKIP_IP_CHECK
gcloud run services update agentic-traveler `
  --region europe-west1 `
  --remove-env-vars SKIP_IP_CHECK
```

**Postman:** Import `tests/postman/alert_tests.postman_collection.json` and set the `secret_token` collection variable.

### View alerts

```
https://console.cloud.google.com/monitoring/alerting?project=YOUR_PROJECT_ID
```

## Deleting the webhook

```powershell
.\.venv\Scripts\python scripts/register_webhook.py --url dummy --delete
```

## Deploying Tally Webhook v2

The Tally Webhook has been separated into its own Cloud Run Function under the `tally_webhook_v2` directory.

To deploy it:

```bash
cd tally_webhook_v2
gcloud run deploy tally-webhook-v2 \
  --source . \
  --function tally_webhook \
  --region europe-west1 \
  --allow-unauthenticated \
  --set-env-vars="TALLY_WEBHOOK_TOKEN=your-secret-token"
```

Replace `your-secret-token` with the actual token configured in your Tally form.

