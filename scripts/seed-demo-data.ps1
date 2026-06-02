$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendDir = Join-Path $Root "backend"
$Python = Get-Command python -ErrorAction Stop | Select-Object -ExpandProperty Source

$env:DATABASE_URL = if ($env:DATABASE_URL) { $env:DATABASE_URL } else { "sqlite:///./xr_test.db" }
$env:SECRET_KEY = if ($env:SECRET_KEY) { $env:SECRET_KEY } else { "test-secret-key-for-local-dev-only" }

Set-Location $BackendDir
& $Python ".\scripts\seed_demo_data.py"
