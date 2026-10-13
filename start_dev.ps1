# TraceIQ Local Development Startup Script
# Requires: Docker Desktop running (for PostgreSQL), Python 3.11, Node 20

Write-Host "=== TraceIQ Development Setup ===" -ForegroundColor Cyan

# 1. Start only the DB in Docker
Write-Host "`n[1/4] Starting PostgreSQL via Docker..." -ForegroundColor Yellow
docker compose up -d db
Start-Sleep -Seconds 5

# 2. Wait for DB
Write-Host "[2/4] Waiting for PostgreSQL to be ready..." -ForegroundColor Yellow
$retries = 0
do {
    $retries++
    Start-Sleep -Seconds 2
    $result = docker compose exec db pg_isready -U traceiq -d traceiq 2>&1
} while ($result -notmatch "accepting connections" -and $retries -lt 15)

if ($retries -ge 15) {
    Write-Host "ERROR: PostgreSQL did not start in time." -ForegroundColor Red
    exit 1
}
Write-Host "PostgreSQL is ready." -ForegroundColor Green

# 3. Create virtualenv and install deps if needed
Write-Host "[3/4] Setting up Python virtual environment..." -ForegroundColor Yellow
Push-Location .\backend
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
& .\.venv\Scripts\Activate.ps1

pip install -r requirements.txt --quiet

# Set env vars for local dev (pointing to localhost DB, host Ollama)
$env:DATABASE_URL = "postgresql+asyncpg://traceiq:traceiq_secret@localhost:5432/traceiq"
$env:DATABASE_URL_SYNC = "postgresql://traceiq:traceiq_secret@localhost:5432/traceiq"
$env:LLM_BASE_URL = "http://localhost:11434/v1"
$env:LLM_MODEL = "llama3.2"
$env:LLM_API_KEY = "ollama"
$env:UPLOAD_DIR = "./uploads"
$env:ML_MODELS_DIR = "./ml_models"
$env:SECRET_KEY = "traceiq-dev-secret-key-change-in-production-32chars"

# Run migrations
Write-Host "Running Alembic migrations..." -ForegroundColor Yellow
alembic upgrade head

# 4. Start FastAPI
Write-Host "[4/4] Starting FastAPI backend on http://localhost:8000 ..." -ForegroundColor Yellow
Pop-Location

# Start backend in a new terminal window
Start-Process powershell -ArgumentList "-NoExit", "-Command", "
  cd '$PWD\backend';
  .\.venv\Scripts\Activate.ps1;
  `$env:DATABASE_URL='postgresql+asyncpg://traceiq:traceiq_secret@localhost:5432/traceiq';
  `$env:DATABASE_URL_SYNC='postgresql://traceiq:traceiq_secret@localhost:5432/traceiq';
  `$env:LLM_BASE_URL='http://localhost:11434/v1';
  `$env:LLM_MODEL='llama3.2';
  `$env:LLM_API_KEY='ollama';
  `$env:UPLOAD_DIR='./uploads';
  `$env:ML_MODELS_DIR='./ml_models';
  `$env:SECRET_KEY='traceiq-dev-secret-key-change-in-production-32chars';
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"

# Start frontend
Write-Host "Starting Vite frontend on http://localhost:5173 ..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD\frontend'; npm run dev"

Write-Host "`n=== TraceIQ is starting ===" -ForegroundColor Cyan
Write-Host "Frontend: http://localhost:5173" -ForegroundColor Green
Write-Host "Backend:  http://localhost:8000" -ForegroundColor Green
Write-Host "API Docs: http://localhost:8000/docs" -ForegroundColor Green
Write-Host "`nOllama must be running locally with: ollama run llama3.2" -ForegroundColor Yellow
