.PHONY: dev start up down stop restart build seed test lint migrate \
       frontend backend cli clean check-env \
       logs logs-api logs-worker logs-frontend \
       status shell-api db-shell fresh health \
       quickstart smoke-test

COMPOSE_DEV = docker compose -f docker-compose.dev.yml
API_CONTAINER = chrono-canvas-api-1

# ── Quickstart (one command, cold start) ─────────────────────────────
quickstart:
	@bash scripts/quickstart.sh

smoke-test:
	@bash scripts/smoke-test.sh

# ── Development ──────────────────────────────────────────────────────
dev: up
	@echo "ChronoCanvas running at http://localhost:3000"

start: dev

up:
	$(COMPOSE_DEV) up --build -d

down:
	$(COMPOSE_DEV) down

stop: down

restart: down up

build:
	docker compose build

# ── Logs & Status ────────────────────────────────────────────────────
logs:
	$(COMPOSE_DEV) logs -f --tail=100

logs-api:
	$(COMPOSE_DEV) logs -f --tail=100 api

logs-worker:
	$(COMPOSE_DEV) logs -f --tail=100 worker

logs-frontend:
	$(COMPOSE_DEV) logs -f --tail=100 frontend

status:
	$(COMPOSE_DEV) ps

# ── Shell Access ─────────────────────────────────────────────────────
shell-api:
	docker exec -it $(API_CONTAINER) bash

db-shell:
	docker exec -it chrono-canvas-db-1 psql -U chronocanvas -d chronocanvas

# ── Database ─────────────────────────────────────────────────────────
migrate:
	docker exec $(API_CONTAINER) alembic upgrade head

migrate-local:
	cd backend && alembic upgrade head

migration:
	cd backend && alembic revision --autogenerate -m "$(msg)"

# ── Seed data ────────────────────────────────────────────────────────
seed:
	docker cp seed/. $(API_CONTAINER):/app/seed/
	docker exec \
		-e DATABASE_URL="postgresql+asyncpg://chronocanvas:chronocanvas@db:5432/chronocanvas" \
		-e REDIS_URL="redis://redis:6379/0" \
		-e PYTHONPATH=/app/src \
		$(API_CONTAINER) python /app/seed/load_seed.py

seed-local:
	cd backend && python -m chronocanvas.seed.load_seed

# ── Testing ──────────────────────────────────────────────────────────
test:
	cd backend && pytest -v
	cd cli && pytest -v

test-backend:
	cd backend && pytest -v

test-cli:
	cd cli && pytest -v

# ── Config drift check ──────────────────────────────────────────────
check-env:
	python scripts/check_env_keys.py

# ── Linting ──────────────────────────────────────────────────────────
lint:
	cd backend && ruff check src/ tests/
	cd frontend && npm run lint

format:
	cd backend && ruff format src/ tests/

# ── Frontend ─────────────────────────────────────────────────────────
frontend:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build

# ── Backend (local dev) ──────────────────────────────────────────────
backend:
	cd backend && uvicorn chronocanvas.main:app --reload --host 0.0.0.0 --port 8000

# ── CLI ──────────────────────────────────────────────────────────────
cli:
	cd cli && pip install -e .

# ── Health Check ─────────────────────────────────────────────────────
health:
	@echo "API:"
	@curl -sf http://localhost:8000/api/health && echo " ✔ API healthy" || echo " ✘ API unreachable"
	@echo "Frontend:"
	@curl -sf http://localhost:3000 > /dev/null && echo " ✔ Frontend healthy" || echo " ✘ Frontend unreachable"

# ── Full Reset ───────────────────────────────────────────────────────
fresh: clean up
	@echo "Waiting for services to be ready..."
	@sleep 5
	@$(MAKE) seed
	@echo "Fresh environment ready at http://localhost:3000"

# ── Clean ────────────────────────────────────────────────────────────
clean:
	$(COMPOSE_DEV) down -v
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf backend/dist cli/dist frontend/dist
