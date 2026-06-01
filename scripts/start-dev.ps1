$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendScript = Join-Path $PSScriptRoot "start-backend.ps1"
$FrontendScript = Join-Path $PSScriptRoot "start-frontend.ps1"

$PowerShellExe = (Get-Command pwsh -ErrorAction SilentlyContinue).Source
if (!$PowerShellExe) {
    $PowerShellExe = (Get-Command powershell.exe -ErrorAction Stop).Source
}

function Quote-Arg([string]$Value) {
    '"' + $Value.Replace('"', '\"') + '"'
}

Write-Host "Opening backend and frontend terminals..." -ForegroundColor Cyan

Start-Process -FilePath $PowerShellExe `
    -WorkingDirectory $Root `
    -ArgumentList "-NoExit -ExecutionPolicy Bypass -File $(Quote-Arg $BackendScript)"

Start-Process -FilePath $PowerShellExe `
    -WorkingDirectory $Root `
    -ArgumentList "-NoExit -ExecutionPolicy Bypass -File $(Quote-Arg $FrontendScript)"

Write-Host "Backend:  http://localhost:8002/api/v1/docs" -ForegroundColor Green
Write-Host "Frontend: http://localhost:5173" -ForegroundColor Green
