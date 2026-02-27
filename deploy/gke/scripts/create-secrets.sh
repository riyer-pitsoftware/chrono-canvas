#!/usr/bin/env bash
# Create K8s secrets from environment variables or a .env file.
#
# Usage:
#   # Option 1: Set env vars, then run
#   export DB_PASSWORD=mypassword
#   export ANTHROPIC_API_KEY=sk-ant-...
#   bash deploy/gke/scripts/create-secrets.sh
#
#   # Option 2: Source a .env file first
#   source .env.gke
#   bash deploy/gke/scripts/create-secrets.sh
set -euo pipefail

NAMESPACE="chronocanvas"

DB_PASSWORD="${DB_PASSWORD:?Set DB_PASSWORD}"
ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}"
OPENAI_API_KEY="${OPENAI_API_KEY:-}"
SERPAPI_KEY="${SERPAPI_KEY:-}"
APP_SECRET_KEY="${APP_SECRET_KEY:-$(openssl rand -hex 32)}"

DATABASE_URL="postgresql+asyncpg://chronocanvas:${DB_PASSWORD}@postgres:5432/chronocanvas"
REDIS_URL="redis://redis:6379/0"

echo "=== Creating K8s secret: chronocanvas-secrets ==="

kubectl create secret generic chronocanvas-secrets \
  --namespace="${NAMESPACE}" \
  --from-literal="DATABASE_URL=${DATABASE_URL}" \
  --from-literal="REDIS_URL=${REDIS_URL}" \
  --from-literal="ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}" \
  --from-literal="OPENAI_API_KEY=${OPENAI_API_KEY}" \
  --from-literal="SERPAPI_KEY=${SERPAPI_KEY}" \
  --from-literal="SECRET_KEY=${APP_SECRET_KEY}" \
  --from-literal="POSTGRES_PASSWORD=${DB_PASSWORD}" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "=== Secret created/updated ==="
