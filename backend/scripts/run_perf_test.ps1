# scripts/run_perf_test.ps1
# Setup virtual environment and toggle mock parameters for load testing
$env:MOCK_LLM = "true"
$env:MOCK_TELEGRAM = "true"
$env:SKIP_IP_CHECK = "true"
$env:DISABLE_RATE_LIMIT = "false"
$env:TELEGRAM_SECRET_TOKEN = "perf_test_secret"

Write-Host "Booting FastAPI local server in MOCK mode..." -ForegroundColor Green
$serverProcess = Start-Process -FilePath "..\.venv\Scripts\python.exe" -ArgumentList "-m uvicorn agentic_traveler.interfaces.main:app --host 127.0.0.1 --port 8080" -PassThru -NoNewWindow

# Wait for startup
Start-Sleep -Seconds 3

# Make sure reports directory exists
New-Item -ItemType Directory -Force -Path "tests\performance\reports" | Out-Null

Write-Host "Initializing Locust headless load test (100 Virtual Users, 15s run time, rate limits active)..." -ForegroundColor Green
..\.venv\Scripts\locust.exe -f tests/performance/locustfile.py --host http://127.0.0.1:8080 --headless -u 100 -r 5 --run-time 15s --html=tests/performance/reports/locust_report.html

Write-Host "Shutting down FastAPI local server..." -ForegroundColor Red
Stop-Process -Id $serverProcess.Id

Write-Host "Performance test run completed! Opening interactive visual report..." -ForegroundColor Green
$reportPath = "tests\performance\reports\locust_report.html"
if (Test-Path $reportPath) {
    Start-Process $reportPath
} else {
    Write-Host "Warning: HTML report not found at $reportPath" -ForegroundColor Yellow
}

