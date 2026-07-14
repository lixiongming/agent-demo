#!/bin/bash
# ============================================
# 生产部署脚本 - 零缓存更新
# 用法:
#   ./deploy.sh          # 正常部署（增量构建）
#   ./deploy.sh full     # 全量重建（清除缓存）
#   ./deploy.sh rollback # 回滚到上一版本
# ============================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo "${GREEN}[INFO]${NC} $1"; }
warn()  { echo "${YELLOW}[WARN]${NC} $1"; }
error() { echo "${RED}[ERROR]${NC} $1"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$SCRIPT_DIR/docker compose.yml"

# 拉取最新代码
git_pull() {
    info "拉取最新代码..."
    cd "$PROJECT_DIR"
    git pull origin main || warn "Git pull 失败，使用本地代码"
}

# 健康检查
health_check() {
    info "等待服务启动..."
    local max_wait=60
    local waited=0

    while [ $waited -lt $max_wait ]; do
        if curl -sf http://localhost:8888/api/v1/health/ready > /dev/null 2>&1; then
            info "服务健康检查通过"
            return 0
        fi
        sleep 3
        waited=$((waited + 3))
        echo -n "."
    done

    error "服务启动超时（${max_wait}s），请检查日志: docker compose logs api"
}

# 正常部署（增量）
deploy() {
    info "=== 开始部署 ==="
    git_pull

    cd "$SCRIPT_DIR"

    # 构建并启动（只重建有变化的层）
    info "构建镜像..."
    docker compose build api

    info "重启服务..."
    docker compose up -d --no-deps api

    health_check

    info "=== 部署完成 ==="
    docker compose ps
}

# 全量部署（零缓存）
deploy_full() {
    info "=== 全量重建（零缓存）==="
    git_pull

    cd "$SCRIPT_DIR"

    # 停止旧服务
    info "停止旧服务..."
    docker compose down

    # 无缓存构建
    info "清除缓存并重新构建..."
    docker compose build --no-cache api

    # 启动所有服务
    info "启动所有服务..."
    docker compose up -d

    health_check

    info "=== 全量部署完成 ==="
    docker compose ps
}

# 回滚
rollback() {
    info "=== 回滚到上一版本 ==="

    cd "$PROJECT_DIR"

    # Git 回退
    info "回退代码..."
    git log --oneline -3
    ROLLBACK_COMMIT=$(git log --oneline -2 | tail -1 | awk '{print $1}')

    if [ -z "$ROLLBACK_COMMIT" ]; then
        error "没有可回滚的版本"
    fi

    read -p "确认回滚到 $ROLLBACK_COMMIT ? (y/N): " confirm
    if [ "$confirm" != "y" ]; then
        info "取消回滚"
        exit 0
    fi

    git checkout "$ROLLBACK_COMMIT"

    cd "$SCRIPT_DIR"

    # 重建并启动
    info "重建旧版本镜像..."
    docker compose build --no-cache api
    docker compose up -d --no-deps api

    health_check

    warn "当前处于 detached HEAD 状态，确认无误后请: git checkout main"
    info "=== 回滚完成 ==="
}

case "$1" in
    full)
        deploy_full
        ;;
    rollback)
        rollback
        ;;
    *)
        deploy
        ;;
esac
