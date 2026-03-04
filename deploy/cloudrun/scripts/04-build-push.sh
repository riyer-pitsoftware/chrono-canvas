#!/usr/bin/env bash
# Step 4: Build Docker images and push to Artifact Registry.
#
# Must be run from the chrono-canvas repo root.
#
# Usage:
#   cd /path/to/chrono-canvas
#   source deploy/cloudrun/scripts/00-env.sh
#   bash deploy/cloudrun/scripts/04-build-push.sh
set -euo pipefail
source "$(dirname "$0")/00-env.sh"

# Authenticate Docker with Artifact Registry
echo "=== Configuring Docker for Artifact Registry ==="
gcloud auth configure-docker "${GCP_REGION}-docker.pkg.dev" --quiet

# ── Build API image (also used for worker) ────────────────────────────
echo "=== Building API image ==="
docker build \
  -f deploy/cloudrun/Dockerfile.api \
  -t "${IMAGE_BASE}/api:${DEPLOY_TAG}" \
  -t "${IMAGE_BASE}/api:latest" \
  .

echo "=== Pushing API image ==="
docker push "${IMAGE_BASE}/api:${DEPLOY_TAG}"
docker push "${IMAGE_BASE}/api:latest"

# ── Build Frontend image ─────────────────────────────────────────────
echo "=== Building Frontend image ==="
docker build \
  -f deploy/cloudrun/Dockerfile.frontend \
  -t "${IMAGE_BASE}/frontend:${DEPLOY_TAG}" \
  -t "${IMAGE_BASE}/frontend:latest" \
  .

echo "=== Pushing Frontend image ==="
docker push "${IMAGE_BASE}/frontend:${DEPLOY_TAG}"
docker push "${IMAGE_BASE}/frontend:latest"

echo ""
echo "============================================================"
echo "  Images built and pushed!"
echo "============================================================"
echo "  API:      ${IMAGE_BASE}/api:${DEPLOY_TAG}"
echo "  Frontend: ${IMAGE_BASE}/frontend:${DEPLOY_TAG}"
echo ""
echo "  Next: bash deploy/cloudrun/scripts/05-deploy-services.sh"
