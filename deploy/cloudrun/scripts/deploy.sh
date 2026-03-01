#!/usr/bin/env bash
# Deploy ChronoCanvas to Cloud Run.
#
# Builds container images, pushes to Artifact Registry, and deploys
# three Cloud Run services: api, worker, frontend.
#
# Prerequisites:
#   - GCP setup completed (setup-gcp.sh)
#   - Secret Manager secrets populated with real values
#   - gcloud CLI authenticated
#
# Usage:
#   export GCP_PROJECT_ID=my-project
#   export GCP_REGION=us-central1
#   bash deploy/cloudrun/scripts/deploy.sh
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
REGION="${GCP_REGION:-us-central1}"
AR_REPO="chronocanvas"
SA_NAME="chronocanvas-run"
DB_INSTANCE="chronocanvas-db"
REDIS_INSTANCE="chronocanvas-redis"
VPC_CONNECTOR="chronocanvas-vpc"
TAG="${DEPLOY_TAG:-$(git rev-parse --short HEAD 2>/dev/null || echo latest)}"

IMAGE_BASE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "=== Deploying ChronoCanvas to Cloud Run ==="
echo "  Project:  ${PROJECT_ID}"
echo "  Region:   ${REGION}"
echo "  Tag:      ${TAG}"
echo ""

# ── Resolve infrastructure ──────────────────────────────────────────
DB_CONNECTION_NAME=$(gcloud sql instances describe "${DB_INSTANCE}" --format="value(connectionName)")
REDIS_HOST=$(gcloud redis instances describe "${REDIS_INSTANCE}" --region="${REGION}" --format="value(host)")
REDIS_PORT=$(gcloud redis instances describe "${REDIS_INSTANCE}" --region="${REGION}" --format="value(port)")

echo "  Cloud SQL: ${DB_CONNECTION_NAME}"
echo "  Redis:     ${REDIS_HOST}:${REDIS_PORT}"
echo ""

# ── Configure Docker for Artifact Registry ──────────────────────────
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# ── Build and push images ───────────────────────────────────────────
echo "=== Building API image ==="
docker build -f docker/Dockerfile.api -t "${IMAGE_BASE}/api:${TAG}" .
docker tag "${IMAGE_BASE}/api:${TAG}" "${IMAGE_BASE}/api:latest"
docker push "${IMAGE_BASE}/api:${TAG}"
docker push "${IMAGE_BASE}/api:latest"

echo "=== Building Frontend image ==="
docker build -f docker/Dockerfile.frontend -t "${IMAGE_BASE}/frontend:${TAG}" .
docker tag "${IMAGE_BASE}/frontend:${TAG}" "${IMAGE_BASE}/frontend:latest"
docker push "${IMAGE_BASE}/frontend:${TAG}"
docker push "${IMAGE_BASE}/frontend:latest"

# ── Common environment for API and Worker ───────────────────────────
# Cloud SQL connection uses Unix socket via Cloud SQL Auth Proxy (built into Cloud Run)
DB_URL="postgresql+asyncpg://chronocanvas:DB_PASSWORD_PLACEHOLDER@/chronocanvas?host=/cloudsql/${DB_CONNECTION_NAME}"

# ── Deploy API service ──────────────────────────────────────────────
echo "=== Deploying API service ==="
gcloud run deploy chronocanvas-api \
  --image="${IMAGE_BASE}/api:${TAG}" \
  --region="${REGION}" \
  --platform=managed \
  --service-account="${SA_EMAIL}" \
  --set-cloudsql-instances="${DB_CONNECTION_NAME}" \
  --vpc-connector="${VPC_CONNECTOR}" \
  --vpc-egress=private-ranges-only \
  --port=8000 \
  --cpu=2 \
  --memory=4Gi \
  --min-instances=1 \
  --max-instances=4 \
  --timeout=300 \
  --concurrency=40 \
  --allow-unauthenticated \
  --set-env-vars="\
DATABASE_URL=postgresql+asyncpg://chronocanvas@/chronocanvas?host=/cloudsql/${DB_CONNECTION_NAME},\
REDIS_URL=redis://${REDIS_HOST}:${REDIS_PORT}/0,\
IMAGE_PROVIDER=imagen,\
DEFAULT_LLM_PROVIDER=gemini,\
GEMINI_MODEL=gemini-2.5-flash,\
CLAUDE_MODEL=claude-sonnet-4-5-20250929,\
CONTENT_MODERATION_ENABLED=true,\
RESEARCH_CACHE_ENABLED=true,\
VALIDATION_RETRY_ENABLED=true,\
FACE_SEARCH_ENABLED=true,\
FACEFUSION_ENABLED=false,\
RATE_LIMIT_RPM=60,\
LLM_MAX_CONCURRENT=5,\
OUTPUT_DIR=/app/output,\
UPLOAD_DIR=/app/uploads,\
RUN_MIGRATIONS=true,\
LOG_LEVEL=INFO,\
CORS_ORIGINS=[\"*\"]" \
  --set-secrets="\
GOOGLE_API_KEY=chronocanvas-google-api-key:latest,\
ANTHROPIC_API_KEY=chronocanvas-anthropic-api-key:latest,\
SECRET_KEY=chronocanvas-secret-key:latest,\
DATABASE_PASSWORD=chronocanvas-db-password:latest"

