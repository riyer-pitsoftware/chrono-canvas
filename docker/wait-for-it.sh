#!/usr/bin/env bash
# wait-for-it.sh — wait for a TCP host:port to become available
set -euo pipefail

HOST="$1"
PORT="$2"
TIMEOUT="${3:-30}"

elapsed=0
until nc -z "$HOST" "$PORT" 2>/dev/null; do
    if [ "$elapsed" -ge "$TIMEOUT" ]; then
        echo "❌ Timed out waiting for ${HOST}:${PORT} after ${TIMEOUT}s"
        exit 1
    fi
    sleep 1
    elapsed=$((elapsed + 1))
done

echo "  ✔ ${HOST}:${PORT} is available (${elapsed}s)"
