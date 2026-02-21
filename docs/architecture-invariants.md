# Architecture Invariants

These rules must remain true across all refactors. Violating any of them is a breaking change that requires explicit discussion and a new architectural decision record.

---

## 1. Async all the way down

Every I/O operation — database queries, HTTP calls, Redis pub/sub, file reads — must be async. No synchronous blocking calls inside the FastAPI/uvicorn process or the ARQ worker. Use `asyncpg`, `httpx`, `aiofiles`, and async SQLAlchemy.

## 2. Pipeline jobs run in the ARQ worker, not in the API process

`run_generation_pipeline` and `retry_generation_pipeline` are enqueued via `arq_pool.enqueue_job()`. The API process must never `await` a pipeline function directly. The worker process owns all long-running work.

## 3. Agent state is defined in `AgentState`

All data that flows between agent nodes travels through the `AgentState` TypedDict defined in `agents/state.py`. Nodes must not share state through module-level globals, class attributes, or any other side channel.

## 4. Validation is informational only

The validation agent records a score and a pass/fail result for auditing purposes. It must not block the pipeline from reaching `facial_compositing` and `export`. Routing decisions after validation must proceed to compositing regardless of the score.

## 5. External URLs are SSRF-screened before fetching

Any URL provided by a user or constructed from user input must be passed through `security.validate_url()` before an outbound HTTP request is made. No exceptions.

## 6. Images are magic-byte validated before processing

Files accepted via upload or downloaded from external sources must be validated with `security.validate_image_magic_bytes()` before being processed by Pillow, FaceFusion, or any other imaging library.

## 7. Redis pub/sub is the only real-time channel

WebSocket clients receive progress events exclusively via Redis pub/sub (`publish_progress` / `subscribe_progress`). Agent nodes must never hold a reference to a WebSocket connection.

## 8. The LLM router is a singleton; providers are stateless

`llm_router` in `llm/router.py` is instantiated once at module load. LLM provider classes must be stateless — no per-request mutable instance state.

## 9. No hardcoded machine-specific paths

`docker-compose.dev.yml` and all configuration files must use environment variables for any path that differs between developer machines. Personal absolute paths (e.g. `/Users/yourname/...`) must never be committed.

## 10. `.env` is never committed

`.env` contains secrets and local overrides. `.env.example` is the canonical reference for all supported variables and must be kept in sync when variables are added or removed.

## 11. Database access goes through repositories

SQLAlchemy models must only be queried through repository classes in `db/repositories/`. Route handlers and agent nodes must not construct raw SQL or access `Session`/`AsyncSession` directly (except to pass it to a repository constructor).

## 12. Seed data is idempotent

`seed/load_seed.py` must be safe to run multiple times against a populated database (upsert, not insert). Running it twice must not duplicate rows.
