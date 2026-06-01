# XR Test Platform - 数据库恢复脚本 (Windows)
# 用法: .\scripts\restore.ps1 -BackupFile backups/xr_test_db_20260527_120000.sql

param(
    [Parameter(Mandatory=$true)]
    [string]$BackupFile
)

Write-Host "🗄️  XR Test Platform 数据库恢复" -ForegroundColor Cyan
Write-Host "==============================" -ForegroundColor Cyan
Write-Host ""

if (!(Test-Path $BackupFile)) {
    Write-Host "❌ 备份文件不存在: $BackupFile" -ForegroundColor Red
    exit 1
}

Write-Host "⚠️  这将覆盖现有数据库，是否继续?" -ForegroundColor Yellow
$confirm = Read-Host "输入 'yes' 确认"

if ($confirm -ne "yes") {
    Write-Host "已取消恢复操作" -ForegroundColor Gray
    exit 0
}

# 恢复数据库
Write-Host "📦 正在恢复数据库..." -ForegroundColor Yellow
Get-Content $BackupFile | docker exec -i xr-postgres psql -U xruser -d xr_test_db

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ 恢复完成!" -ForegroundColor Green
} else {
    Write-Host "❌ 恢复失败" -ForegroundColor Red
}
