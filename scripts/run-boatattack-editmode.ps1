param(
    [string]$UnityExe = "E:\unity_install\2022.3.62f3\Editor\Unity.exe",
    [string]$BoatAttackProject = "",
    [string]$ResultsPath = "",
    [string]$LogPath = ""
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
if (!$BoatAttackProject) {
    $BoatAttackProject = "D:\intellij" + [string][char]0x9879 + [string][char]0x76EE + "\BoatAttack"
}
if (!$ResultsPath) {
    $ResultsPath = Join-Path $Root "boatattack-editmode-results.xml"
}
if (!$LogPath) {
    $LogPath = Join-Path $Root "boatattack-editmode.log"
}

if (!(Test-Path -LiteralPath $UnityExe)) {
    Write-Error "Unity executable not found: $UnityExe"
}
if (!(Test-Path -LiteralPath $BoatAttackProject)) {
    Write-Error "BoatAttack project not found: $BoatAttackProject"
}

$args = @(
    "-batchmode",
    "-nographics",
    "-projectPath", $BoatAttackProject,
    "-runTests",
    "-testPlatform", "EditMode",
    "-testResults", $ResultsPath,
    "-logFile", $LogPath
)

Write-Host "Running BoatAttack EditMode tests..." -ForegroundColor Cyan
$process = Start-Process -FilePath $UnityExe -ArgumentList $args -Wait -PassThru
if ($process.ExitCode -ne 0) {
    Write-Error "Unity exited with code $($process.ExitCode). See log: $LogPath"
}
if (!(Test-Path -LiteralPath $ResultsPath)) {
    Write-Error "Unity did not produce test results: $ResultsPath"
}

Write-Host "BoatAttack EditMode results: $ResultsPath" -ForegroundColor Green
Write-Host "Unity log: $LogPath" -ForegroundColor Green
