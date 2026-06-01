#!/bin/bash
# XR Test Platform - 数据库恢复脚本 (Linux/macOS)
# 用法: ./scripts/restore.sh backups/xr_test_db_20260527_120000.sql

set -e

BACKUP_FILE="$1"

echo -e "\033[36m🗄️  XR Test Platform 数据库恢复\033[0m"
echo -e "\033[36m==============================\033[0m"
echo ""

if [ -z "$BACKUP_FILE" ]; then
    echo -e "\033[31m❌ 请指定备份文件路径\033[0m"
    echo -e "\033[90m   用法: ./scripts/restore.sh <备份文件>\033[0m"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo -e "\033[31m❌ 备份文件不存在: $BACKUP_FILE\033[0m"
    exit 1
fi

echo -e "\033[33m⚠️  这将覆盖现有数据库，是否继续?\033[0m"
read -p "输入 'yes' 确认: " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "\033[90m已取消恢复操作\033[0m"
    exit 0
fi

# 恢复数据库
echo -e "\033[33m📦 正在恢复数据库...\033[0m"
cat "$BACKUP_FILE" | docker exec -i xr-postgres psql -U xruser -d xr_test_db

echo -e "\033[32m✅ 恢复完成!\033[0m"
