# scripts/run_local.ps1
# ─────────────────────────────────────────────────────────────────────────────
# Boot the FastAPI backend locally so the Next.js dev server (localhost:3000)
# can hit /chat/* via the Route Handlers.
#
# Expects backend/.env to contain at least:
#   GOOGLE_API_KEY=...
#   SUPABASE_URL=...
#   SUPABASE_SERVICE_KEY=...
#   SUPABASE_JWT_SECRET=...           ← copy the LEGACY JWT secret from Supabase
#   FRONTEND_ORIGIN=http://localhost:3000
#   TELEGRAM_SECRET_TOKEN=anything    ← required, even for local web-only
#
# load_dotenv() in main.py picks these up automatically.
# ─────────────────────────────────────────────────────────────────────────────
Set-Location "$PSScriptRoot\.."

# Skip the Telegram IP whitelist so /webhook/* (if you also test Telegram via
# ngrok) doesn't bounce.
$env:SKIP_IP_CHECK = "1"

Write-Host "→ Starting uvicorn on http://127.0.0.1:8080 ..." -ForegroundColor Cyan
Write-Host "  Frontend should set BACKEND_URL=http://127.0.0.1:8080 in its .env.local" `
  -ForegroundColor DarkGray

.\.venv\Scripts\uvicorn agentic_traveler.interfaces.main:app `
  --reload --port 8080 --host 127.0.0.1
