#!/usr/bin/env bash
# Step 5: Deploy Cloud Run services (API, Worker, Frontend).
#
# Prerequisites:
#   - Infrastructure created (step 02)
#   - Secrets populated (step 03)
#   - Images built and pushed (step 04)
#
# Usage:
#   source deploy/cloudrun/scripts/00-env.sh
#   bash deploy/cloudrun/scripts/05-deploy-services.sh
set -euo pipefail
source "$(dirname "$0")/00-env.sh"

# ── Verify images exist ──────────────────────────────────────────────
echo "=== Verifying images exist for tag: ${DEPLOY_TAG} ==="
for svc in api frontend; do
  if ! gcloud artifacts docker images describe "${IMAGE_BASE}/${svc}:${DEPLOY_TAG}" \
       --project="${GCP_PROJECT_ID}" &>/dev/null; then
    echo "ERROR: Image ${IMAGE_BASE}/${svc}:${DEPLOY_TAG} not found in Artifact Registry."
    echo "Did you build with a different tag? Current HEAD is $(git rev-parse --short HEAD)."
    echo "Fix: re-run step 04, or use --tag=<correct-tag>"
    exit 1
  fi
done
echo "  Images verified for tag: ${DEPLOY_TAG}"
echo ""

# ── Resolve infrastructure details ────────────────────────────────────
DB_CONNECTION_NAME=$(gcloud sql instances describe "${DB_INSTANCE}" \
  --project="${GCP_PROJECT_ID}" \
  --format="value(connectionName)")

REDIS_HOST=$(gcloud redis instances describe "${REDIS_INSTANCE}" \
  --region="${GCP_REGION}" --project="${GCP_PROJECT_ID}" \
  --format="value(host)")
REDIS_PORT=$(gcloud redis instances describe "${REDIS_INSTANCE}" \
  --region="${GCP_REGION}" --project="${GCP_PROJECT_ID}" \
  --format="value(port)")

echo "  Cloud SQL: ${DB_CONNECTION_NAME}"
echo "  Redis:     ${REDIS_HOST}:${REDIS_PORT}"
echo ""

# ── Common env vars for API and Worker ────────────────────────────────
# Cloud SQL Auth Proxy provides a Unix socket at /cloudsql/<connection-name>
COMMON_ENV="\
DATABASE_URL=postgresql+asyncpg://chronocanvas@/chronocanvas?host=/cloudsql/${DB_CONNECTION_NAME},\
REDIS_URL=redis://${REDIS_HOST}:${REDIS_PORT}/0,\
DEPLOYMENT_MODE=gcp,\
IMAGE_PROVIDER=imagen,\
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
LOG_LEVEL=INFO,\
HACKATHON_MODE=true,\
HACKATHON_STRICT_GEMINI=true,\
ENABLE_ADMIN_API=true,\
ENABLE_AUDIT_UI=true,\
ENABLE_FACE_UPLOAD=false,\
LOG_FORMAT=json"

COMMON_SECRETS="\
GOOGLE_API_KEY=chronocanvas-google-api-key:latest,\
ANTHROPIC_API_KEY=chronocanvas-anthropic-api-key:latest,\
SECRET_KEY=chronocanvas-secret-key:latest,\
DATABASE_PASSWORD=chronocanvas-db-password:latest,\
ADMIN_API_KEY=chronocanvas-admin-api-key:latest"

# ── Deploy API ────────────────────────────────────────────────────────
echo "=== Deploying API service ==="
gcloud run deploy chronocanvas-api \
  --image="${IMAGE_BASE}/api:${DEPLOY_TAG}" \
  --region="${GCP_REGION}" \
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
  --set-env-vars="${COMMON_ENV},RUN_MIGRATIONS=true,CORS_ORIGINS=[\"*\"]" \
  --set-secrets="${COMMON_SECRETS}" \
  --project="${GCP_PROJECT_ID}"

API_URL=$(gcloud run services describe chronocanvas-api \
  --region="${GCP_REGION}" --project="${GCP_PROJECT_ID}" \
  --format="value(status.url)")
echo "  API URL: ${API_URL}"

# ── Deploy Worker ─────────────────────────────────────────────────────
echo "=== Deploying Worker service ==="
gcloud run deploy chronocanvas-worker \
  --image="${IMAGE_BASE}/api:${DEPLOY_TAG}" \
  --region="${GCP_REGION}" \
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
  --command="/app/entrypoint.sh" \
  --args="python,-m,chronocanvas.worker_main" \
  --port=8080 \
  --set-env-vars="${COMMON_ENV},RUN_MIGRATIONS=false" \
  --set-secrets="${COMMON_SECRETS}" \
  --project="${GCP_PROJECT_ID}"

# ── Deploy Frontend ──────────────────────────────────────────────────
echo "=== Deploying Frontend service ==="
gcloud run deploy chronocanvas-frontend \
  --image="${IMAGE_BASE}/frontend:${DEPLOY_TAG}" \
  --region="${GCP_REGION}" \
  --platform=managed \
  --port=8080 \
  --cpu=1 \
  --memory=256Mi \
  --min-instances=0 \
  --max-instances=4 \
  --concurrency=100 \
  --allow-unauthenticated \
  --set-env-vars="API_URL=${API_URL}" \
  --project="${GCP_PROJECT_ID}"

FRONTEND_URL=$(gcloud run services describe chronocanvas-frontend \
  --region="${GCP_REGION}" --project="${GCP_PROJECT_ID}" \
  --format="value(status.url)")

echo ""
echo "============================================================"
echo "  Cloud Run deployment complete!"
echo "============================================================"
echo ""
echo "  API:      ${API_URL}"
echo "  Frontend: ${FRONTEND_URL}"
echo ""
echo "  Next: bash deploy/cloudrun/scripts/06-verify.sh"
