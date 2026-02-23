# ChronoCanvas Deployment Hardening Checklist

ChronoCanvas ships as a research prototype (see [docs/development.md](development.md)#not-production-ready). Before exposing the stack to untrusted users, work through this checklist and document the compensating controls you implement. Each section states the risk, the minimum control to add, and pointers to existing code/config you can extend.

## 1. Authentication & Authorization

**Risk**: Anyone who can reach the FastAPI server can issue long-running generations, read audit logs, and upload arbitrary files.

**Controls**

- 
  - Terminate TLS and enforce mutual auth (mTLS) or OAuth/OIDC-backed login **before** requests reach the FastAPI app. Options: reverse proxy (NGINX, Traefik) + OAuth2 Proxy, or network-layer auth via Cloudflare Access / Google IAP.
  - Issue per-user API tokens and gate `/admin` routes. FastAPI already includes dependency injection hooks—wrap routes in a dependency that verifies JWTs or signed headers. Store signing secrets via your vault (see section 6).
  - Enforce role-based access in the UI: hide `/admin`, `/audit`, `/review`, and `/memory` routes unless the token carries an `admin`/`reviewer` claim.
  - Centralize session logging: forward proxy logs plus backend audit logs (`llm_calls`, `agent_trace`) to your SIEM for traceability.

## 2. Mediated File Serving & Path Confinement

**Risk**: Generated portraits live under `OUTPUT_DIR` and uploads under `UPLOAD_DIR`. If those directories are exposed directly (e.g., via a CDN), users could enumerate files or exploit stale assets.

**Controls**

- Keep storage directories private. Serve downloads through authenticated backend routes that check the requester’s identity before streaming files. Extend `backend/src/chronocanvas/api/routes/export.py` (and similar) with authorization checks.
- Mount `OUTPUT_DIR`/`UPLOAD_DIR` with restrictive filesystem permissions (chmod 750) and ensure the FastAPI process is the only reader/writer.
- Enable short-lived, signed URLs if you front assets with S3/GCS: generate URLs on-demand after verifying auth, and scope them to a single object.
- Run scheduled scrubs of `/output` and `/uploads/faces` to delete orphaned files. Document the retention window in your runbook.

## 3. Strengthen SSRF Protection & Outbound Allow List

**Risk**: The backend fetches remote URLs (face search, future integrations). Although `chronocanvas/security.py` blocks private ranges, you should assume new code may bypass the helper.

**Controls**

- Route all outbound HTTP(S) traffic through an egress proxy or VPC service controls with an allow list. Only permit domains required for: SerpAPI, ComfyUI, FaceFusion, storage APIs, and your identity provider.
- Require developers to call `is_safe_url()` everywhere URLs are fetched. Add unit tests that cover every route performing downloads.
- Disable IPv6 if your allow list tools do not cover it; otherwise, add IPv6 ranges to the deny list.
- Consider running a metadata-proxy (e.g., AWS IMDSv2 hop limit = 1) so SSRF can’t reach instance metadata even if controls fail.

## 4. Rate Limiting & Ingress Hygiene

**Risk**: Long prompts and image generations are expensive; unauthenticated traffic can exhaust GPU time or fill Redis.

**Controls**

- Enforce global request limits at your edge (e.g., Cloudflare/WAF custom rules) and per-IP quotas in your ingress controller before traffic hits FastAPI.
- Keep the internal `RATE_LIMIT_RPM` (see `.env.example`) enabled for defense-in-depth, but do not rely on it alone.
- Set maximum body sizes on the proxy (uploads are limited in code, but large bodies can still tie up sockets).
- Require TLS 1.2+ and set `Strict-Transport-Security` headers at the proxy.

## 5. Secrets & Configuration Management

**Risk**: `.env` files ship API keys and signing secrets in plaintext.

**Controls**

- Store secrets in a managed vault (AWS Secrets Manager, GCP Secret Manager, HashiCorp Vault). Inject them via the runtime environment and remove `.env` files from production hosts.
- Rotate SerpAPI, Anthropic, OpenAI, and FaceFusion credentials at least every 90 days; automate revocation when staff offboard.
- Enable audit logging on the vault and restrict read access to the deployment service account.
- Keep environment diffs in source control (`.env.example` + change log) but never commit actual values. Run `scripts/check_env_keys.py` as part of CI to ensure the example stays aligned.

## 6. Storage Durability & Backups

**Risk**: PostgreSQL, Redis, `/output`, and `/uploads` run on single-instance volumes. Hardware failure or `rm` can lose data.

**Controls**

- Use managed PostgreSQL (RDS, Cloud SQL) with automated backups, point-in-time recovery, and at least one read replica. Configure TLS and restrict DB access to the VPC.
- Replace Redis with a durable queue (e.g., Redis with AOF persistence + replication, or AWS ElastiCache with Multi-AZ). Snapshot Redis daily while you still depend on it for checkpoints.
- Offload generated images and uploads to object storage (S3 bucket with lifecycle policy, private by default). Mount the bucket via an S3 gateway or upload directly from the backend after validation.
- Version and encrypt backups. Test recovery quarterly by restoring into a staging environment and running smoke tests.

## 7. Operational Runbook

**Risk**: Without explicit procedures, responders may miss critical controls during incidents.

**Controls**

- Document on-call escalation, incident severities, and KPIs (latency, generation success rate, validation error rate).
- Define patch cadence for dependencies (LLMs, ComfyUI, FaceFusion, OS). Automate scanning for CVEs.
- Add health and readiness probes for every container so your orchestrator can restart unhealthy workloads.
- Capture dependency versions (`npm`, `pip`, Docker image digests) in deployment manifests for reproducibility.

---

### How to Use This Checklist

1. Copy the sections above into your deployment runbook and record the person/date that verified each control.
2. Link evidence: Git commit adding auth middleware, screenshot of WAF rule, Terraform snippet for bucket policies, etc.
3. Re-run the checklist whenever you add a new external integration or expose a previously internal route.

For deeper architectural details, reference [TECHNICAL.md](../TECHNICAL.md). Update this file whenever new risks or mitigations emerge.
