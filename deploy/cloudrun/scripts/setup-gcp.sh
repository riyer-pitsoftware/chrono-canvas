#!/usr/bin/env bash
# One-time GCP project setup for ChronoCanvas Cloud Run deployment.
#
# Creates: Cloud SQL (PostgreSQL), Memorystore (Redis), Artifact Registry,
# Secret Manager secrets, VPC connector, and service account.
#
# Prerequisites:
#   - gcloud CLI authenticated (gcloud auth login)
#   - A GCP project with billing enabled
#
# Usage:
#   export GCP_PROJECT_ID=my-project
#   export GCP_REGION=us-central1
#   bash deploy/cloudrun/scripts/setup-gcp.sh
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
REGION="${GCP_REGION:-us-central1}"
AR_REPO="chronocanvas"
SA_NAME="chronocanvas-run"
DB_INSTANCE="chronocanvas-db"
DB_NAME="chronocanvas"
DB_USER="chronocanvas"
REDIS_INSTANCE="chronocanvas-redis"
VPC_CONNECTOR="chronocanvas-vpc"
GITHUB_REPO="${GITHUB_REPO:-}"

echo "=== Setting project: ${PROJECT_ID} ==="
gcloud config set project "${PROJECT_ID}"

# ── 1. Enable APIs ──────────────────────────────────────────────────
echo "=== Enabling APIs ==="
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  sqladmin.googleapis.com \
  redis.googleapis.com \
  secretmanager.googleapis.com \
  vpcaccess.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  compute.googleapis.com

# ── 2. Create Artifact Registry repository ──────────────────────────
echo "=== Creating Artifact Registry repo: ${AR_REPO} ==="
gcloud artifacts repositories create "${AR_REPO}" \
  --repository-format=docker \
  --location="${REGION}" \
  --description="ChronoCanvas container images" \
  2>/dev/null || echo "  (already exists)"

# ── 3. Create Cloud SQL instance (PostgreSQL 16) ───────────────────
echo "=== Creating Cloud SQL instance: ${DB_INSTANCE} ==="
if gcloud sql instances describe "${DB_INSTANCE}" &>/dev/null; then
  echo "  (already exists)"
else
  # Generate DB password
  DB_PASSWORD="$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 24)"
  echo "  Generated DB password (save this!): ${DB_PASSWORD}"

  gcloud sql instances create "${DB_INSTANCE}" \
    --database-version=POSTGRES_16 \
    --tier=db-f1-micro \
    --region="${REGION}" \
    --storage-auto-increase \
    --storage-size=10 \
    --no-assign-ip \
    --network=default \
    --enable-google-private-path

  gcloud sql databases create "${DB_NAME}" --instance="${DB_INSTANCE}"
  gcloud sql users create "${DB_USER}" --instance="${DB_INSTANCE}" --password="${DB_PASSWORD}"

  # Store DB password in Secret Manager
  echo -n "${DB_PASSWORD}" | gcloud secrets create "chronocanvas-db-password" --data-file=-
fi

# Get the Cloud SQL connection name
DB_CONNECTION_NAME=$(gcloud sql instances describe "${DB_INSTANCE}" --format="value(connectionName)")
echo "  Connection: ${DB_CONNECTION_NAME}"

# ── 4. Create Memorystore Redis instance ────────────────────────────
echo "=== Creating Memorystore Redis: ${REDIS_INSTANCE} ==="
if gcloud redis instances describe "${REDIS_INSTANCE}" --region="${REGION}" &>/dev/null; then
  echo "  (already exists)"
else
  gcloud redis instances create "${REDIS_INSTANCE}" \
    --region="${REGION}" \
    --size=1 \
    --tier=basic \
    --redis-version=redis_7_0
fi

REDIS_HOST=$(gcloud redis instances describe "${REDIS_INSTANCE}" --region="${REGION}" --format="value(host)")
REDIS_PORT=$(gcloud redis instances describe "${REDIS_INSTANCE}" --region="${REGION}" --format="value(port)")
echo "  Redis: ${REDIS_HOST}:${REDIS_PORT}"

# ── 5. Create VPC connector (Cloud Run → Cloud SQL / Redis) ────────
echo "=== Creating VPC connector: ${VPC_CONNECTOR} ==="
gcloud compute networks vpc-access connectors create "${VPC_CONNECTOR}" \
  --region="${REGION}" \
  --range="10.8.0.0/28" \
  --min-instances=2 \
  --max-instances=3 \
  2>/dev/null || echo "  (already exists)"

