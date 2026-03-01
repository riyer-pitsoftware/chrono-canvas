#!/usr/bin/env bash
# quickstart.sh — One-command cold start for ChronoCanvas
# Usage: bash scripts/quickstart.sh
set -euo pipefail

COMPOSE="docker compose -f docker-compose.dev.yml"
API_CONTAINER="chrono-canvas-api-1"
MAX_WAIT=120

# ── Colors ────────────────────────────────────────────────────────────
bold()  { printf "\033[1m%s\033[0m\n" "$*"; }
green() { printf "\033[32m%s\033[0m\n" "$*"; }
red()   { printf "\033[31m%s\033[0m\n" "$*"; }
dim()   { printf "\033[2m%s\033[0m\n" "$*"; }

# ── Preflight checks ─────────────────────────────────────────────────
bold "ChronoCanvas — Quickstart"
echo ""

if ! command -v docker &>/dev/null; then
    red "Error: Docker is not installed. Install it from https://docs.docker.com/get-docker/"
    exit 1
fi

if ! docker info &>/dev/null 2>&1; then
    red "Error: Docker daemon is not running. Start Docker Desktop and try again."
    exit 1
fi

if ! docker compose version &>/dev/null 2>&1; then
    red "Error: Docker Compose v2 is required. Update Docker Desktop or install the compose plugin."
    exit 1
fi

# ── Environment file ─────────────────────────────────────────────────
if [ ! -f .env ]; then
    echo "Creating .env from .env.example (safe defaults — no API keys needed)..."
    cp .env.example .env
    green "  .env created"
else
    dim "  .env already exists, keeping it"
fi

# ── Build and start ──────────────────────────────────────────────────
bold "Starting services..."
$COMPOSE up --build -d

# ── Wait for API health ──────────────────────────────────────────────
echo ""
echo "Waiting for API to be ready (up to ${MAX_WAIT}s)..."
elapsed=0
until curl -sf http://localhost:8000/api/health >/dev/null 2>&1; do
    if [ "$elapsed" -ge "$MAX_WAIT" ]; then
        red "Timed out waiting for API. Check logs with: make logs-api"
        exit 1
    fi
    sleep 2
    elapsed=$((elapsed + 2))
    printf "."
done
echo ""
green "  API healthy (${elapsed}s)"

# ── Seed data ─────────────────────────────────────────────────────────
bold "Loading seed data..."
docker cp seed/. "$API_CONTAINER":/app/seed/
docker exec \
    -e DATABASE_URL="postgresql+asyncpg://chronocanvas:chronocanvas@db:5432/chronocanvas" \
    -e REDIS_URL="redis://redis:6379/0" \
    -e PYTHONPATH=/app/src \
    "$API_CONTAINER" python /app/seed/load_seed.py

green "  Seed data loaded"

# ── Verify frontend ──────────────────────────────────────────────────
echo ""
echo "Waiting for frontend..."
elapsed=0
until curl -sf http://localhost:3000 >/dev/null 2>&1; do
    if [ "$elapsed" -ge 60 ]; then
        red "Frontend not responding. Check logs with: make logs-frontend"
        exit 1
    fi
    sleep 2
    elapsed=$((elapsed + 2))
done
green "  Frontend healthy"

# ── Done ──────────────────────────────────────────────────────────────
echo ""
green "============================================"
green "  ChronoCanvas is running!"
green "============================================"
echo ""
echo "  UI:   http://localhost:3000"
echo "  API:  http://localhost:8000/api/health"
echo "  Docs: http://localhost:8000/docs"
echo ""
dim "Useful commands:"
dim "  make logs        — stream all service logs"
dim "  make status      — show running containers"
dim "  make health      — quick health check"
dim "  make down        — stop all services"
echo ""
