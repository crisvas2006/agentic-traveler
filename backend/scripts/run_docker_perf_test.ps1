# scripts/run_docker_perf_test.ps1
# Automates the entire performance test suite under Docker resource limitations.
# Restricts container to 512MB memory and 0.5 CPU to emulate GCP Cloud Run behavior.

# Exit immediately if any command fails
$ErrorActionPreference = "Stop"

# 1. Clean up any existing container with the same name
$existing = docker ps -a --filter "name=agentic-traveler-restricted" --format "{{.ID}}"
if ($existing) {
    Write-Host "Stopping and removing existing 'agentic-traveler-restricted' container..." -ForegroundColor Yellow
    docker stop agentic-traveler-restricted | Out-Null
    docker rm agentic-traveler-restricted | Out-Null
}

# 2. Build the Docker image locally
Write-Host "Building Docker image 'agentic-traveler-backend'..." -ForegroundColor Green
docker build -t agentic-traveler-backend .

# Parse the TELEGRAM_SECRET_TOKEN from .env if present
$token = "perf_test_secret"
if (Test-Path ".env") {
    $envLines = Get-Content ".env"
    foreach ($line in $envLines) {
        if ($line -match "^TELEGRAM_SECRET_TOKEN=(.+)$") {
            $token = $Matches[1].Trim()
        }
    }
}
Write-Host "Using TELEGRAM_SECRET_TOKEN: $token" -ForegroundColor Yellow

# 3. Run the container with Cloud Run resource constraints (512MB RAM, 0.5 CPU)
# Enable Mocks and ACTIVE Rate Limiting (DISABLE_RATE_LIMIT = false)
Write-Host "Running container with limits: 512MB RAM, 0.5 CPU..." -ForegroundColor Green
docker run -d -p 8080:8080 `
  --name agentic-traveler-restricted `
  --memory="512m" `
  --cpus="0.5" `
  -e MOCK_LLM="true" `
  -e MOCK_TELEGRAM="true" `
  -e SKIP_IP_CHECK="true" `
  -e DISABLE_RATE_LIMIT="false" `
  -e TELEGRAM_SECRET_TOKEN="$token" `
  agentic-traveler-backend

# 4. Wait for the FastAPI server inside the container to be healthy
Write-Host "Waiting for backend server to become healthy..." -ForegroundColor Yellow
$retries = 0
$healthy = $false
while ($retries -lt 15 -and -not $healthy) {
    try {
        $response = Invoke-RestMethod -Uri "http://127.0.0.1:8080/health" -Method Get -TimeoutSec 1
        if ($response.status -eq "ok") {
            $healthy = $true
        }
    } catch {
        Start-Sleep -Seconds 1
        $retries++
    }
}

if (-not $healthy) {
    Write-Host "Error: Server failed to start inside container! Container logs:" -ForegroundColor Red
    docker logs agentic-traveler-restricted
    docker stop agentic-traveler-restricted | Out-Null
    docker rm agentic-traveler-restricted | Out-Null
    exit 1
}
Write-Host "Server is healthy!" -ForegroundColor Green

# 5. Initialize reports directory
New-Item -ItemType Directory -Force -Path "tests\performance\reports" | Out-Null

# 6. Execute Locust load testing
Write-Host "Initializing Locust headless load test (100 Virtual Users, 15s run time)..." -ForegroundColor Green
# Pass token matching the container env
$env:TELEGRAM_SECRET_TOKEN = $token

# Execute headless Locust suite
..\.venv\Scripts\locust.exe -f tests/performance/locustfile.py --host http://127.0.0.1:8080 --headless -u 5000 -r 200 --run-time 30s --html=tests/performance/reports/locust_report.html

# 7. Post-test cleanup
Write-Host "Shutting down and removing Docker container..." -ForegroundColor Red
docker stop agentic-traveler-restricted | Out-Null
docker rm agentic-traveler-restricted | Out-Null

# 8. Open HTML report in default browser
Write-Host "Opening interactive performance report..." -ForegroundColor Green
$reportPath = "tests\performance\reports\locust_report.html"
if (Test-Path $reportPath) {
    Start-Process $reportPath
} else {
    Write-Host "Warning: HTML report not found at $reportPath" -ForegroundColor Yellow
}

Write-Host "Performance test run successfully completed!" -ForegroundColor Green
