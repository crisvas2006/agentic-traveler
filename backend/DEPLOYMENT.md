# Deployment Instructions

This guide explains how to deploy the Agentic Traveler to Google Cloud Run.

## Prerequisites

1. **Google Cloud Project** with billing enabled
2. **[gcloud CLI](https://cloud.google.com/sdk/docs/install)** installed and initialized
3. **APIs enabled**:
   ```bash
   gcloud services enable run.googleapis.com cloudbuild.googleapis.com
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
# Core
TELEGRAM_BOT_TOKEN=your-bot-token-from-botfather
TELEGRAM_SECRET_TOKEN=your-generated-secret
GOOGLE_API_KEY=your-gemini-api-key
GOOGLE_PROJECT_ID=your-gcp-project-id
GEMINI_REGION=europe-west1

# Supabase (Project Settings → API + JWT Keys)
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SERVICE_KEY=<service-role-key>
SUPABASE_JWT_SECRET=<Legacy JWT secret, used to verify access tokens>

# Web chat — comma-separated origin allowlist for CORS.
# Local:      http://localhost:3000
FRONTEND_ORIGIN=http://localhost:3000

# Optional
TALLY_WEBHOOK_TOKEN=<tally-secret>
APP_ADMIN_API_KEY=<admin-key>
```

> **JWT secret note:** Supabase is migrating to JWT Signing Keys (asymmetric RS256). For now, copy the value from the **Legacy JWT Secret** tab in Project Settings → API → JWT Keys — that's what tokens are still signed with. When the backend later moves to JWKS-based verification, this env var goes away.

## Pre-Deployment Regression Check

Before deploying any major changes, you **must** run the regression test suite to ensure existing features haven't broken.

1. **Run Automated Tests:**
   Ensure the `pytest` suite passes with zero errors:
   ```powershell
   .\.venv\Scripts\pytest
   ```
2. **Run Manual Staging Tests:**
   Start the local FastAPI server (`uvicorn agentic_traveler.interfaces.main:app --reload --port 8080`) and route Telegram to it using ngrok. 
   Then, follow the step-by-step instructions in `tests/manual_test_flow.md` to validate core agent capabilities (Profile linking, Routing, Memory, Tools) via Telegram.

Once both automated and manual tests pass, proceed with deployment.

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

Once your secrets are created in Secret Manager (see Step 2.5), run the deployment command. 

**IMPORTANT:** Cloud Run persists your configuration. You only need to specify `--set-secrets` or `--set-env-vars` when you want to **change** the configuration. Subsequent deployments of new images only need the `--image` flag.

```bash
gcloud run deploy agentic-traveler \
  --image gcr.io/YOUR_PROJECT_ID/agentic-traveler \
  --region europe-west1 \
  --platform managed \
  --allow-unauthenticated \
  --max-instances 1 \
  --concurrency 10 \
  --no-cpu-throttling \
  --memory 512Mi \
  --timeout 120 \
  --set-env-vars "GOOGLE_PROJECT_ID=your-project-id,GEMINI_REGION=global,FRONTEND_ORIGIN=https://www..." \
  --set-secrets="TELEGRAM_BOT_TOKEN=TELEGRAM_BOT_TOKEN:latest,TELEGRAM_SECRET_TOKEN=TELEGRAM_SECRET_TOKEN:latest,GOOGLE_API_KEY=GOOGLE_API_KEY:latest,SUPABASE_URL=SUPABASE_URL:latest,SUPABASE_SERVICE_KEY=SUPABASE_SERVICE_KEY:latest,SUPABASE_JWT_SECRET=SUPABASE_JWT_SECRET:latest,TALLY_WEBHOOK_TOKEN=TALLY_WEBHOOK_TOKEN:latest,GOOGLE_CLOUD_PROJECT=GOOGLE_CLOUD_PROJECT:latest,APP_ADMIN_API_KEY=APP_ADMIN_API_KEY:latest"
```

> **Note on `--no-cpu-throttling`:** Required for FastAPI BackgroundTasks processing. Without it, Cloud Run throttles CPU to near-zero after the HTTP `200` is returned, stalling the background task before it completes the LLM call and Telegram reply.

> **Note on Configuration Persistence:** If you are just updating the code, you can simply run:
> `gcloud run deploy agentic-traveler --image gcr.io/YOUR_PROJECT_ID/agentic-traveler`
> Cloud Run will reuse all existing secret and environment variable mappings.


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

### 1. Start the FastAPI app

```powershell
$env:SKIP_IP_CHECK="1"
.\.venv\Scripts\uvicorn agentic_traveler.interfaces.main:app --reload --port 8080
```

> `SKIP_IP_CHECK=1` disables the Telegram IP whitelist for local testing.

### 2. Start ngrok

```powershell
ngrok http 8080
```

Copy the `https://xxx.ngrok-free.dev` URL.

### 3. Register webhook with ngrok

```powershell
.\.venv\Scripts\python scripts/register_webhook.py --url https://xxx.ngrok-free.app
```

### 4. Chat in Telegram

Messages flow: **Telegram → ngrok → local FastAPI → response**.

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

## Tally Webhook

The Tally webhook is fully integrated into the main application as the
`/tally-webhook` endpoint. No separate Cloud Function deployment is needed.

### Required environment variable

Add `TALLY_WEBHOOK_TOKEN` to your Cloud Run env vars (same deploy command):

```
TALLY_WEBHOOK_TOKEN=your-tally-secret-token
```

This token must match the **Authorization** header Tally sends with every
submission (`Bearer <token>`).

### Endpoint

```
POST https://your-cloud-run-url/tally-webhook
Authorization: Bearer <TALLY_WEBHOOK_TOKEN>
```

Configure this URL in your Tally form's Webhook integration settings.
