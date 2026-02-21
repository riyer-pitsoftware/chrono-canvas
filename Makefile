.PHONY: dev up down build seed test lint migrate frontend backend cli clean

# Development
dev: up
	@echo "ChronoCanvas running at http://localhost:3000"

up:
	docker compose -f docker-compose.dev.yml up --build -d

down:
	docker compose -f docker-compose.dev.yml down

build:
	docker compose build

# Database
migrate:
	cd backend && alembic upgrade head

migration:
	cd backend && alembic revision --autogenerate -m "$(msg)"

# Seed data
seed:
	cd backend && python -m chronocanvas.seed.load_seed

# Testing
test:
	cd backend && pytest -v
	cd cli && pytest -v

test-backend:
	cd backend && pytest -v

test-cli:
	cd cli && pytest -v

# Linting
lint:
	cd backend && ruff check src/ tests/
	cd frontend && npm run lint

format:
	cd backend && ruff format src/ tests/

# Frontend
frontend:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build

# Backend (local dev)
backend:
	cd backend && uvicorn chronocanvas.main:app --reload --host 0.0.0.0 --port 8000

# CLI
cli:
	cd cli && pip install -e .

# Clean
clean:
	docker compose -f docker-compose.dev.yml down -v
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf backend/dist cli/dist frontend/dist
