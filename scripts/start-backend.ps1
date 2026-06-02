$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendDir = Join-Path $Root "backend"
$Python = Get-Command python -ErrorAction Stop | Select-Object -ExpandProperty Source

$env:DATABASE_URL = if ($env:DATABASE_URL) { $env:DATABASE_URL } else { "sqlite:///./xr_test.db" }
$env:SECRET_KEY = if ($env:SECRET_KEY) { $env:SECRET_KEY } else { "test-secret-key-for-local-dev-only" }
$env:PYTHONUNBUFFERED = "1"

Set-Location $BackendDir
Write-Host "Starting backend on http://localhost:8002" -ForegroundColor Cyan
& $Python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8002
