#!/bin/bash
# ============================================
# MySQL 数据库备份脚本
# ============================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 打印信息
info() {
    echo "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo "${RED}[ERROR]${NC} $1"
    exit 1
}

# 加载环境变量（安全方式：逐行读取，跳过注释和空行）
load_env() {
    local env_file=""
    if [ -f "../.env" ]; then
        env_file="../.env"
    elif [ -f ".env" ]; then
        env_file=".env"
    fi

    if [ -n "$env_file" ]; then
        while IFS='=' read -r key value; do
            # 跳过注释和空行
            [[ "$key" =~ ^#.*$ ]] && continue
            [[ -z "$key" ]] && continue
            # 去除首尾引号
            value="${value%\"}"
            value="${value#\"}"
            export "$key"="$value"
        done < "$env_file"
    fi
}

load_env

# 数据库配置
DB_HOST="${MYSQL_HOST:-localhost}"
DB_PORT="${MYSQL_PORT:-3306}"
DB_USER="${MYSQL_USER:-root}"
DB_PASSWORD="${MYSQL_PASSWORD:-123456}"
DB_NAME="${MYSQL_DATABASE:-agent_db}"

# 备份目录
BACKUP_DIR="../data/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_${DATE}.sql"

# 创建备份目录
mkdir -p "${BACKUP_DIR}"

info "开始备份 MySQL 数据库..."
info "数据库: ${DB_NAME}"
info "主机: ${DB_HOST}:${DB_PORT}"

# 检查是否在 Docker 环境中
if command -v docker &> /dev/null && docker ps | grep -q mysql; then
    info "检测到 Docker MySQL 容器"

    # 使用 Docker 容器内的 mysqldump
    CONTAINER_ID=$(docker ps | grep mysql | awk '{print $1}')

    info "容器 ID: ${CONTAINER_ID}"

    # 执行备份（使用 MYSQL_PWD 环境变量避免密码暴露在进程参数中）
    MYSQL_PWD="${DB_PASSWORD}" docker exec -e MYSQL_PWD="${DB_PASSWORD}" "${CONTAINER_ID}" mysqldump \
        -h"${DB_HOST}" \
        -P"${DB_PORT}" \
        -u"${DB_USER}" \
        --single-transaction \
        --routines \
        --triggers \
        --events \
        "${DB_NAME}" > "${BACKUP_FILE}"

else
    info "使用本地 mysqldump"

    # 检查 mysqldump 是否存在
    if ! command -v mysqldump &> /dev/null; then
        error "mysqldump 未安装，请先安装 MySQL 客户端工具"
    fi

    # 执行备份（使用 MYSQL_PWD 环境变量避免密码暴露在进程参数中）
    MYSQL_PWD="${DB_PASSWORD}" mysqldump \
        -h"${DB_HOST}" \
        -P"${DB_PORT}" \
        -u"${DB_USER}" \
        --skip-ssl \
        --single-transaction \
        --routines \
        --triggers \
        --events \
        "${DB_NAME}" > "${BACKUP_FILE}"
fi

# 检查备份是否成功
if [ -f "${BACKUP_FILE}" ] && [ -s "${BACKUP_FILE}" ]; then
    # 压缩备份文件
    gzip "${BACKUP_FILE}"

    BACKUP_SIZE=$(du -h "${BACKUP_FILE}.gz" | cut -f1)

    info "备份成功!"
    info "备份文件: ${BACKUP_FILE}.gz"
    info "文件大小: ${BACKUP_SIZE}"

    # 清理旧备份（保留最近 7 天）
    find "${BACKUP_DIR}" -name "*.sql.gz" -mtime +7 -delete
    info "已清理 7 天前的旧备份"

    # 显示备份列表
    echo ""
    info "当前备份文件列表:"
    ls -lh "${BACKUP_DIR}"/*.sql.gz 2>/dev/null | tail -5
else
    error "备份失败!"
fi