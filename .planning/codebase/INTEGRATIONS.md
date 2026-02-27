# External Integrations

**Analysis Date:** 2026-02-27

## APIs & External Services

**Web Search:**
- SerpAPI (Google Images) - Face reference image discovery
  - SDK/Client: httpx async HTTP client (custom wrapper)
  - Config: `SERPAPI_KEY` environment variable
  - Usage: `backend/src/chronocanvas/agents/nodes/face_search.py` (`_search_serpapi()`)
  - Fallback: Disabled when `SERPAPI_KEY` not set or `FACE_SEARCH_ENABLED=false`
  - Endpoint: `https://serpapi.com/search.json` (engine=google_images)
  - Limits: 5MB per image download, URL validation + image magic byte checks

**LLM Providers (Pluggable Multi-Provider):**
- Claude (Anthropic)
  - SDK: `anthropic` 0.40.0+
  - Auth: `ANTHROPIC_API_KEY`
  - Default models: `claude-sonnet-4-5-20250929`
  - Usage: TaskType.RESEARCH, PROMPT_GENERATION, VALIDATION (see DEFAULT_ROUTING in `llm/router.py`)
  - Client: `chronocanvas/llm/providers/claude.py`

- OpenAI (GPT-4o)
  - SDK: `openai` 1.60.0+
  - Auth: `OPENAI_API_KEY`
  - Default model: `gpt-4o`
  - Usage: Available fallback via LLMRouter
  - Client: `chronocanvas/llm/providers/openai.py`

- Ollama (Local LLM)
  - SDK: httpx async HTTP client
  - Config: `OLLAMA_BASE_URL` (default `http://localhost:11434`), `OLLAMA_MODEL` (default `llama3.1:8b`)
  - Usage: TaskType.EXTRACTION, ORCHESTRATION (default fallback)
  - Client: `chronocanvas/llm/providers/ollama.py`
  - No auth required; runs locally in dev/test

**LLM Routing:**
- Location: `backend/src/chronocanvas/llm/router.py`
- Task-based provider selection: EXTRACTION→ollama, RESEARCH→claude, PROMPT_GENERATION→claude, VALIDATION→claude, ORCHESTRATION→ollama
- Fallback chain: preferred → ollama → any available (automatic if primary unavailable)
- Rate limiting: Config `RATE_LIMIT_RPM=60`, `LLM_MAX_CONCURRENT=5` per `config.py`
- Cost tracking: Per-call tracking in `CostTracker` class (task_type, tokens, provider)

## Data Storage

**Databases:**

- PostgreSQL 16+
  - Connection: `postgresql+asyncpg://user:pass@localhost:5432/chronocanvas`
  - Extensions: pgvector (semantic search embeddings)
  - ORM: SQLAlchemy 2.0+ with asyncio
  - Checkpointer: LangGraph AsyncPostgresSaver (schema auto-created on init)
  - Tables: generation_requests, figures, generated_images, validations, research_cache, audit_logs, validation_rules, admin_settings, audit_feedback
  - Migrations: Alembic 1.14.0+ (007 versions in `backend/alembic/versions/`)

**File Storage:**
- Local filesystem only (development/single-node)
  - Output: `./output/` — generated images, referenced as `/output/{relative_path}` in API
  - Uploads: `./uploads/` — user-submitted files (e.g., face images for upload path)
  - Served via FastAPI StaticFiles mount
  - Config: `OUTPUT_DIR`, `UPLOAD_DIR` in `.env`
  - Docker: Named volumes persist across restarts

**Caching:**

- Redis 7+ - In-memory store for pub/sub and job queue
  - Connection: `REDIS_URL=redis://localhost:6379/0`
  - Pub/Sub channels: `generation:{request_id}` for WebSocket progress updates
  - Job Queue: ARQ 0.25.0+ for background task execution (worker.py)
  - No authentication configured (localhost dev default)

- Research Cache (Semantic)
  - Backend: PostgreSQL + pgvector extension
  - Embedder: `sentence-transformers` (`all-MiniLM-L6-v2` model)
  - Config: `RESEARCH_CACHE_ENABLED=true`, `RESEARCH_CACHE_THRESHOLD=0.85` (cosine similarity)
  - Service: `chronocanvas/memory/cache_service.py` (ResearchCacheService)
  - Lookup: Embeds query text, finds similar entries above threshold, avoids duplicate API calls
  - Cost savings: Recorded in research_cache table (hit_count, cost_saved_usd)

## Authentication & Identity

**Auth Provider:**
- Custom JWT-based (reserved, not fully implemented)
  - SDK: `python-jose[cryptography]` 3.3.0+
  - Location: `backend/src/chronocanvas/security.py`
  - Status: Token generation code present; full auth enforcement not yet active
  - Secret: `SECRET_KEY` config (production: must override from env)

**API Security:**
- CORS enabled: `CORS_ORIGINS` config (default `["http://localhost:3000"]`)
- Security headers middleware: X-Content-Type-Options, X-Frame-Options, Referrer-Policy, X-XSS-Protection
- HTTPS: GKE deployment supports ManagedCertificate + FrontendConfig for TLS redirect

## Monitoring & Observability

**Error Tracking:**
- Not integrated (future enhancement)
- Local error logging via Python `logging` module (level: `LOG_LEVEL` env, default `INFO`)

