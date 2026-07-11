#!/bin/bash
# ============================================
# MySQL 数据库恢复脚本
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
            [[ "$key" =~ ^#.*$ ]] && continue
            [[ -z "$key" ]] && continue
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

# 显示帮助信息
show_help() {
    echo "用法: $0 [备份文件]"
    echo ""
    echo "示例:"
    echo "  $0                                    # 交互式选择备份文件"
    echo "  $0 agent_db_20260610_120000.sql.gz   # 恢复指定备份文件"
    echo ""
    echo "可用备份文件:"
    if [ -d "${BACKUP_DIR}" ]; then
        ls -lht "${BACKUP_DIR}"/*.sql.gz 2>/dev/null | head -10
    else
        echo "  无备份文件"
    fi
}

# 检查备份目录
if [ ! -d "${BACKUP_DIR}" ]; then
    error "备份目录不存在: ${BACKUP_DIR}"
fi

# 获取备份文件
if [ -z "$1" ]; then
    # 交互式选择
    echo "可用备份文件:"
    echo ""

    files=($(ls -t "${BACKUP_DIR}"/*.sql.gz 2>/dev/null))

    if [ ${#files[@]} -eq 0 ]; then
        error "没有找到备份文件"
    fi

    PS3="请选择要恢复的备份文件 (输入编号): "
    select file in "${files[@]}" "取消"; do
        if [ "$file" = "取消" ]; then
            echo "已取消"
            exit 0
        elif [ -n "$file" ]; then
            BACKUP_FILE="$file"
            break
        else
            echo "无效选择，请重试"
        fi
    done
else
    BACKUP_FILE="$1"

    # 检查文件是否存在
    if [ ! -f "${BACKUP_FILE}" ]; then
        # 尝试在备份目录中查找
        if [ -f "${BACKUP_DIR}/${BACKUP_FILE}" ]; then
            BACKUP_FILE="${BACKUP_DIR}/${BACKUP_FILE}"
        else
            error "备份文件不存在: ${BACKUP_FILE}"
        fi
    fi
fi

info "准备恢复数据库..."
info "备份文件: ${BACKUP_FILE}"
info "目标数据库: ${DB_NAME}"
info "主机: ${DB_HOST}:${DB_PORT}"

# 确认操作
read -p "$(echo -e ${RED}警告: 此操作将覆盖现有数据，是否继续? [y/N]:${NC} )" confirm
if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "已取消"
    exit 0
fi

# 解压备份文件
TEMP_SQL="/tmp/restore_${DB_NAME}_$(date +%s).sql"

if [[ "${BACKUP_FILE}" == *.gz ]]; then
    info "解压备份文件..."
    gunzip -c "${BACKUP_FILE}" > "${TEMP_SQL}"
else
    TEMP_SQL="${BACKUP_FILE}"
fi

# 检查是否在 Docker 环境中
if command -v docker &> /dev/null && docker ps | grep -q mysql; then
    info "检测到 Docker MySQL 容器"

    CONTAINER_ID=$(docker ps | grep mysql | awk '{print $1}')
    info "容器 ID: ${CONTAINER_ID}"

    # 将 SQL 文件复制到容器中
    info "复制 SQL 文件到容器..."
    docker cp "${TEMP_SQL}" "${CONTAINER_ID}:/tmp/restore.sql"

    # 执行恢复（使用容器内的文件，避免 stdin 重定向问题）
    info "恢复数据库..."
    docker exec -e MYSQL_PWD="${DB_PASSWORD}" "${CONTAINER_ID}" mysql \
        -h"${DB_HOST}" \
        -P"${DB_PORT}" \
        -u"${DB_USER}" \
        "${DB_NAME}" -e "source /tmp/restore.sql"

    # 清理容器中的临时文件
    docker exec "${CONTAINER_ID}" rm -f /tmp/restore.sql

else
    info "使用本地 mysql 客户端"

    # 检查 mysql 是否存在
    if ! command -v mysql &> /dev/null; then
        error "mysql 客户端未安装，请先安装 MySQL 客户端工具"
    fi

    # 执行恢复（使用 MYSQL_PWD 环境变量避免密码暴露在进程参数中）
    info "恢复数据库..."
    MYSQL_PWD="${DB_PASSWORD}" mysql \
        -h"${DB_HOST}" \
        -P"${DB_PORT}" \
        -u"${DB_USER}" \
        "${DB_NAME}" < "${TEMP_SQL}"
fi

# 清理临时文件
if [ "${TEMP_SQL}" != "${BACKUP_FILE}" ] && [ -f "${TEMP_SQL}" ]; then
    rm -f "${TEMP_SQL}"
fi

info "数据库恢复成功!"
info "请验证数据完整性"