#!/usr/bin/env bash
set -euo pipefail

# Cloud Run entrypoint — no wait-for-it needed.
# Cloud SQL Auth Proxy and VPC connector handle connectivity.

if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
    echo "🔄 Running Alembic migrations..."
    alembic upgrade head
    echo "✅ Migrations complete"
fi

exec "$@"
