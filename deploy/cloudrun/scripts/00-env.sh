#!/usr/bin/env bash
# Shared environment for all Cloud Run deployment scripts.
# Source this file before running any other script:
#   source deploy/cloudrun/scripts/00-env.sh
set -euo pipefail

# ── Required ──────────────────────────────────────────────────────────
export GCP_PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID in .env or shell}"
export GCP_REGION="${GCP_REGION:-us-central1}"

# ── Resource names ────────────────────────────────────────────────────
export AR_REPO="chronocanvas"
export SA_NAME="chronocanvas-run"
export DB_INSTANCE="chronocanvas-db"
export DB_NAME="chronocanvas"
export DB_USER="chronocanvas"
export REDIS_INSTANCE="chronocanvas-redis"
export VPC_CONNECTOR="chronocanvas-vpc"
export IMAGE_BASE="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${AR_REPO}"
export SA_EMAIL="${SA_NAME}@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
# Tag resolution: explicit env > state file > git HEAD
STATE_FILE="$(cd "$(dirname "$0")/.." && pwd)/.deploy-state"
if [ -n "${DEPLOY_TAG:-}" ]; then
  # Explicit override — use as-is
  :
elif [ -f "$STATE_FILE" ]; then
  export DEPLOY_TAG="$(cat "$STATE_FILE")"
else
  export DEPLOY_TAG="$(git rev-parse --short HEAD 2>/dev/null || echo latest)"
fi
# Persist for subsequent steps
echo "$DEPLOY_TAG" > "$STATE_FILE"

echo "╔══════════════════════════════════════════════════════╗"
echo "║  ChronoCanvas Cloud Run Deploy                      ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║  Project:  ${GCP_PROJECT_ID}"
echo "║  Region:   ${GCP_REGION}"
echo "║  Tag:      ${DEPLOY_TAG}"
echo "╚══════════════════════════════════════════════════════╝"
