#!/usr/bin/env bash
set -euo pipefail

# Cloud Run entrypoint — no wait-for-it needed.
# Cloud SQL Auth Proxy and VPC connector handle connectivity.

# Inject DATABASE_PASSWORD into DATABASE_URL if both are set.
# Cloud Run injects secrets as env vars; the URL template has no password.
if [ -n "${DATABASE_PASSWORD:-}" ] && [ -n "${DATABASE_URL:-}" ]; then
    export DATABASE_URL="${DATABASE_URL/chronocanvas@/chronocanvas:${DATABASE_PASSWORD}@}"
fi

if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
    echo "🔄 Running Alembic migrations..."
    alembic upgrade head
    echo "✅ Migrations complete"
fi

exec "$@"
