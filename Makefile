.PHONY: help install dev run test lint format clean docker-up docker-down migrate init-db seed backup restore deploy

# ============================================
# Default
# ============================================
help:
	@echo "Usage: make <command>"
	@echo ""
	@echo "Development:"
	@echo "  make install       Install production dependencies"
	@echo "  make dev           Install dev dependencies"
	@echo "  make run           Run dev server (hot reload)"
	@echo ""
	@echo "Quality:"
	@echo "  make lint          Run linter (ruff)"
	@echo "  make format        Format code (black + isort)"
	@echo "  make typecheck     Run type checker (mypy)"
	@echo "  make test          Run tests with coverage"
	@echo "  make test-unit     Run unit tests only"
	@echo "  make test-integ    Run integration tests only"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up     Start all services"
	@echo "  make docker-down   Stop all services"
	@echo "  make docker-build  Rebuild images"
	@echo "  make docker-logs   Tail API logs"
	@echo ""
	@echo "Database:"
	@echo "  make migrate       Run Alembic migrations"
	@echo "  make init-db       Initialize database schema"
	@echo "  make seed          Seed sample data"
	@echo ""
	@echo "Operations:"
	@echo "  make backup        Backup MySQL database"
	@echo "  make restore       Restore MySQL database"
	@echo "  make deploy        Production deploy (incremental)"
	@echo "  make deploy-full   Production deploy (full rebuild)"
	@echo "  make rollback      Rollback to previous version"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean         Remove build artifacts"
	@echo "  make check         Run all checks (lint + typecheck + test)"

# ============================================
# Development
# ============================================
install:
	pip install -r requirements.txt

dev:
	pip install -r requirements.txt -r requirements-dev.txt

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8888

# ============================================
# Quality
# ============================================
lint:
	ruff check app/ tests/

format:
	black app/ tests/
	isort app/ tests/

typecheck:
	mypy app/

test:
	pytest tests/ -v --cov=app --cov-report=term-missing

test-unit:
	pytest tests/unit/ -v

test-integ:
	pytest tests/integration/ -v

check: lint typecheck test

# ============================================
# Docker
# ============================================
docker-up:
	./scripts/start.sh start

docker-down:
	./scripts/start.sh stop

docker-build:
	./scripts/start.sh rebuild

docker-logs:
	./scripts/start.sh logs

# ============================================
# Database
# ============================================
migrate:
	alembic upgrade head

init-db:
	python scripts/init_db.py

seed:
	python scripts/seed_data.py

# ============================================
# Operations
# ============================================
backup:
	bash ops/backup_mysql.sh

restore:
	bash ops/restore_mysql.sh

deploy:
	bash docker/deploy.sh

deploy-full:
	bash docker/deploy.sh full

rollback:
	bash docker/deploy.sh rollback

# ============================================
# Maintenance
# ============================================
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .coverage htmlcov .mypy_cache
