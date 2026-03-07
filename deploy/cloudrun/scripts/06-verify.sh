#!/usr/bin/env bash
# Step 6: Verify the deployment is healthy.
#
# Usage:
#   source deploy/cloudrun/scripts/00-env.sh
#   bash deploy/cloudrun/scripts/06-verify.sh
set -euo pipefail
source "$(dirname "$0")/00-env.sh"

echo "=== Checking Cloud Run services ==="

API_URL=$(gcloud run services describe chronocanvas-api \
  --region="${GCP_REGION}" --project="${GCP_PROJECT_ID}" \
  --format="value(status.url)" 2>/dev/null || echo "NOT_DEPLOYED")

FRONTEND_URL=$(gcloud run services describe chronocanvas-frontend \
  --region="${GCP_REGION}" --project="${GCP_PROJECT_ID}" \
  --format="value(status.url)" 2>/dev/null || echo "NOT_DEPLOYED")

WORKER_STATUS=$(gcloud run services describe chronocanvas-worker \
  --region="${GCP_REGION}" --project="${GCP_PROJECT_ID}" \
  --format="value(status.conditions[0].status)" 2>/dev/null || echo "NOT_DEPLOYED")

echo "  API:      ${API_URL}"
echo "  Frontend: ${FRONTEND_URL}"
echo "  Worker:   ${WORKER_STATUS}"
echo ""

# ── Health check ──────────────────────────────────────────────────────
if [ "${API_URL}" != "NOT_DEPLOYED" ]; then
  echo "=== API Health Check ==="
  HTTP_CODE=$(curl -s -o /tmp/health_response.json -w "%{http_code}" "${API_URL}/api/health" 2>/dev/null || echo "000")
  if [ "${HTTP_CODE}" = "200" ]; then
    echo "  ✅ API is healthy (HTTP 200)"
    cat /tmp/health_response.json | python3 -m json.tool 2>/dev/null || cat /tmp/health_response.json

    # Verify deployment_mode is set correctly for GCP
    DEPLOY_MODE=$(python3 -c "import json; print(json.load(open('/tmp/health_response.json')).get('deployment_mode',''))" 2>/dev/null || echo "")
    if [ "${DEPLOY_MODE}" = "gcp" ]; then
      echo "  ✅ deployment_mode=gcp (cloud providers enforced)"
    else
      echo "  ❌ deployment_mode='${DEPLOY_MODE}' — expected 'gcp'. Local providers may be accessible!"
      echo "     Fix: ensure DEPLOYMENT_MODE=gcp is set in Cloud Run env vars."
      exit 1
    fi
  else
    echo "  ❌ API returned HTTP ${HTTP_CODE}"
    cat /tmp/health_response.json 2>/dev/null || true
  fi
  echo ""

  echo "=== Frontend Check ==="
  FE_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${FRONTEND_URL}/" 2>/dev/null || echo "000")
  if [ "${FE_CODE}" = "200" ]; then
    echo "  ✅ Frontend is serving (HTTP 200)"
  else
    echo "  ❌ Frontend returned HTTP ${FE_CODE}"
  fi
else
  echo "  ⚠️  API not deployed yet — skipping health checks"
fi

echo ""
echo "=== Cloud Run Console ==="
echo "  https://console.cloud.google.com/run?project=${GCP_PROJECT_ID}"
echo ""
echo "  📸 Take a screenshot of the console for Devpost proof!"
