# ChronoCanvas GKE Deployment Guide

Deploy ChronoCanvas to Google Kubernetes Engine (Autopilot) with in-cluster PostgreSQL and Redis. This deployment is designed for experimentation and low-cost operation, with a clear upgrade path to managed services.

## Architecture

```
Internet → Cloud LB (static IP + TLS) → frontend (nginx)
                                            ├── / (SPA)
                                            ├── /api/* → api:8000 (FastAPI)
                                            ├── /ws/*  → api:8000 (WebSocket)
                                            └── /output/* → api:8000 (images)

api → postgres:5432 (StatefulSet, pgvector)
    → redis:6379 (Deployment, ephemeral)
    → PVC /data (output + uploads)

worker (ARQ) → same postgres, redis, PVC
```

All services run in the `chronocanvas` namespace.

## Prerequisites

- [gcloud CLI](https://cloud.google.com/sdk/docs/install) authenticated with project owner/editor
- `kubectl` (installed via `gcloud components install kubectl`)
- A GCP project with billing enabled
- A domain name with DNS access
- GitHub repo with Actions enabled

## 1. One-Time GCP Setup

```bash
export GCP_PROJECT_ID=your-project-id
export GCP_REGION=us-central1          # optional, defaults to us-central1
export GITHUB_REPO=your-user/chrono-canvas

bash deploy/gke/scripts/setup-gcp.sh
```

This creates:
- GKE Autopilot cluster
- Artifact Registry repository
- Global static IP for the Ingress
- Workload Identity Federation for GitHub Actions
- GCP service account with required permissions

**After running**, the script prints values to configure as GitHub Secrets.

## 2. Configure GitHub Secrets

In your repo's Settings > Secrets and variables > Actions, add:

| Secret | Description |
|--------|-------------|
| `GCP_PROJECT_ID` | Your GCP project ID |
| `GCP_REGION` | Region (e.g., `us-central1`) |
| `WIF_PROVIDER` | Workload Identity Federation provider (printed by setup script) |
| `WIF_SERVICE_ACCOUNT` | GCP service account email (printed by setup script) |
| `DB_PASSWORD` | PostgreSQL password (generate a strong one) |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `OPENAI_API_KEY` | OpenAI API key (optional) |
| `SERPAPI_KEY` | SerpAPI key (optional, for face search) |
| `APP_SECRET_KEY` | Random string for app sessions (e.g., `openssl rand -hex 32`) |

## 3. Configure GitHub Environment

Create a GitHub Environment for deployment approval:

1. Go to Settings > Environments > New environment
2. Name: `gke-production`
3. Add required reviewers (yourself or your team)
4. Save

## 4. Configure Manifests

Before the first deploy, update:

- **`deploy/gke/managed-certificate.yaml`**: Replace `chronocanvas.example.com` with your actual domain
- **`deploy/gke/configmap.yaml`**: Update `CORS_ORIGINS` to `["https://your-domain.com"]`
- **DNS**: Point your domain's A record to the static IP from step 1

## 5. Deploy

Push to `main`. The CD pipeline will:

1. Build and push Docker images to Artifact Registry
2. **Pause for approval** (check GitHub Actions)
3. After approval: apply manifests, run migrations, deploy workloads

```bash
git push origin main
# Go to GitHub Actions → "CD — Deploy to GKE" → Review and approve
```

### First-time manual deploy (alternative)

```bash
# Create namespace and secrets
kubectl apply -f deploy/gke/namespace.yaml
bash deploy/gke/scripts/create-secrets.sh

# Build and push images manually
REGISTRY="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/chronocanvas"
docker build -f docker/Dockerfile.api -t "${REGISTRY}/api:initial" .
docker build -f docker/Dockerfile.frontend -t "${REGISTRY}/frontend:initial" .
docker push "${REGISTRY}/api:initial"
docker push "${REGISTRY}/frontend:initial"

# Apply all manifests (update image tags in deployment YAMLs first)
kubectl apply -f deploy/gke/
```

## 6. Verify

```bash
# All pods running?
kubectl get pods -n chronocanvas

# Migration completed?
kubectl get jobs -n chronocanvas

# API health?
kubectl exec deployment/api -n chronocanvas -- curl -s localhost:8000/api/health

# Ingress has IP?
kubectl get ingress -n chronocanvas

# TLS certificate status (may take 15–60 min for initial provisioning)
kubectl describe managedcertificate chronocanvas-cert -n chronocanvas

# External access
curl https://your-domain.com/api/health
```

## Operations

### Logs

```bash
kubectl logs deployment/api -n chronocanvas
kubectl logs deployment/worker -n chronocanvas
kubectl logs deployment/frontend -n chronocanvas
kubectl logs statefulset/postgres -n chronocanvas
```

### Scaling

Edit the HPA manifests:

```bash
# Scale worker max replicas
kubectl edit hpa worker-hpa -n chronocanvas
```

Note: Scaling the API beyond 1 replica requires switching to a ReadWriteMany PVC (see upgrade path below).

### Rollback

```bash
kubectl rollout undo deployment/api -n chronocanvas
kubectl rollout undo deployment/worker -n chronocanvas
kubectl rollout undo deployment/frontend -n chronocanvas
```

### Manual migration

```bash
REGISTRY="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/chronocanvas"
kubectl run migrate --rm -it --restart=Never -n chronocanvas \
  --image="${REGISTRY}/api:latest" \
  --overrides='{"spec":{"serviceAccountName":"chronocanvas-sa"}}' \
  --env="DATABASE_URL=$(kubectl get secret chronocanvas-secrets -n chronocanvas -o jsonpath='{.data.DATABASE_URL}' | base64 -d)" \
  -- alembic upgrade head
```

### Database shell

```bash
kubectl exec -it statefulset/postgres -n chronocanvas -- psql -U chronocanvas
```

## Upgrading to Managed Services

The in-cluster deployment is suitable for experimentation. For production workloads, upgrade to managed services:

### Cloud SQL (PostgreSQL)

1. Create a Cloud SQL instance with pgvector enabled:
   ```bash
   gcloud sql instances create chronocanvas-db --database-version=POSTGRES_16 --region=${GCP_REGION} --tier=db-f1-micro
   gcloud sql databases create chronocanvas --instance=chronocanvas-db
   ```
2. Update `DATABASE_URL` in the secret to use `127.0.0.1:5432` (Cloud SQL Proxy address)
3. Add Cloud SQL Auth Proxy sidecar to `api-deployment.yaml`, `worker-deployment.yaml`, and `migration-job.yaml`
4. Delete `postgres-statefulset.yaml` and `postgres-service.yaml`

### Memorystore (Redis)

1. Create a Memorystore instance:
   ```bash
   gcloud redis instances create chronocanvas-redis --region=${GCP_REGION} --size=1
   ```
2. Update `REDIS_URL` in the secret to use the Memorystore IP
3. Delete `redis-deployment.yaml` and `redis-service.yaml`

### Filestore (ReadWriteMany PVC)

1. Update `data-pvc.yaml`: change StorageClass to `filestore.csi.storage.gke.io`, access mode to `ReadWriteMany`, size to `1Ti` (Filestore minimum)
2. Update `api-hpa.yaml`: increase `maxReplicas` above 1

## Cost Estimate (Autopilot)

Approximate monthly costs for the default configuration (as of early 2026):

| Resource | vCPU | Memory | ~Cost/mo |
|----------|------|--------|----------|
| API | 0.5 | 1 GiB | ~$15 |
| Worker | 0.5 | 1 GiB | ~$15 |
| Frontend (x2) | 0.2 | 128 MiB | ~$8 |
| PostgreSQL | 0.5 | 512 MiB | ~$13 |
| Redis | 0.1 | 128 MiB | ~$4 |
| PVCs (15 GiB) | — | — | ~$2 |
| **Total** | | | **~$57/mo** |

GKE Autopilot pricing is per-pod based on requested resources. Actual costs depend on region and usage patterns.

## Local Development

This GKE deployment is completely independent of the local development workflow. Use the existing Docker Compose setup for local development:

```bash
make dev          # Start all services with docker-compose.dev.yml
make frontend     # Start Vite dev server
make seed         # Seed the database
```

See `docs/development.md` for the full local development guide.
