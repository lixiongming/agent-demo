# ============================================
# Docker 配置
# Python 版本: 3.12.10
# ============================================

# 基础镜像 - 使用 slim 版本（最小化）
FROM python:3.12-slim AS base

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# ============================================
# 构建阶段 - 安装依赖
# ============================================
FROM base AS builder

# 复制 pip 配置文件（使用国内镜像）
COPY docker/pip.conf /root/.pip/pip.conf

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖（使用国内镜像加速）
RUN pip install --no-cache-dir -r requirements.txt

# ============================================
# 运行阶段 - 最终镜像
# ============================================
FROM base AS runner

# 从构建阶段复制依赖
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制应用代码
COPY app ./app
COPY main.py .
COPY run_server.py .
COPY scripts ./scripts
COPY data ./data

# 创建必要目录
RUN mkdir -p logs

# 暴露端口
EXPOSE 8888

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8888", "--workers", "1"]