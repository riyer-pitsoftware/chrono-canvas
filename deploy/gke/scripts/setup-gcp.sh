#!/usr/bin/env bash
# One-time GCP project setup for ChronoCanvas GKE deployment.
#
# Prerequisites:
#   - gcloud CLI authenticated (gcloud auth login)
#   - A GCP project with billing enabled
#
# Usage:
#   export GCP_PROJECT_ID=my-project
#   export GCP_REGION=us-central1
#   bash deploy/gke/scripts/setup-gcp.sh
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
REGION="${GCP_REGION:-us-central1}"
CLUSTER_NAME="chronocanvas-cluster"
AR_REPO="chronocanvas"
SA_NAME="chronocanvas-deploy"
K8S_SA_NAME="chronocanvas-sa"
K8S_NAMESPACE="chronocanvas"
STATIC_IP_NAME="chronocanvas-ip"
# GitHub org/user and repo for Workload Identity Federation
GITHUB_REPO="${GITHUB_REPO:?Set GITHUB_REPO (e.g. myuser/chrono-canvas)}"

echo "=== Setting project: ${PROJECT_ID} ==="
gcloud config set project "${PROJECT_ID}"

# ── 1. Enable APIs ──────────────────────────────────────────────────
echo "=== Enabling APIs ==="
gcloud services enable \
  container.googleapis.com \
  artifactregistry.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com

# ── 2. Create Artifact Registry repository ──────────────────────────
echo "=== Creating Artifact Registry repo: ${AR_REPO} ==="
gcloud artifacts repositories create "${AR_REPO}" \
  --repository-format=docker \
  --location="${REGION}" \
  --description="ChronoCanvas container images" \
  2>/dev/null || echo "  (already exists)"

# ── 3. Create GKE Autopilot cluster ────────────────────────────────
echo "=== Creating GKE Autopilot cluster: ${CLUSTER_NAME} ==="
if gcloud container clusters describe "${CLUSTER_NAME}" --region="${REGION}" &>/dev/null; then
  echo "  (already exists)"
else
  gcloud container clusters create-auto "${CLUSTER_NAME}" \
    --region="${REGION}" \
    --release-channel=regular
fi

# Get credentials for kubectl
gcloud container clusters get-credentials "${CLUSTER_NAME}" --region="${REGION}"

# ── 4. Reserve global static IP ────────────────────────────────────
echo "=== Reserving static IP: ${STATIC_IP_NAME} ==="
gcloud compute addresses create "${STATIC_IP_NAME}" --global 2>/dev/null || echo "  (already exists)"
STATIC_IP=$(gcloud compute addresses describe "${STATIC_IP_NAME}" --global --format="value(address)")
echo "  Static IP: ${STATIC_IP}"

# ── 5. Create GCP service account for Workload Identity ────────────
echo "=== Creating GCP service account: ${SA_NAME} ==="
GCP_SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
gcloud iam service-accounts create "${SA_NAME}" \
  --display-name="ChronoCanvas deploy SA" \
  2>/dev/null || echo "  (already exists)"

# ── 6. Set up Workload Identity Federation for GitHub Actions ──────
echo "=== Setting up Workload Identity Federation ==="
WIF_POOL="github-pool"
WIF_PROVIDER="github-provider"

# Create the pool
gcloud iam workload-identity-pools create "${WIF_POOL}" \
  --location="global" \
  --display-name="GitHub Actions" \
  2>/dev/null || echo "  Pool already exists"

# Create the provider
gcloud iam workload-identity-pools providers create-oidc "${WIF_PROVIDER}" \
  --location="global" \
  --workload-identity-pool="${WIF_POOL}" \
  --display-name="GitHub" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  2>/dev/null || echo "  Provider already exists"

# Allow GitHub Actions to impersonate the SA
gcloud iam service-accounts add-iam-policy-binding "${GCP_SA_EMAIL}" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/$(gcloud projects describe ${PROJECT_ID} --format='value(projectNumber)')/locations/global/workloadIdentityPools/${WIF_POOL}/attribute.repository/${GITHUB_REPO}"

# Grant the SA permissions to push images and manage GKE
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${GCP_SA_EMAIL}" \
  --role="roles/artifactregistry.writer"
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${GCP_SA_EMAIL}" \
  --role="roles/container.developer"

# ── 7. Bind K8s SA to GCP SA (for future Workload Identity usage) ──
echo "=== Binding K8s SA to GCP SA ==="
gcloud iam service-accounts add-iam-policy-binding "${GCP_SA_EMAIL}" \
  --role="roles/iam.workloadIdentityUser" \
  --member="serviceAccount:${PROJECT_ID}.svc.id.goog[${K8S_NAMESPACE}/${K8S_SA_NAME}]" \
  2>/dev/null || true

# ── Summary ─────────────────────────────────────────────────────────
WIF_PROVIDER_FULL="projects/$(gcloud projects describe ${PROJECT_ID} --format='value(projectNumber)')/locations/global/workloadIdentityPools/${WIF_POOL}/providers/${WIF_PROVIDER}"

echo ""
echo "============================================================"
echo "  GCP setup complete!"
echo "============================================================"
echo ""
echo "Static IP:         ${STATIC_IP}"
echo "Artifact Registry: ${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}"
echo "GKE Cluster:       ${CLUSTER_NAME} (${REGION})"
echo ""
echo "Configure these GitHub Secrets in your repo:"
echo "  GCP_PROJECT_ID      = ${PROJECT_ID}"
echo "  GCP_REGION          = ${REGION}"
echo "  WIF_PROVIDER        = ${WIF_PROVIDER_FULL}"
echo "  WIF_SERVICE_ACCOUNT = ${GCP_SA_EMAIL}"
echo ""
echo "Configure these additional GitHub Secrets for the app:"
echo "  DB_PASSWORD          = (generate a strong password)"
echo "  ANTHROPIC_API_KEY    = (your Anthropic key)"
echo "  OPENAI_API_KEY       = (your OpenAI key)"
echo "  SERPAPI_KEY           = (your SerpAPI key)"
echo "  APP_SECRET_KEY        = (generate a random string)"
echo ""
echo "Point your domain's DNS A record to: ${STATIC_IP}"
echo "Then update deploy/gke/managed-certificate.yaml with your domain."
