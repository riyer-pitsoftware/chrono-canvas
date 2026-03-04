#!/usr/bin/env bash
# Step 1: Enable required GCP APIs.
# Run this first, then wait 1-2 minutes for propagation before step 2.
#
# Usage:
#   source deploy/cloudrun/scripts/00-env.sh
#   bash deploy/cloudrun/scripts/01-enable-apis.sh
set -euo pipefail
source "$(dirname "$0")/00-env.sh"

echo "=== Enabling APIs (this takes ~60 seconds) ==="
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  sqladmin.googleapis.com \
  redis.googleapis.com \
  secretmanager.googleapis.com \
  vpcaccess.googleapis.com \
  iam.googleapis.com \
  compute.googleapis.com \
  --project="${GCP_PROJECT_ID}"

echo ""
echo "✅ All APIs enabled."
echo ""
echo "⏳ Wait 1-2 minutes for API propagation before running step 02."