# ── 6. Create service account for Cloud Run ─────────────────────────
echo "=== Creating service account: ${SA_NAME} ==="
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
gcloud iam service-accounts create "${SA_NAME}" \
  --display-name="ChronoCanvas Cloud Run SA" \
  2>/dev/null || echo "  (already exists)"

# Grant permissions
for ROLE in \
  roles/cloudsql.client \
  roles/secretmanager.secretAccessor \
  roles/storage.objectAdmin \
  roles/logging.logWriter \
  roles/monitoring.metricWriter; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${ROLE}" \
    --quiet
done

# ── 7. Create secrets in Secret Manager ─────────────────────────────
echo "=== Creating Secret Manager secrets ==="
create_secret() {
  local name="$1"
  local value="$2"
  if gcloud secrets describe "${name}" &>/dev/null; then
    echo "  ${name} (already exists — add new version with: echo -n 'value' | gcloud secrets versions add ${name} --data-file=-)"
  else
    echo -n "${value}" | gcloud secrets create "${name}" --data-file=-
    echo "  ${name} created"
  fi
}

create_secret "chronocanvas-secret-key" "$(openssl rand -hex 32)"
create_secret "chronocanvas-google-api-key" "REPLACE_WITH_YOUR_GOOGLE_API_KEY"
create_secret "chronocanvas-anthropic-api-key" "REPLACE_WITH_YOUR_ANTHROPIC_API_KEY"

# ── 8. Set up Workload Identity Federation for GitHub Actions ───────
if [ -n "${GITHUB_REPO}" ]; then
  echo "=== Setting up Workload Identity Federation ==="
  WIF_POOL="github-pool"
  WIF_PROVIDER="github-provider"

  gcloud iam workload-identity-pools create "${WIF_POOL}" \
    --location="global" \
    --display-name="GitHub Actions" \
    2>/dev/null || echo "  Pool already exists"

  gcloud iam workload-identity-pools providers create-oidc "${WIF_PROVIDER}" \
    --location="global" \
    --workload-identity-pool="${WIF_POOL}" \
    --display-name="GitHub" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    2>/dev/null || echo "  Provider already exists"

  # Allow GitHub Actions to impersonate the deploy SA
  DEPLOY_SA="${SA_NAME}-deploy@${PROJECT_ID}.iam.gserviceaccount.com"
  gcloud iam service-accounts create "${SA_NAME}-deploy" \
    --display-name="ChronoCanvas Deploy SA (CI/CD)" \
    2>/dev/null || echo "  (already exists)"

  PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)")
  gcloud iam service-accounts add-iam-policy-binding "${DEPLOY_SA}" \
    --role="roles/iam.workloadIdentityUser" \
    --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WIF_POOL}/attribute.repository/${GITHUB_REPO}"

  for ROLE in roles/artifactregistry.writer roles/run.developer roles/iam.serviceAccountUser; do
    gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
      --member="serviceAccount:${DEPLOY_SA}" \
      --role="${ROLE}" \
      --quiet
  done

  WIF_PROVIDER_FULL="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WIF_POOL}/providers/${WIF_PROVIDER}"
fi

# ── Summary ─────────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo "  GCP Cloud Run setup complete!"
echo "============================================================"
echo ""
echo "Artifact Registry: ${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}"
echo "Cloud SQL:         ${DB_CONNECTION_NAME}"
echo "Redis:             ${REDIS_HOST}:${REDIS_PORT}"
echo "VPC Connector:     ${VPC_CONNECTOR}"
echo "Service Account:   ${SA_EMAIL}"
echo ""
echo "Next steps:"
echo "  1. Update Secret Manager values:"
echo "     echo -n 'YOUR_KEY' | gcloud secrets versions add chronocanvas-google-api-key --data-file=-"
echo "     echo -n 'YOUR_KEY' | gcloud secrets versions add chronocanvas-anthropic-api-key --data-file=-"
echo ""
echo "  2. Deploy with:"
echo "     bash deploy/cloudrun/scripts/deploy.sh"
echo ""
if [ -n "${GITHUB_REPO}" ]; then
  echo "  GitHub Actions secrets to configure:"
  echo "    GCP_PROJECT_ID      = ${PROJECT_ID}"
  echo "    GCP_REGION          = ${REGION}"
  echo "    WIF_PROVIDER        = ${WIF_PROVIDER_FULL}"
  echo "    WIF_SERVICE_ACCOUNT = ${DEPLOY_SA}"
fi