# ── Deploy Worker service ───────────────────────────────────────────
echo "=== Deploying Worker service ==="
gcloud run deploy chronocanvas-worker \
  --image="${IMAGE_BASE}/api:${TAG}" \
  --region="${REGION}" \
  --platform=managed \
  --service-account="${SA_EMAIL}" \
  --set-cloudsql-instances="${DB_CONNECTION_NAME}" \
  --vpc-connector="${VPC_CONNECTOR}" \
  --vpc-egress=private-ranges-only \
  --cpu=2 \
  --memory=4Gi \
  --min-instances=1 \
  --max-instances=2 \
  --timeout=600 \
  --no-cpu-throttling \
  --no-allow-unauthenticated \
  --command="arq" \
  --args="chronocanvas.worker.WorkerSettings" \
  --set-env-vars="\
DATABASE_URL=postgresql+asyncpg://chronocanvas@/chronocanvas?host=/cloudsql/${DB_CONNECTION_NAME},\
REDIS_URL=redis://${REDIS_HOST}:${REDIS_PORT}/0,\
IMAGE_PROVIDER=imagen,\
DEFAULT_LLM_PROVIDER=gemini,\
GEMINI_MODEL=gemini-2.5-flash,\
CLAUDE_MODEL=claude-sonnet-4-5-20250929,\
CONTENT_MODERATION_ENABLED=true,\
RESEARCH_CACHE_ENABLED=true,\
VALIDATION_RETRY_ENABLED=true,\
FACE_SEARCH_ENABLED=true,\
FACEFUSION_ENABLED=false,\
OUTPUT_DIR=/app/output,\
UPLOAD_DIR=/app/uploads,\
RUN_MIGRATIONS=false,\
LOG_LEVEL=INFO" \
  --set-secrets="\
GOOGLE_API_KEY=chronocanvas-google-api-key:latest,\
ANTHROPIC_API_KEY=chronocanvas-anthropic-api-key:latest,\
SECRET_KEY=chronocanvas-secret-key:latest,\
DATABASE_PASSWORD=chronocanvas-db-password:latest"

# ── Deploy Frontend service ─────────────────────────────────────────
echo "=== Deploying Frontend service ==="
# Get the API URL to configure nginx proxy
API_URL=$(gcloud run services describe chronocanvas-api --region="${REGION}" --format="value(status.url)")

gcloud run deploy chronocanvas-frontend \
  --image="${IMAGE_BASE}/frontend:${TAG}" \
  --region="${REGION}" \
  --platform=managed \
  --port=8080 \
  --cpu=1 \
  --memory=256Mi \
  --min-instances=0 \
  --max-instances=4 \
  --concurrency=100 \
  --allow-unauthenticated \
  --set-env-vars="API_URL=${API_URL}"

# ── Summary ─────────────────────────────────────────────────────────
FRONTEND_URL=$(gcloud run services describe chronocanvas-frontend --region="${REGION}" --format="value(status.url)")
echo ""
echo "============================================================"
echo "  Cloud Run deployment complete!"
echo "============================================================"
echo ""
echo "  API:      ${API_URL}"
echo "  Frontend: ${FRONTEND_URL}"
echo ""
echo "  Test: curl ${API_URL}/api/health"
echo ""
echo "  Note: Frontend nginx proxy needs API_URL set. You may need"
echo "  to configure Cloud Run domain mapping or use a load balancer"
echo "  for production traffic routing."
