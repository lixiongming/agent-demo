#!/bin/bash
# ============================================
# Docker 一键启动脚本
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

# 检查 Docker
check_docker() {
    if ! command -v docker &> /dev/null; then
        error "Docker 未安装，请先安装 Docker"
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose 未安装，请先安装 Docker Compose"
    fi
    
    info "Docker 环境检查通过"
}

# 检查环境变量
check_env() {
    if [ ! -f ".env" ]; then
        warn ".env 文件不存在，从 .env.example 复制"
        cp .env.example .env
    fi
    
    # 检查 DASHSCOPE_API_KEY
    if grep -q "DASHSCOPE_API_KEY=your_api_key_here" .env; then
        warn "请修改 .env 文件中的 DASHSCOPE_API_KEY"
    fi
    
    info "环境变量检查完成"
}

# 启动服务
start() {
    info "启动 Docker 服务..."
    
    cd docker
    
    # 构建镜像
    info "构建镜像..."
    docker-compose build
    
    # 启动服务
    info "启动服务..."
    docker-compose up -d
    
    # 等待服务启动
    info "等待服务启动..."
    sleep 10
    
    # 检查服务状态
    docker-compose ps
    
    info "服务启动完成!"
    echo ""
    echo "============================================"
    echo "服务地址:"
    echo "  API:      http://localhost:8888"
    echo "  Qdrant:   http://localhost:6333"
    echo "  MySQL:    localhost:3306"
    echo "  Redis:    localhost:6379"
    echo "============================================"
    echo ""
    echo "查看日志: docker-compose logs -f api"
    echo "停止服务: docker-compose down"
}

# 停止服务
stop() {
    info "停止 Docker 服务..."
    cd docker
    docker-compose down
    info "服务已停止"
}

# 查看日志
logs() {
    cd docker
    docker-compose logs -f api
}

# 重建服务
rebuild() {
    info "重建 Docker 服务..."
    cd docker
    docker-compose down
    docker-compose build --no-cache
    docker-compose up -d
    info "重建完成"
}

# 导入知识库
import_knowledge() {
    info "导入 LOL 知识库到 Qdrant..."
    
    # 等待 Qdrant 启动
    sleep 5
    
    # 执行导入脚本
    docker-compose exec api python scripts/lol_knowledge_to_qdrant.py \
        "/app/data/lol_knowledge_base.md" \
        --host qdrant \
        --port 6333
    
    info "知识库导入完成"
}

# 备份 MySQL 数据库
backup_mysql() {
    info "备份 MySQL 数据库..."
    cd ..
    bash ops/backup_mysql.sh
    cd docker
}

# 恢复 MySQL 数据库
restore_mysql() {
    info "恢复 MySQL 数据库..."
    cd ..
    bash ops/restore_mysql.sh "$2"
    cd docker
}

# 帮助信息
help() {
    echo "用法: ./docker/start.sh [命令]"
    echo ""
    echo "命令:"
    echo "  start     启动所有服务"
    echo "  stop      停止所有服务"
    echo "  logs      查看 API 日志"
    echo "  rebuild   重建服务"
    echo "  import    导入知识库"
    echo "  backup    备份 MySQL 数据库"
    echo "  restore   恢复 MySQL 数据库 [备份文件]"
    echo "  help      显示帮助信息"
}

# 主函数
main() {
    case "$1" in
        start)
            check_docker
            check_env
            start
            ;;
        stop)
            stop
            ;;
        logs)
            logs
            ;;
        rebuild)
            rebuild
            ;;
        import)
            import_knowledge
            ;;
        backup)
            backup_mysql
            ;;
        restore)
            restore_mysql "$@"
            ;;
        help|--help|-h)
            help
            ;;
        *)
            error "未知命令: $1"
            help
            exit 1
            ;;
    esac
}

main "$@"