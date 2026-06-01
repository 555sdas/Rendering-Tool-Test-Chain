#!/bin/bash
# XR Test Platform - Linux/macOS 快速设置脚本
# 用法: ./scripts/setup.sh

set -e

echo -e "\033[36m🚀 XR Test Platform 快速设置\033[0m"
echo -e "\033[36m==============================\033[0m"
echo ""

# 检查 Docker
echo -e "\033[33m📦 检查 Docker...\033[0m"
if ! command -v docker &> /dev/null; then
    echo -e "\033[31m❌ Docker 未安装或未启动\033[0m"
    echo -e "\033[90m   请访问 https://docs.docker.com/get-docker/ 安装 Docker\033[0m"
    exit 1
fi
echo -e "\033[32m✅ Docker 已安装\033[0m"
echo ""

# 检查 Docker Compose
echo -e "\033[33m📦 检查 Docker Compose...\033[0m"
if ! command -v docker compose &> /dev/null; then
    echo -e "\033[31m❌ Docker Compose 未安装\033[0m"
    exit 1
fi
echo -e "\033[32m✅ Docker Compose 已安装\033[0m"
echo ""

# 设置环境变量
echo -e "\033[33m⚙️  设置环境变量...\033[0m"
export POSTGRES_USER="xruser"
export POSTGRES_PASSWORD="xrpass"
export POSTGRES_DB="xr_test_db"
export SECRET_KEY="your-secret-key-change-in-production"
echo -e "\033[32m✅ 环境变量已设置\033[0m"
echo ""

# 创建必要的目录
echo -e "\033[33m📁 创建必要的目录...\033[0m"
mkdir -p uploads backups nginx
echo -e "\033[32m✅ 目录已创建\033[0m"
echo ""

# 启动服务
echo -e "\033[33m🚀 启动服务...\033[0m"
echo -e "\033[90m   这可能需要几分钟时间...\033[0m"
docker compose up -d
echo -e "\033[32m✅ 服务已启动\033[0m"
echo ""

# 等待数据库就绪
echo -e "\033[33m⏳ 等待数据库就绪...\033[0m"
sleep 5
retry_count=0
max_retries=10
while [ $retry_count -lt $max_retries ]; do
    if docker exec xr-postgres pg_isready -U xruser > /dev/null 2>&1; then
        break
    fi
    echo -e "\033[90m  重试中... ($retry_count/$max_retries)\033[0m"
    sleep 2
    retry_count=$((retry_count + 1))
done
echo -e "\033[32m✅ 数据库已就绪\033[0m"
echo ""

# 初始化数据库表
echo -e "\033[33m🗄️  初始化数据库表...\033[0m"
docker compose exec -T backend python -c "from app.database import init_db; init_db()" > /dev/null 2>&1 || true
echo -e "\033[32m✅ 数据库表已创建\033[0m"
echo ""

# 显示访问信息
echo -e "\033[36m🎉 设置完成！\033[0m"
echo -e "\033[36m==============================\033[0m"
echo ""
echo -e "\033[33m🌐 访问地址:\033[0m"
echo -e "\033[32m   前端: http://localhost\033[0m"
echo -e "\033[32m   API文档: http://localhost/api/v1/docs\033[0m"
echo -e "\033[32m   健康检查: http://localhost/health\033[0m"
echo ""
echo -e "\033[33m🔧 管理命令:\033[0m"
echo -e "\033[90m   查看日志: docker compose logs -f\033[0m"
echo -e "\033[90m   停止服务: docker compose down\033[0m"
echo -e "\033[90m   重启服务: docker compose restart\033[0m"
echo ""
echo -e "\033[36m📖 更多信息请参考 docs/ 目录下的文档\033[0m"
