#!/usr/bin/env bash
# cc-remote-diag.sh — Remote diagnostics CLI for ChronoCanvas on GCP Cloud Run.
#
# Wraps curl calls to the admin diagnostic API.
# Config: reads CLOUD_RUN_URL and ADMIN_API_KEY from .env.remote (gitignored).
#
# Usage:
#   ./scripts/cc-remote-diag.sh failures              # Recent failures with error details
#   ./scripts/cc-remote-diag.sh imagen-errors          # Imagen-specific failure analysis
#   ./scripts/cc-remote-diag.sh health-deep            # Live deep health check (DB, Redis, Imagen)
#   ./scripts/cc-remote-diag.sh stats                  # Request counts by status
#   ./scripts/cc-remote-diag.sh show <request_id>      # Full audit detail for a request
#   ./scripts/cc-remote-diag.sh retry <request_id>     # Re-enqueue a failed request
#   ./scripts/cc-remote-diag.sh logs [--tail N]        # Cloud Run logs via gcloud
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="${PROJECT_DIR}/.env.remote"

# ── Load config ──────────────────────────────────────────────────────────────

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: ${ENV_FILE} not found."
  echo ""
  echo "Create it with:"
  echo "  CLOUD_RUN_URL=https://chronocanvas-api-XXXXXX-uc.a.run.app"
  echo "  ADMIN_API_KEY=your-admin-api-key"
  echo ""
  echo "Get the admin key from Secret Manager:"
  echo "  gcloud secrets versions access latest --secret=chronocanvas-admin-api-key"
  exit 1
fi

source "$ENV_FILE"

if [[ -z "${CLOUD_RUN_URL:-}" ]]; then
  echo "ERROR: CLOUD_RUN_URL not set in ${ENV_FILE}"
  exit 1
fi
if [[ -z "${ADMIN_API_KEY:-}" ]]; then
  echo "ERROR: ADMIN_API_KEY not set in ${ENV_FILE}"
  exit 1
fi

BASE_URL="${CLOUD_RUN_URL}/api/admin/diag"

# ── Helpers ──────────────────────────────────────────────────────────────────

api_get() {
  local path="$1"
  shift
  curl -sS -H "X-Admin-Key: ${ADMIN_API_KEY}" "${BASE_URL}${path}" "$@" | python3 -m json.tool
}

api_post() {
  local path="$1"
  shift
  curl -sS -X POST -H "X-Admin-Key: ${ADMIN_API_KEY}" "${BASE_URL}${path}" "$@" | python3 -m json.tool
}

# ── Commands ─────────────────────────────────────────────────────────────────

cmd_failures() {
  local hours="${1:-24}"
  echo "=== Recent failures (last ${hours}h) ==="
  api_get "/failures?hours=${hours}&limit=20"
}

cmd_imagen_errors() {
  local hours="${1:-24}"
  echo "=== Imagen errors (last ${hours}h) ==="
  api_get "/imagen-errors?hours=${hours}&limit=20"
}

cmd_health_deep() {
  echo "=== Deep health check ==="
  api_get "/health-deep"
}

cmd_stats() {
  echo "=== Request stats ==="
  api_get "/stats"
}

cmd_show() {
  local request_id="${1:?Usage: cc-remote-diag.sh show <request_id>}"
  echo "=== Request ${request_id} ==="
  api_get "/request/${request_id}"
}

cmd_retry() {
  local request_id="${1:?Usage: cc-remote-diag.sh retry <request_id> [from_step]}"
  local from_step="${2:-orchestrator}"
  echo "=== Retrying ${request_id} from ${from_step} ==="
  api_post "/retry/${request_id}?from_step=${from_step}"
}

cmd_logs() {
  local tail="${1:-50}"
  echo "=== Cloud Run logs (tail ${tail}) ==="
  gcloud run services logs read chronocanvas-api --limit="${tail}" --format=json 2>/dev/null \
    | python3 -m json.tool \
    || gcloud run services logs read chronocanvas-api --limit="${tail}" 2>/dev/null \
    || echo "Failed to fetch logs. Ensure gcloud is configured and you have permissions."
}

cmd_help() {
  echo "cc-remote-diag.sh — Remote diagnostics for ChronoCanvas on GCP"
  echo ""
  echo "Usage:"
  echo "  failures [hours]         Recent failures with error details (default: 24h)"
  echo "  imagen-errors [hours]    Imagen-specific failure analysis"
  echo "  health-deep              Live deep health check (DB, Redis, Imagen)"
  echo "  stats                    Request counts by status"
  echo "  show <request_id>        Full audit detail for a request"
  echo "  retry <id> [from_step]   Re-enqueue a failed request (default: orchestrator)"
  echo "  logs [tail_count]        Cloud Run logs via gcloud (default: 50)"
  echo ""
  echo "Config: ${ENV_FILE}"
}

# ── Dispatch ─────────────────────────────────────────────────────────────────

case "${1:-help}" in
  failures)       shift; cmd_failures "$@" ;;
  imagen-errors)  shift; cmd_imagen_errors "$@" ;;
  health-deep)    shift; cmd_health_deep "$@" ;;
  stats)          shift; cmd_stats "$@" ;;
  show)           shift; cmd_show "$@" ;;
  retry)          shift; cmd_retry "$@" ;;
  logs)           shift; cmd_logs "$@" ;;
  help|--help|-h) cmd_help ;;
  *)              echo "Unknown command: $1"; cmd_help; exit 1 ;;
esac
