# ChronoCanvas — Cloud Run Deployment

Deploy ChronoCanvas to Google Cloud Run with managed PostgreSQL (Cloud SQL)
and Redis (Memorystore).

## Architecture

```
                    ┌─────────────────┐
                    │   Cloud Run:    │
    Internet ──────>│   Frontend      │──────> Cloud Run: API ──────> Cloud SQL
                    │   (nginx SPA)   │           │                  (PostgreSQL)
                    └─────────────────┘           │
                                                  ├──> Memorystore (Redis)
                                                  │
                                            Cloud Run: Worker
                                              (arq jobs)
                                                  │
                                            ┌─────┴─────┐
                                            │  Imagen   │  Gemini
                                            │  (images) │  (LLM)
                                            └───────────┘
```

**Services:**
- **API** — FastAPI backend, handles HTTP requests and WebSocket connections
- **Worker** — arq job processor, runs portrait and story generation pipelines
- **Frontend** — nginx serving Vite SPA, proxies API requests

**Managed infrastructure:**
- **Cloud SQL** — PostgreSQL 16 with pgvector extension
- **Memorystore** — Redis 7.0 for job queue
- **Secret Manager** — API keys and credentials
- **Artifact Registry** — Container images
- **VPC connector** — Private networking between Cloud Run and managed services

## Cost estimate (hackathon/demo)

| Service | Spec | Est. monthly |
|---------|------|-------------|
| Cloud SQL (db-f1-micro) | shared vCPU, 614MB | ~$9 |
| Memorystore (basic, 1GB) | Redis 7.0 | ~$35 |
| Cloud Run API (min 1) | 2 vCPU, 4GB | ~$40 |
| Cloud Run Worker (min 1) | 2 vCPU, 4GB | ~$40 |
| Cloud Run Frontend | 1 vCPU, 256MB | ~$5 |
| VPC connector | 2 instances | ~$15 |
| **Total** | | **~$144/mo** |

Scale to zero the worker and frontend to reduce costs when idle.

## Prerequisites

- Google Cloud project with billing enabled
- `gcloud` CLI installed and authenticated
- Docker installed locally (for manual deploys)

## Quick start

### 1. One-time GCP setup

```bash
export GCP_PROJECT_ID=your-project-id
export GCP_REGION=us-central1
export GITHUB_REPO=your-user/chrono-canvas  # optional, for CI/CD

bash deploy/cloudrun/scripts/setup-gcp.sh
```

This creates: Cloud SQL, Memorystore, Artifact Registry, VPC connector,
service account, and Secret Manager secrets.

### 2. Populate secrets

```bash
# Set your real API keys
echo -n 'YOUR_GOOGLE_API_KEY' | gcloud secrets versions add chronocanvas-google-api-key --data-file=-
echo -n 'YOUR_ANTHROPIC_API_KEY' | gcloud secrets versions add chronocanvas-anthropic-api-key --data-file=-
```

### 3. Deploy

```bash
export GCP_PROJECT_ID=your-project-id
export GCP_REGION=us-central1

bash deploy/cloudrun/scripts/deploy.sh
```

### 4. Verify

```bash
API_URL=$(gcloud run services describe chronocanvas-api --region=us-central1 --format="value(status.url)")
curl "${API_URL}/api/health"
```

## CI/CD (GitHub Actions)

The `cd-cloudrun.yml` workflow deploys on manual trigger (`workflow_dispatch`).

**Required GitHub Secrets:**
- `GCP_PROJECT_ID` — your GCP project ID
- `GCP_REGION` — deployment region (e.g., `us-central1`)
- `WIF_PROVIDER` — Workload Identity Federation provider (from setup output)
- `WIF_SERVICE_ACCOUNT` — deploy service account email (from setup output)

**Required GitHub Environment:** `cloudrun-production`

## Cloud Build (alternative)

For Cloud Build instead of GitHub Actions:

```bash
gcloud builds submit \
  --config=deploy/cloudrun/cloudbuild.yaml \
  --substitutions=_SA_EMAIL=chronocanvas-run@PROJECT.iam.gserviceaccount.com \
  .
```

## Key differences from GKE deployment

| Aspect | GKE | Cloud Run |
|--------|-----|-----------|
| PostgreSQL | In-cluster StatefulSet | Cloud SQL (managed) |
| Redis | In-cluster Deployment | Memorystore (managed) |
| Scaling | HPA (pod autoscaling) | Instance autoscaling |
| Networking | ClusterIP + Ingress | VPC connector + direct URLs |
| Cost model | Always-on cluster | Per-request (mostly) |
| Complexity | Higher (K8s manifests) | Lower (gcloud commands) |
| Best for | Production at scale | Hackathon/demo/small scale |

## Troubleshooting

**Worker not processing jobs:**
The worker must have `--min-instances=1` and `--no-cpu-throttling` to stay alive
and poll the Redis queue. If set to 0 min instances, it will scale down and stop
processing jobs.

**Cloud SQL connection errors:**
Ensure `--set-cloudsql-instances` is set and the VPC connector is active.
Cloud Run uses the built-in Cloud SQL Auth Proxy via Unix socket at
`/cloudsql/PROJECT:REGION:INSTANCE`.

**Secrets not found:**
Verify the service account has `roles/secretmanager.secretAccessor` and
the secret names match exactly.
