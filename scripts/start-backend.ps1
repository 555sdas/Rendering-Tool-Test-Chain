$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendDir = Join-Path $Root "backend"
$PythonCandidates = @(
    (Join-Path $BackendDir ".conda-test\python.exe"),
    (Join-Path $BackendDir ".venv\Scripts\python.exe"),
    (Join-Path $Root ".venv\Scripts\python.exe")
)

$Python = $PythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (!$Python) {
    $Python = (Get-Command python -ErrorAction Stop).Source
}

$env:DATABASE_URL = if ($env:DATABASE_URL) { $env:DATABASE_URL } else { "sqlite:///./xr_test.db" }
$env:SECRET_KEY = if ($env:SECRET_KEY) { $env:SECRET_KEY } else { "test-secret-key-for-local-dev-only" }
$env:PYTHONUNBUFFERED = "1"

Set-Location $BackendDir
& $Python -c "import uvicorn" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Error "当前 Python 缺少 uvicorn：$Python。请先运行：`n$Python -m pip install -r requirements.txt"
}

Write-Host "Starting backend on http://localhost:8002" -ForegroundColor Cyan
Write-Host "Python: $Python" -ForegroundColor DarkGray
& $Python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8002
