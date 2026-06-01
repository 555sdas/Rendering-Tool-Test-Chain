# XR Test Platform - 数据库备份脚本 (Windows)
# 用法: .\scripts\backup.ps1

param(
    [string]$OutputDir = "backups"
)

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupFile = "$OutputDir/xr_test_db_$timestamp.sql"

Write-Host "🗄️  XR Test Platform 数据库备份" -ForegroundColor Cyan
Write-Host "==============================" -ForegroundColor Cyan
Write-Host ""

# 创建备份目录
if (!(Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir | Out-Null
}

# 执行备份
Write-Host "📦 正在备份数据库..." -ForegroundColor Yellow
docker exec xr-postgres pg_dump -U xruser -d xr_test_db > $backupFile

if ($LASTEXITCODE -eq 0) {
    $size = (Get-Item $backupFile).Length / 1KB
    Write-Host "✅ 备份完成!" -ForegroundColor Green
    Write-Host "   文件: $backupFile" -ForegroundColor Gray
    Write-Host "   大小: $([math]::Round($size, 2)) KB" -ForegroundColor Gray
} else {
    Write-Host "❌ 备份失败" -ForegroundColor Red
}
