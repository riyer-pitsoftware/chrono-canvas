#!/usr/bin/env bash
# Step 4: Build Docker images and push to Artifact Registry.
#
# Uses buildx to cross-compile for linux/amd64 (Cloud Run)
# from Apple Silicon or any other architecture.
#
# Must be run from the chrono-canvas repo root.
#
# Usage:
#   cd /path/to/chrono-canvas
#   source deploy/cloudrun/scripts/00-env.sh
#   bash deploy/cloudrun/scripts/04-build-push.sh
set -euo pipefail
source "$(dirname "$0")/00-env.sh"

# Build vendor wheels (neo-modules etc.)
echo "=== Building vendor wheels ==="
bash "$(git rev-parse --show-toplevel)/scripts/build-vendor-wheels.sh"

# Authenticate Docker with Artifact Registry
echo "=== Configuring Docker for Artifact Registry ==="
gcloud auth configure-docker "${GCP_REGION}-docker.pkg.dev" --quiet

# Use the default buildx builder (shares Docker daemon's network and credentials)
docker buildx use default 2>/dev/null || true

# ── Build & push API image (also used for worker) ──────────────────────
echo "=== Building & pushing API image ==="
docker buildx build \
  --platform linux/amd64 \
  -f deploy/cloudrun/Dockerfile.api \
  -t "${IMAGE_BASE}/api:${DEPLOY_TAG}" \
  -t "${IMAGE_BASE}/api:latest" \
  --push \
  .

# ── Build & push Frontend image ───────────────────────────────────────
echo "=== Building & pushing Frontend image ==="
docker buildx build \
  --platform linux/amd64 \
  -f deploy/cloudrun/Dockerfile.frontend \
  -t "${IMAGE_BASE}/frontend:${DEPLOY_TAG}" \
  -t "${IMAGE_BASE}/frontend:latest" \
  --push \
  .

# Persist tag for subsequent deploy steps
STATE_FILE="$(cd "$(dirname "$0")/.." && pwd)/.deploy-state"
echo "$DEPLOY_TAG" > "$STATE_FILE"
echo "  Tag persisted to ${STATE_FILE}"

echo ""
echo "============================================================"
echo "  Images built and pushed!"
echo "============================================================"
echo "  API:      ${IMAGE_BASE}/api:${DEPLOY_TAG}"
echo "  Frontend: ${IMAGE_BASE}/frontend:${DEPLOY_TAG}"
echo ""
echo "  Next: bash deploy/cloudrun/scripts/05-deploy-services.sh"
