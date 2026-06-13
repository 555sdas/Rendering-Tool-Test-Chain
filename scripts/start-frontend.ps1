param(
    [switch]$Browser
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$FrontendDir = Join-Path $Root "frontend"
$Npm = (Get-Command npm -ErrorAction Stop).Source

$env:VITE_API_BASE_URL = if ($env:VITE_API_BASE_URL) { $env:VITE_API_BASE_URL } else { "http://localhost:8002/api/v1" }

Set-Location $FrontendDir
if ($Browser) {
    Write-Host "Starting browser frontend on http://localhost:5173" -ForegroundColor Cyan
    & $Npm run dev -- --host 0.0.0.0
} else {
    Write-Host "Starting Electron desktop frontend..." -ForegroundColor Cyan
    & $Npm run desktop:dev
}
