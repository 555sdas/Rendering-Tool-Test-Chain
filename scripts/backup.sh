#!/bin/bash
# XR Test Platform - 数据库备份脚本 (Linux/macOS)
# 用法: ./scripts/backup.sh

OUTPUT_DIR="${1:-backups}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$OUTPUT_DIR/xr_test_db_$TIMESTAMP.sql"

echo -e "\033[36m🗄️  XR Test Platform 数据库备份\033[0m"
echo -e "\033[36m==============================\033[0m"
echo ""

# 创建备份目录
mkdir -p "$OUTPUT_DIR"

# 执行备份
echo -e "\033[33m📦 正在备份数据库...\033[0m"
docker exec xr-postgres pg_dump -U xruser -d xr_test_db > "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo -e "\033[32m✅ 备份完成!\033[0m"
    echo -e "\033[90m   文件: $BACKUP_FILE\033[0m"
    echo -e "\033[90m   大小: $SIZE\033[0m"
else
    echo -e "\033[31m❌ 备份失败\033[0m"
fi
