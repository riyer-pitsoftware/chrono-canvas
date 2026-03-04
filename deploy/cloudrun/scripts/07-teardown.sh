#!/usr/bin/env bash
# Tear down Cloud Run services and infrastructure to stop billing.
#
# Usage:
#   source deploy/cloudrun/scripts/00-env.sh
#   bash deploy/cloudrun/scripts/07-teardown.sh
#
# Pass --all to also delete Cloud SQL, Redis, and secrets.
set -euo pipefail
source "$(dirname "$0")/00-env.sh"

echo "=== Deleting Cloud Run services ==="
for SVC in chronocanvas-api chronocanvas-worker chronocanvas-frontend; do
  gcloud run services delete "${SVC}" \
    --region="${GCP_REGION}" --project="${GCP_PROJECT_ID}" --quiet 2>/dev/null \
    && echo "  Deleted ${SVC}" \
    || echo "  ${SVC} (not found)"
done

if [ "${1:-}" = "--all" ]; then
  echo ""
  echo "=== Deleting infrastructure ==="

  echo "  Deleting Cloud SQL: ${DB_INSTANCE}"
  gcloud sql instances delete "${DB_INSTANCE}" \
    --project="${GCP_PROJECT_ID}" --quiet 2>/dev/null || echo "  (not found)"

  echo "  Deleting Redis: ${REDIS_INSTANCE}"
  gcloud redis instances delete "${REDIS_INSTANCE}" \
    --region="${GCP_REGION}" --project="${GCP_PROJECT_ID}" --quiet 2>/dev/null || echo "  (not found)"

  echo "  Deleting VPC connector: ${VPC_CONNECTOR}"
  gcloud compute networks vpc-access connectors delete "${VPC_CONNECTOR}" \
    --region="${GCP_REGION}" --project="${GCP_PROJECT_ID}" --quiet 2>/dev/null || echo "  (not found)"

  echo "  Deleting Artifact Registry: ${AR_REPO}"
  gcloud artifacts repositories delete "${AR_REPO}" \
    --location="${GCP_REGION}" --project="${GCP_PROJECT_ID}" --quiet 2>/dev/null || echo "  (not found)"

  for SECRET in chronocanvas-db-password chronocanvas-secret-key chronocanvas-google-api-key chronocanvas-anthropic-api-key; do
    gcloud secrets delete "${SECRET}" \
      --project="${GCP_PROJECT_ID}" --quiet 2>/dev/null || true
  done
  echo "  Secrets deleted"
fi

echo ""
echo "✅ Teardown complete."
echo "   Run with --all to also delete Cloud SQL, Redis, VPC, AR, and secrets."
