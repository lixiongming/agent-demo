#!/bin/bash
# ============================================
# 自动备份验证脚本
# ============================================

echo "======================================"
echo "自动备份功能验证"
echo "======================================"
echo ""

# 1. 检查备份容器状态
echo "1️⃣ 检查备份容器状态"
echo "--------------------------------------"
if docker ps | grep -q "agent-demo-backup"; then
    echo "✅ 备份容器正在运行"
    docker ps | grep "agent-demo-backup"
else
    echo "❌ 备份容器未运行"
    echo "请先启动服务: ./docker/start.sh start"
fi
echo ""

# 2. 检查 cron 配置
echo "2️⃣ 检查定时任务配置"
echo "--------------------------------------"
if docker ps | grep -q "agent-demo-backup"; then
    echo "容器内的 cron 配置:"
    docker exec agent-demo-backup-1 crontab -l 2>/dev/null || echo "❌ 无法获取 cron 配置"
else
    echo "❌ 备份容器未运行，无法检查 cron"
fi
echo ""

# 3. 检查备份日志
echo "3️⃣ 检查备份日志"
echo "--------------------------------------"
if [ -f "logs/backup.log" ]; then
    echo "最近的备份日志:"
    tail -20 logs/backup.log
else
    echo "❌ 备份日志文件不存在: logs/backup.log"
    echo "可能还没有执行过备份"
fi
echo ""

# 4. 检查备份文件
echo "4️⃣ 检查备份文件"
echo "--------------------------------------"
if [ -d "data/backups" ]; then
    backup_count=$(ls -1 data/backups/*.sql.gz 2>/dev/null | wc -l)
    if [ "$backup_count" -gt 0 ]; then
        echo "✅ 找到 $backup_count 个备份文件:"
        ls -lh data/backups/*.sql.gz | tail -5
    else
        echo "❌ 没有找到备份文件"
        echo "备份文件应该存储在: data/backups/"
    fi
else
    echo "❌ 备份目录不存在: data/backups/"
fi
echo ""

# 5. 手动触发备份测试
echo "5️⃣ 手动触发备份测试"
echo "--------------------------------------"
echo "是否要手动触发一次备份测试？(y/n)"
read -r confirm
if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
    echo "正在手动触发备份..."
    ./docker/start.sh backup

    echo ""
    echo "等待 5 秒后检查备份结果..."
    sleep 5

    if [ -f "logs/backup.log" ]; then
        echo "最新的备份日志:"
        tail -10 logs/backup.log
    fi

    backup_count=$(ls -1 data/backups/*.sql.gz 2>/dev/null | wc -l)
    if [ "$backup_count" -gt 0 ]; then
        echo ""
        echo "✅ 备份成功！找到 $backup_count 个备份文件"
        ls -lht data/backups/*.sql.gz | head -1
    fi
fi

echo ""
echo "======================================"
echo "验证完成"
echo "======================================"
echo ""
echo "💡 提示:"
echo "1. 自动备份时间: 每天凌晨 2:00"
echo "2. 备份日志位置: logs/backup.log"
echo "3. 备份文件位置: data/backups/"
echo "4. 手动备份命令: ./docker/start.sh backup"
echo ""