**Logs:**
- Approach: Standard Python logging to console (captured by container stdout/stderr)
- Per-module loggers in each module (e.g., `logger = logging.getLogger(__name__)`)
- Audit logging: `AuditLoggingMiddleware` captures request/response metadata (location: `backend/src/chronocanvas/api/middleware.py`)
- LLM calls: Each call logged with provider, model, tokens, duration, cost

**LLM Call Tracing:**
- Captured in `llm_calls` JSONB field on GenerationRequest
- Includes: provider, model, system_prompt, user_prompt, tokens, duration_ms, cost, requested_provider, fallback status
- Agent trace: `agent_trace` JSONB list with step name, timestamp, status, skip reason (if applicable)

## CI/CD & Deployment

**Hosting:**
- Docker (development and production)
- GKE (Kubernetes Engine) - Full deployment available in `deploy/gke/`
  - Postgres StatefulSet (pgvector, 5Gi PVC)
  - Redis Deployment (ephemeral, 2Gi)
  - API, Worker, Frontend Deployments with HPA
  - Ingress: GKE Ingress with ManagedCertificate (HTTPS)
  - Migration Job: Runs `alembic upgrade head` per deploy

**CI Pipeline:**
- GitHub Actions: `.github/workflows/cd-gke.yml` (auto-build, GitHub Environment approval)
- Docker image build: `Dockerfile.api` (Python), `Dockerfile.frontend` (Node 20 → nginx)
- Not integrated: Automated tests on PR (test framework ready in pytest)

**Local Development:**
- Docker Compose: `docker-compose.yml` (PostgreSQL + Redis + API + Frontend)
- Dev variant: `docker-compose.dev.yml` (for interactive development)

## Environment Configuration

**Required env vars (critical):**
- `DATABASE_URL` — PostgreSQL connection string (asyncpg syntax)
- `REDIS_URL` — Redis connection URL
- `ANTHROPIC_API_KEY` — Claude API key (if using Claude provider)
- `OPENAI_API_KEY` — OpenAI API key (if using GPT-4o)
- `SERPAPI_KEY` — SerpAPI key for face search (optional; skipped if missing)

**Optional env vars (with defaults):**
- `DEFAULT_LLM_PROVIDER` — fallback provider (default: `ollama`)
- `OLLAMA_BASE_URL` — Ollama API endpoint (default: `http://localhost:11434`)
- `IMAGE_PROVIDER` — Image generation backend (`mock`, `stable_diffusion`, `comfyui`)
- `COMFYUI_API_URL` — ComfyUI API endpoint (default: `http://localhost:8188`)
- `FACEFUSION_ENABLED` — Enable real face-swapping (default: `false`, uses mock)
- `FACEFUSION_API_URL` — FaceFusion API endpoint (default: `http://localhost:7861`)
- `VALIDATION_RETRY_ENABLED` — Retry prompt generation on validation failure (default: `true`)
- `FACE_SEARCH_ENABLED` — Enable SerpAPI face search (default: `true`)
- `RESEARCH_CACHE_ENABLED` — Enable semantic research caching (default: `true`)
- `RESEARCH_CACHE_THRESHOLD` — Cosine similarity threshold (default: `0.85`)
- `CONTENT_MODERATION_ENABLED` — Basic keyword input validation (default: `true`)

**Secrets location:**
- Development: `.env` file (git-ignored, `cp .env.example .env`)
- Production: Kubernetes Secrets mounted as env vars (GKE deployment)
- Never committed: All `*secret*`, `*credential*`, `*.env` files

## Webhooks & Callbacks

**Incoming:**
- Not implemented (reserved for future integrations)
- WebSocket: Real-time progress streaming via `/ws/generation/{request_id}` (not a traditional webhook)

**Outgoing:**
- Not implemented (no external callbacks from pipeline)
- Progress updates: Published to Redis pub/sub (`generation:{request_id}` channel) for WebSocket subscribers

**Pub/Sub Channels (Redis):**
- `generation:{request_id}` — LLM tokens, node execution events, step completion
- Event structure: `{"type": "llm_token" | "llm_stream_end" | "...", "agent": "node_name", ...}`
- Used by: Frontend WebSocket client to display live progress

## Additional Integrations

**Batch Processing:**
- ARQ 0.25.0+ job queue (Redis-backed)
- Worker: `backend/src/chronocanvas/worker.py` (async background task runner)
- Tasks: Long-running pipeline executions queued to avoid request timeouts

**Face Detection/Swap:**
- FaceFusion API (optional real integration)
  - Location: `backend/src/chronocanvas/imaging/facefusion_client.py`
  - Docker: Pulls FaceFusion repo, runs in separate container (port 7861)
  - Fallback: Mock face-swap overlay (development)
  - Config: `FACEFUSION_ENABLED`, `FACEFUSION_SOURCE_PATH` (for bind-mount)

**Image Generation Options (Pluggable):**
- ComfyUI (advanced Stable Diffusion workflows)
  - Client: `backend/src/chronocanvas/imaging/comfyui_client.py`
  - Config: `COMFYUI_API_URL`, `COMFYUI_MODEL` (sdxl/flux), `COMFYUI_SDXL_CHECKPOINT`
  - Workflow: Custom node graph for SDXL inpainting

- Stable Diffusion (direct API)
  - Client: `backend/src/chronocanvas/imaging/sd_client.py`
  - Config: `SD_API_URL` (default `http://localhost:7860`)

- Mock (development stub)
  - Returns placeholder images without API calls
  - Used by default (`IMAGE_PROVIDER=mock`)

---

*Integration audit: 2026-02-27*
