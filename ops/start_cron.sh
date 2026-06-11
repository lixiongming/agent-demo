#!/bin/bash
# ============================================
# 启动 cron 服务
# ============================================

set -e

# 创建日志文件（如果不存在）
touch /app/logs/backup.log

# 启动 cron
echo "启动 MySQL 定时备份服务..."
cron

# 保持容器运行
tail -f /app/logs/backup.log