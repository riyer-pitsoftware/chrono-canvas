#!/usr/bin/env bash
set -euo pipefail

# ── Wait for dependencies ────────────────────────────────────────────
echo "⏳ Waiting for PostgreSQL..."
/app/docker/wait-for-it.sh "${DB_HOST:-db}" "${DB_PORT:-5432}" 30

echo "⏳ Waiting for Redis..."
/app/docker/wait-for-it.sh "${REDIS_HOST:-redis}" "${REDIS_PORT:-6379}" 30

echo "✅ Dependencies are ready"

# ── Run migrations (api only) ────────────────────────────────────────
if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
    echo "🔄 Running Alembic migrations..."
    alembic upgrade head
    echo "✅ Migrations complete"
fi

# ── Hand off to the actual process ───────────────────────────────────
exec "$@"
