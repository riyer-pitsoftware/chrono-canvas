#!/usr/bin/env bash
# Step 2: Create GCP infrastructure.
# Creates: Artifact Registry, Cloud SQL, Memorystore Redis,
#          VPC connector, service account with IAM roles.
#
# Safe to re-run — skips resources that already exist.
#
# Usage:
#   source deploy/cloudrun/scripts/00-env.sh
#   bash deploy/cloudrun/scripts/02-create-infra.sh
set -euo pipefail
source "$(dirname "$0")/00-env.sh"

# ── Artifact Registry ────────────────────────────────────────────────
echo "=== Creating Artifact Registry: ${AR_REPO} ==="
gcloud artifacts repositories create "${AR_REPO}" \
  --repository-format=docker \
  --location="${GCP_REGION}" \
  --description="ChronoCanvas container images" \
  --project="${GCP_PROJECT_ID}" \
  2>/dev/null || echo "  (already exists)"

# ── Cloud SQL (public IP — Cloud Run uses built-in Auth Proxy) ───────
echo "=== Creating Cloud SQL: ${DB_INSTANCE} ==="
if gcloud sql instances describe "${DB_INSTANCE}" --project="${GCP_PROJECT_ID}" &>/dev/null; then
  echo "  (already exists)"
else
  DB_PASSWORD="$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 24)"
  echo ""
  echo "  ╔═══════════════════════════════════════════════╗"
  echo "  ║  SAVE THIS — DB password: ${DB_PASSWORD}  ║"
  echo "  ╚═══════════════════════════════════════════════╝"
  echo ""

  gcloud sql instances create "${DB_INSTANCE}" \
    --database-version=POSTGRES_16 \
    --edition=ENTERPRISE \
    --tier=db-f1-micro \
    --region="${GCP_REGION}" \
    --storage-auto-increase \
    --storage-size=10 \
    --assign-ip \
    --project="${GCP_PROJECT_ID}"

  gcloud sql databases create "${DB_NAME}" \
    --instance="${DB_INSTANCE}" \
    --project="${GCP_PROJECT_ID}"

  gcloud sql users create "${DB_USER}" \
    --instance="${DB_INSTANCE}" \
    --password="${DB_PASSWORD}" \
    --project="${GCP_PROJECT_ID}"

  # Store password in Secret Manager
  echo -n "${DB_PASSWORD}" | gcloud secrets create "chronocanvas-db-password" \
    --data-file=- \
    --project="${GCP_PROJECT_ID}"
  echo "  DB password stored in Secret Manager: chronocanvas-db-password"
else
  # DB already exists — ensure the password secret exists too
  if ! gcloud secrets describe "chronocanvas-db-password" --project="${GCP_PROJECT_ID}" &>/dev/null; then
    echo "  ⚠️  Cloud SQL exists but chronocanvas-db-password secret is missing."
    echo "  Creating placeholder — you MUST set the real password:"
    echo ""
    echo -n "REPLACE_ME" | gcloud secrets create "chronocanvas-db-password" \
      --data-file=- \
      --project="${GCP_PROJECT_ID}"
    echo "  echo -n 'YOUR_DB_PASSWORD' | \\"
    echo "    gcloud secrets versions add chronocanvas-db-password --data-file=-"
    echo ""
  fi
fi

DB_CONNECTION_NAME=$(gcloud sql instances describe "${DB_INSTANCE}" \
  --project="${GCP_PROJECT_ID}" \
  --format="value(connectionName)")
echo "  Connection name: ${DB_CONNECTION_NAME}"

# ── Memorystore Redis ────────────────────────────────────────────────
echo "=== Creating Memorystore Redis: ${REDIS_INSTANCE} ==="
if gcloud redis instances describe "${REDIS_INSTANCE}" \
    --region="${GCP_REGION}" --project="${GCP_PROJECT_ID}" &>/dev/null; then
  echo "  (already exists)"
else
  gcloud redis instances create "${REDIS_INSTANCE}" \
    --region="${GCP_REGION}" \
    --size=1 \
    --tier=basic \
    --redis-version=redis_7_0 \
    --project="${GCP_PROJECT_ID}"
fi

REDIS_HOST=$(gcloud redis instances describe "${REDIS_INSTANCE}" \
  --region="${GCP_REGION}" --project="${GCP_PROJECT_ID}" \
  --format="value(host)")
REDIS_PORT=$(gcloud redis instances describe "${REDIS_INSTANCE}" \
  --region="${GCP_REGION}" --project="${GCP_PROJECT_ID}" \
  --format="value(port)")
echo "  Redis: ${REDIS_HOST}:${REDIS_PORT}"

# ── VPC Connector (Cloud Run → Redis) ────────────────────────────────
echo "=== Creating VPC connector: ${VPC_CONNECTOR} ==="
gcloud compute networks vpc-access connectors create "${VPC_CONNECTOR}" \
  --region="${GCP_REGION}" \
  --range="10.8.0.0/28" \
  --min-instances=2 \
  --max-instances=3 \
  --project="${GCP_PROJECT_ID}" \
  2>/dev/null || echo "  (already exists)"

# ── Service Account ──────────────────────────────────────────────────
echo "=== Creating service account: ${SA_NAME} ==="
gcloud iam service-accounts create "${SA_NAME}" \
  --display-name="ChronoCanvas Cloud Run SA" \
  --project="${GCP_PROJECT_ID}" \
  2>/dev/null || echo "  (already exists)"

for ROLE in \
  roles/cloudsql.client \
  roles/secretmanager.secretAccessor \
  roles/storage.objectAdmin \
  roles/logging.logWriter \
  roles/monitoring.metricWriter; do
  gcloud projects add-iam-policy-binding "${GCP_PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${ROLE}" \
    --quiet > /dev/null
done
echo "  IAM roles granted"

# ── Summary ──────────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo "  Infrastructure created!"
echo "============================================================"
echo "  Artifact Registry: ${IMAGE_BASE}"
echo "  Cloud SQL:         ${DB_CONNECTION_NAME}"
echo "  Redis:             ${REDIS_HOST}:${REDIS_PORT}"
echo "  VPC Connector:     ${VPC_CONNECTOR}"
echo "  Service Account:   ${SA_EMAIL}"
echo ""
echo "  Next: bash deploy/cloudrun/scripts/03-setup-secrets.sh"
