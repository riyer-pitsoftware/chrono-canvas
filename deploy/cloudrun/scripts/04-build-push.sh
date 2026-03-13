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

# Ensure we're at repo root (Dockerfiles use paths relative to it)
cd "$(git rev-parse --show-toplevel)"

# Build vendor wheels (neo-modules etc.)
echo "=== Building vendor wheels ==="
bash "$(git rev-parse --show-toplevel)/scripts/build-vendor-wheels.sh"

# Authenticate Docker with Artifact Registry
echo "=== Configuring Docker for Artifact Registry ==="
gcloud auth configure-docker "${GCP_REGION}-docker.pkg.dev" --quiet

# Use the default buildx builder (shares Docker daemon's network and credentials)
docker buildx use default 2>/dev/null || true

# Build labels from git state
GIT_SHA="$(git rev-parse HEAD)"
GIT_SHORT="$(git rev-parse --short HEAD)"
GIT_MSG="$(git log -1 --format='%s' HEAD)"
BUILD_TIME="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
GIT_DIRTY="$(git diff --quiet && git diff --cached --quiet && echo 'false' || echo 'true')"

LABEL_ARGS=(
  --label "org.opencontainers.image.revision=${GIT_SHA}"
  --label "org.opencontainers.image.created=${BUILD_TIME}"
  --label "org.opencontainers.image.source=$(git remote get-url origin 2>/dev/null || echo 'local')"
  --label "com.chronocanvas.git.short=${GIT_SHORT}"
  --label "com.chronocanvas.git.message=${GIT_MSG}"
  --label "com.chronocanvas.git.dirty=${GIT_DIRTY}"
  --label "com.chronocanvas.deploy.tag=${DEPLOY_TAG}"
)

# ── Build & push API image (also used for worker) ──────────────────────
echo "=== Building & pushing API image ==="
docker buildx build \
  --platform linux/amd64 \
  -f deploy/cloudrun/Dockerfile.api \
  -t "${IMAGE_BASE}/api:${DEPLOY_TAG}" \
  -t "${IMAGE_BASE}/api:latest" \
  "${LABEL_ARGS[@]}" \
  --push \
  .

# ── Build & push Frontend image ───────────────────────────────────────
echo "=== Building & pushing Frontend image ==="
docker buildx build \
  --platform linux/amd64 \
  -f deploy/cloudrun/Dockerfile.frontend \
  -t "${IMAGE_BASE}/frontend:${DEPLOY_TAG}" \
  -t "${IMAGE_BASE}/frontend:latest" \
  "${LABEL_ARGS[@]}" \
  --push \
  .

# ── Fetch and record image digests ────────────────────────────────────
echo "=== Fetching image digests ==="
API_DIGEST="$(gcloud artifacts docker images describe \
  "${IMAGE_BASE}/api:${DEPLOY_TAG}" \
  --format='value(image_summary.digest)' 2>/dev/null || echo 'unknown')"
FE_DIGEST="$(gcloud artifacts docker images describe \
  "${IMAGE_BASE}/frontend:${DEPLOY_TAG}" \
  --format='value(image_summary.digest)' 2>/dev/null || echo 'unknown')"

# Persist tag for subsequent deploy steps
STATE_FILE="$(cd "$(dirname "$0")/.." && pwd)/.deploy-state"
echo "$DEPLOY_TAG" > "$STATE_FILE"
echo "  Tag persisted to ${STATE_FILE}"

# Write build manifest for deploy-mark.sh to pick up
MANIFEST_FILE="$(cd "$(dirname "$0")/.." && pwd)/.build-manifest.json"
cat > "$MANIFEST_FILE" <<MANIFEST
{
  "deploy_tag": "${DEPLOY_TAG}",
  "git_sha": "${GIT_SHA}",
  "git_short": "${GIT_SHORT}",
  "git_message": "${GIT_MSG}",
  "git_dirty": ${GIT_DIRTY},
  "build_time": "${BUILD_TIME}",
  "images": {
    "api": {
      "image": "${IMAGE_BASE}/api:${DEPLOY_TAG}",
      "digest": "${API_DIGEST}"
    },
    "frontend": {
      "image": "${IMAGE_BASE}/frontend:${DEPLOY_TAG}",
      "digest": "${FE_DIGEST}"
    }
  }
}
MANIFEST
echo "  Build manifest written to ${MANIFEST_FILE}"

echo ""
echo "============================================================"
echo "  Images built and pushed!"
echo "============================================================"
echo "  API:      ${IMAGE_BASE}/api:${DEPLOY_TAG}"
echo "            digest: ${API_DIGEST}"
echo "  Frontend: ${IMAGE_BASE}/frontend:${DEPLOY_TAG}"
echo "            digest: ${FE_DIGEST}"
echo "  Commit:   ${GIT_SHORT} ${GIT_MSG}"
echo "  Dirty:    ${GIT_DIRTY}"
echo ""
echo "  Next: bash deploy/cloudrun/scripts/05-deploy-services.sh"
