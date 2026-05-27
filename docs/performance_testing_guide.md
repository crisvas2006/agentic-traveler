# Performance & Load Testing Guide

This guide details how to configure, execute, and analyze performance and load tests for the **Agentic Traveler** backend. 

We use **Locust**, a Python-based load testing framework, to simulate high volumes of virtual user interactions (conversations, queries, promo redemptions) against the FastAPI server.

---

## 1. Zero-Overhead Architectural Design
To run high-volume load tests safely, quickly, and at **zero financial cost**, the backend has a built-in "Performance Test Mode" that completely mocks the two heaviest external boundaries:
1. **Gemini LLM calls** (`MOCK_LLM=true`)
2. **Telegram API HTTP calls** (`MOCK_TELEGRAM=true`)

### Absolute Zero Production Overhead
To guarantee that these testing capabilities do **not** introduce any runtime overhead or CPU latency in production:
* **Conditional Swapping at Import Time:** The mock functions are conditionally defined in `telegram.py` only **once** when the module is loaded by the interpreter.
* **No Per-Request Eval:** During production execution, FastAPI processes background tasks using directly compiled real-world methods, avoiding any conditional `if` checks or `os.getenv` lookups inside request paths.

---

## 2. Setting Up the Environment

Before running any performance tests, ensure that you have your virtual environment activated and the required dependencies installed:

```powershell
# Navigate to the backend directory
cd backend

# Activate the virtual environment
.\.venv\Scripts\Activate.ps1

# Install locust if not already present
pip install locust
```

---

## 3. Configuration Variables
You configure performance runs by passing environment variables to the FastAPI server:

| Environment Variable | Allowed Values | Purpose |
| :--- | :--- | :--- |
| **`MOCK_LLM`** | `true`, `false` | Bypasses actual Google GenAI calls with fast, standard synthetic mock responses. |
| **`MOCK_TELEGRAM`** | `true`, `false` | Bypasses outgoing Telegram HTTP calls at import time. |
| **`SKIP_IP_CHECK`** | `true`, `false` | Bypasses the Telegram IP whitelist verification (required for local/staging testing). |
| **`TELEGRAM_SECRET_TOKEN`** | *Any String* | Sets the secret webhook path token (e.g. `perf_test_secret`). |

---

## 4. Running Performance Tests Locally

### Option A: Lightweight Local Run (Uvicorn-based)
You can run a complete, headless automated test suite running against local Uvicorn with a single command. This runs uvicorn in mock mode, executes Locust, generates reports, and shuts down:

```powershell
# Run the automated PowerShell script
.\scripts\run_perf_test.ps1
```

### Option B: Interactive Run (Locust Web UI)
If you want to view live charts and adjust user count dynamically:

1. **Terminal 1: Start the Local FastAPI Mock Server:**
   ```powershell
   $env:MOCK_LLM = "true"
   $env:MOCK_TELEGRAM = "true"
   $env:SKIP_IP_CHECK = "true"
   $env:TELEGRAM_SECRET_TOKEN = "perf_test_secret"
   
   .\.venv\Scripts\uvicorn agentic_traveler.interfaces.main:app --port 8080 --reload
   ```

2. **Terminal 2: Launch the Locust Web Interface:**
   ```powershell
   $env:TELEGRAM_SECRET_TOKEN = "perf_test_secret"
   
   locust -f tests/performance/locustfile.py
   ```

3. **Terminal 3: Run the Test:**
   * Open your browser and navigate to `http://localhost:8089` (default port).
   * Enter the **Number of Users** (e.g., `100`).
   * Enter the **Spawn Rate** (e.g., `5` users per second).
   * Set the **Host** to `http://localhost:8080`.
   * Click **Start Swarming**.

### Option C: Emulated Cloud Run Docker Test (512MB RAM, 0.5 CPU, Active Rate Limiting)
To emulate the exact resource limits of your production Google Cloud Run deployment locally under load, you can run the automated Docker performance script. 

This script:
1. Cleans up any leftover container instances.
2. Builds the backend Docker image.
3. Launches a local container constrained to exactly **512 MB RAM** (`--memory="512m"`) and **0.5 CPU core** (`--cpus="0.5"`).
4. Enables active rate-limiting (`DISABLE_RATE_LIMIT=false`) to test realistic traffic.
5. Polls the server until it is fully healthy.
6. Launches Locust simulating a realistic user weight mix:
   * **95% `NormalTelegramUser`** (waits 8-15s, making 4-7 requests/min; never rate-limited).
   * **5% `SpammerTelegramUser`** (waits 0.5-1.5s, rapid-firing; quickly gets rate-limited).
7. Stops and removes the Docker container.
8. Opens the HTML report automatically in your default browser.

```powershell
# Run the Docker performance simulation script
.\scripts\run_docker_perf_test.ps1
```

---

## 5. Running Performance Tests Against Staging

To run performance tests against a deployed staging Google Cloud Run environment:

1. **Configure Staging Env-Vars:** 
   Deploy your revision to staging with mock flags active:
   ```bash
   gcloud run deploy agentic-traveler-staging \
     --image gcr.io/your-project-id/agentic-traveler \
     --update-env-vars "MOCK_LLM=true,MOCK_TELEGRAM=true,SKIP_IP_CHECK=true,TELEGRAM_SECRET_TOKEN=staging_perf_secret"
   ```

2. **Launch Locust:**
   Point the local Locust instance to your Cloud Run URL:
   ```powershell
   $env:TELEGRAM_SECRET_TOKEN = "staging_perf_secret"
   
   locust -f tests/performance/locustfile.py --host https://agentic-traveler-staging-xxxx.run.app
   ```

---

## 6. Analyzing Performance Reports & Metrics

Reports are written to the console in headless mode, and are accessible under the **Download Data** tab in the Locust Web UI.

### Critical Metrics to Track

1. **Requests/sec (RPS):** The overall request throughput handled by the application server. Standard Cloud Run instances easily sustain 200+ RPS under mock conditions.
2. **p50 Latency (Median):** The response time of 50% of the requests.
   * *Target:* **< 15ms** for `/health`, **< 30ms** for `/webhook` fast-path response.
3. **p95 / p99 Latency:** The tail response time. High p95 latency indicates database locks or FastAPI CPU bottlenecks.
   * *Target:* **< 50ms** for webhook immediate `200 OK`.
4. **Failures / %:** Any non-200 responses.
   * *Target:* **0.0%**. If failure rate is above 0%, review the backend logs to trace Supabase connection exhaustion or unhandled schema assertions.

### View Saved CSV Reports
When using the automated script, raw metrics are exported as CSV files at `tests/performance/reports/locust_summary_stats.csv`. This files includes individual statistics for:
- `/health`
- `/webhook/perf_test_secret`
