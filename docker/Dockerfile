# ============================================
# Multi-stage Docker Build
# Python 3.12 | Production-grade
# ============================================

# ----- Base -----
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# ----- Builder: install dependencies -----
FROM base AS builder

COPY docker/pip.conf /root/.pip/pip.conf
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# ----- Runner: production image -----
FROM base AS runner

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

# Copy application code
COPY app/ /app/app/
COPY data/ /app/data/

# Create necessary directories
RUN mkdir -p logs data && chown -R appuser:appuser /app

USER appuser

EXPOSE 8888

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8888/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8888"]
