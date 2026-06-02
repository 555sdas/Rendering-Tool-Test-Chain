$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendDir = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$Python = Get-Command python -ErrorAction Stop | Select-Object -ExpandProperty Source
$Npm = (Get-Command npm -ErrorAction Stop).Source

Write-Host "Running backend pytest..." -ForegroundColor Cyan
Set-Location $BackendDir
& $Python -m pytest

Write-Host "Running frontend type check..." -ForegroundColor Cyan
Set-Location $FrontendDir
& $Npm run check

Write-Host "Running frontend lint..." -ForegroundColor Cyan
& $Npm run lint

Write-Host "Running frontend build..." -ForegroundColor Cyan
& $Npm run build

Write-Host "Local tests completed." -ForegroundColor Green
