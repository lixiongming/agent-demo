.PHONY: help install run test clean docker-build docker-run

help:
	@echo "Available commands:"
	@echo "  make install      - Install dependencies"
	@echo "  make run          - Run development server"
	@echo "  make test         - Run tests"
	@echo "  make clean        - Clean up"
	@echo "  make docker-build - Build Docker image"
	@echo "  make docker-run   - Run Docker container"
	@echo "  make migrate      - Run database migrations"
	@echo "  make init-db      - Initialize database"

install:
	pip install -r requirements.txt

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8888

test:
	pytest tests/ -v --cov=app

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage htmlcov

docker-build:
	docker build -t agent-service:latest -f docker/Dockerfile .

docker-run:
	docker-compose -f docker/docker-compose.yml up -d

migrate:
	alembic upgrade head

init-db:
	python scripts/init_db.py

seed:
	python scripts/seed_data.py

format:
	black app/ tests/
	isort app/ tests/

lint:
	flake8 app/ tests/
	mypy app/