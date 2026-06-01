# XR Test Platform - Windows 快速设置脚本
# 用法: .\scripts\setup.ps1

Write-Host "🚀 XR Test Platform 快速设置" -ForegroundColor Cyan
Write-Host "==============================" -ForegroundColor Cyan
Write-Host ""

# 检查 Docker
Write-Host "📦 检查 Docker..." -ForegroundColor Yellow
$dockerVersion = docker --version 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker 未安装或未启动" -ForegroundColor Red
    Write-Host "   请访问 https://docs.docker.com/get-docker/ 安装 Docker Desktop" -ForegroundColor Gray
    exit 1
}
Write-Host "✅ Docker 已安装: $dockerVersion" -ForegroundColor Green
Write-Host ""

# 检查 Docker Compose
Write-Host "📦 检查 Docker Compose..." -ForegroundColor Yellow
$composeVersion = docker compose version 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker Compose 未安装" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Docker Compose 已安装" -ForegroundColor Green
Write-Host ""

# 设置环境变量
Write-Host "⚙️  设置环境变量..." -ForegroundColor Yellow
$env:POSTGRES_USER = "xruser"
$env:POSTGRES_PASSWORD = "xrpass"
$env:POSTGRES_DB = "xr_test_db"
$env:SECRET_KEY = "your-secret-key-change-in-production"
Write-Host "✅ 环境变量已设置" -ForegroundColor Green
Write-Host ""

# 创建必要的目录
Write-Host "📁 创建必要的目录..." -ForegroundColor Yellow
$dirs = @("uploads", "backups", "nginx")
foreach ($dir in $dirs) {
    if (!(Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir | Out-Null
        Write-Host "  创建: $dir" -ForegroundColor Gray
    }
}
Write-Host "✅ 目录已创建" -ForegroundColor Green
Write-Host ""

# 启动服务
Write-Host "🚀 启动服务..." -ForegroundColor Yellow
Write-Host "   这可能需要几分钟时间..." -ForegroundColor Gray
docker compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 启动服务失败" -ForegroundColor Red
    exit 1
}
Write-Host "✅ 服务已启动" -ForegroundColor Green
Write-Host ""

# 等待数据库就绪
Write-Host "⏳ 等待数据库就绪..." -ForegroundColor Yellow
Start-Sleep -Seconds 5
$retryCount = 0
$maxRetries = 10
while ($retryCount -lt $maxRetries) {
    $result = docker exec xr-postgres pg_isready -U xruser 2>$null
    if ($LASTEXITCODE -eq 0) {
        break
    }
    Write-Host "  重试中... ($retryCount/$maxRetries)" -ForegroundColor Gray
    Start-Sleep -Seconds 2
    $retryCount++
}
Write-Host "✅ 数据库已就绪" -ForegroundColor Green
Write-Host ""

# 初始化数据库表
Write-Host "🗄️  初始化数据库表..." -ForegroundColor Yellow
docker compose exec -T backend python -c "from app.database import init_db; init_db()" 2>$null
Write-Host "✅ 数据库表已创建" -ForegroundColor Green
Write-Host ""

# 显示访问信息
Write-Host "🎉 设置完成！" -ForegroundColor Cyan
Write-Host "==============================" -ForegroundColor Cyan
Write-Host ""
Write-Host "🌐 访问地址:" -ForegroundColor Yellow
Write-Host "   前端: http://localhost" -ForegroundColor Green
Write-Host "   API文档: http://localhost/api/v1/docs" -ForegroundColor Green
Write-Host "   健康检查: http://localhost/health" -ForegroundColor Green
Write-Host ""
Write-Host "🔧 管理命令:" -ForegroundColor Yellow
Write-Host "   查看日志: docker compose logs -f" -ForegroundColor Gray
Write-Host "   停止服务: docker compose down" -ForegroundColor Gray
Write-Host "   重启服务: docker compose restart" -ForegroundColor Gray
Write-Host ""
Write-Host "📖 更多信息请参考 docs/ 目录下的文档" -ForegroundColor Cyan
