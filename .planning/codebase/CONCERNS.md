# Codebase Concerns

**Analysis Date:** 2026-02-27

## Tech Debt

**In-Memory Checkpointer for LangGraph State Fallback:**
- Issue: The checkpointer starts as `MemorySaver()` at module load and is replaced by `AsyncPostgresSaver` during startup. If the Postgres checkpointer initialization fails, the system falls back to in-memory storage which is lost on process restart, causing interrupted pipelines to become unrecoverable without checkpoint data.
- Files: `backend/src/chronocanvas/agents/checkpointer.py`, `backend/src/chronocanvas/agents/graph.py`
- Impact: Long-running pipelines interrupted by server restarts lose their checkpoint state. The retry system attempts state reconstruction via `RetryCoordinator.rebuild_state_from_db()`, but this is best-effort and may lose intermediate context (sub-dicts from predecessor nodes not preserved in denormalized columns).
- Fix approach: Make Postgres checkpointer initialization blocking during startup. Use `pytest.fail()` in tests if checkpointer setup fails. Add explicit warnings to deployment docs about running without durable checkpoints.

**Implicit State Merging in Retry Reconstruction:**
- Issue: When rebuilding state from the database after a restart, `RetryCoordinator.rebuild_state_from_db()` searches the agent trace for the predecessor node's `state_snapshot` and merges its keys back into state. This relies on trace entries existing and being properly formatted; if a node fails to save its snapshot, downstream retry may have incomplete context.
- Files: `backend/src/chronocanvas/services/retry.py` (lines 56-70)
- Impact: Retries from later pipeline stages may silently miss information from earlier stages (e.g., face search results, prompt details) if the snapshot wasn't recorded. The pipeline continues but with degraded context.
- Fix approach: Add explicit logging and metrics when state is reconstructed; validate that required keys are present before returning from `rebuild_state_from_db()`. Consider storing a full state snapshot at each node rather than just the sub-dicts.

**Validation Node Silently Defaults on JSON Parse Failures:**
- Issue: If the LLM validation response is not valid JSON, the validation node defaults to an unconditional pass (score 75.0, passed=True) and logs nothing to the trace about the parse error, masking failures.
- Files: `backend/src/chronocanvas/agents/nodes/validation.py` (lines 85-95)
- Impact: Invalid LLM responses are not surfaced to the user or audit logs; they pass silently. A downstream issue with the LLM provider or prompt engineering goes unnoticed.
- Fix approach: Log a warning when JSON parsing fails; record the raw response and the parse error in the trace for audit visibility.

**Generic Error Messages Lose Root Cause Context:**
- Issue: Pipeline errors are caught at the `GenerationRunner` level and wrapped in generic error messages (lines 141-142 in `services/runner.py`): `f"Pipeline error after node: {last_successful_agent or 'unknown'}"`. The underlying exception is logged at WARNING level only and not persisted to the database, so users see minimal information.
- Files: `backend/src/chronocanvas/services/runner.py` (lines 133-147), `backend/src/chronocanvas/services/generation.py` (lines 110-114)
- Impact: Users cannot diagnose why their request failed. Audit logs and API responses lack detail needed for support or debugging.
- Fix approach: Store the full exception traceback in a new `error_detail` field on `GenerationRequest` during error handling. Expose it via the API audit endpoint.

---

## Known Bugs

**Face Search Results Not Validated Before Use:**
- Symptoms: If face search returns a malformed or unsafe image URL, the system attempts to fetch and use it without re-validating the magic bytes at download time. Although `security.is_safe_url()` screens the URL for SSRF, the downloaded file is not re-validated.
- Files: `backend/src/chronocanvas/agents/nodes/face_search.py` (line ~124)
- Trigger: Occurs if a URL points to a file with a misleading extension (e.g., `.jpg` that is actually a ZIP or executable).
- Workaround: None. Face search results are trusted once downloaded.
- Fix approach: Add a post-download validation step in face search or the image downloader to re-check magic bytes on all fetched files.

**WebSocket Slow-Client Disconnection Does Not Clear Manager State Immediately:**
- Symptoms: When a WebSocket client cannot accept a message within `_SEND_TIMEOUT_S` (5s) and is disconnected via `manager.disconnect()`, there is a brief window where the connection is removed from the manager's dictionary but the client may still attempt to reconnect and see stale manager state.
- Files: `backend/src/chronocanvas/api/websocket.py` (lines 54-60)
- Trigger: Slow/lagging client connections during active generation.
- Workaround: Client-side reconnection logic should not assume stale connections will be cleaned up immediately.
- Fix approach: No code fix needed; this is expected behavior. Document that WebSocket disconnections are eventual, and clients should handle transient connection loss.

**Database JSONB Incompatibility with SQLite Tests:**
- Symptoms: Tests using SQLite fail when the code attempts to query JSONB columns (e.g., `agent_trace`, `llm_calls` stored as JSON). SQLite does not support JSONB indexing or operators used in production Postgres queries.
- Files: `tests/test_db/test_repositories.py` (pre-existing failures mentioned in memory)
- Trigger: Running `pytest` with the default SQLite test database.
- Workaround: Run tests against a containerized Postgres instance (see conftest.py for session fixture). Alternatively, mock repository methods.
- Fix approach: Use a test Postgres container (e.g., via pytest-postgresql or testcontainers) instead of SQLite. Document the requirement in CONTRIBUTING.md.

---

## Security Considerations

**Default Secret Key in Production:**
- Risk: The `secret_key` setting defaults to `"change-me-in-production"` in `config.py`. If an operator does not override this via environment variables, the system is deployed with a publicly known secret used for signing or encryption.
- Files: `backend/src/chronocanvas/config.py` (line 49)
- Current mitigation: `.env.example` documents the variable; deployment docs mention hardening checklist.
- Recommendations: Make `secret_key` a required setting with no default; fail fast at startup if it is not set or is the default. Add a pre-deployment check script that validates all security-sensitive settings.

**SSRF Protection Assumes DNS Stability:**
- Risk: `security.is_safe_url()` screens URLs for private IP ranges but does not perform DNS lookups (see line 71: "we can't resolve it here"). An attacker can register a domain that initially resolves to a safe IP but later resolves to a private IP (DNS rebinding attack).
- Files: `backend/src/chronocanvas/security.py` (lines 68-71)
- Current mitigation: Documented in `docs/deployment-hardening.md` section 3 as a known gap.
- Recommendations: Implement a separate "fetch with re-check" flow that resolves the hostname, validates the result, and then immediately connects. Alternatively, use a DNS-filtering gateway at the network level.

**WebSocket Channel Access Not Authenticated:**
- Risk: WebSocket connections are keyed by `request_id` (a UUID). An attacker who knows or guesses the request ID of another user's generation can connect to the WebSocket and observe real-time progress, potentially leaking information about figures being generated.
- Files: `backend/src/chronocanvas/api/websocket.py` (line 91: `channel = f"generation:{request_id}"`)
- Current mitigation: Relies on request IDs being unguessable UUIDs.
- Recommendations: Require authentication on WebSocket endpoints. Add a database check that verifies the connecting user (via JWT or session) has permission to watch the given request_id.

**File Path Confinement Check Only Happens After Resolution:**
- Risk: Symlinks and `..` components are resolved before the confinement check in `security.confine_path()`, but if a user can create symlinks within the allowed directory pointing outside it, they can escape. This is a design trade-off: catching symlinks before resolution would be more restrictive.
- Files: `backend/src/chronocanvas/security.py` (lines 117-134)
- Current mitigation: Filesystem permissions should prevent users from creating arbitrary symlinks within output/upload directories.
- Recommendations: Run regular audits of `/output` and `/uploads` to detect unexpected symlinks. Document that the confinement assumes symlink creation is not under user control.

---

## Performance Bottlenecks

**Large Agent Trace and LLM Calls Serialization:**
- Problem: The `agent_trace` and `llm_calls` lists are stored as JSON in the database and serialized on every update. For long-running pipelines with many node iterations (e.g., 5 validation retries), these lists grow unbounded and may cause serialization latency.
- Files: `backend/src/chronocanvas/services/runner.py` (lines 68-70), `backend/src/chronocanvas/db/models/request.py`
- Cause: No limit on trace list growth; each node appends to the list and persists it.
- Improvement path: Implement a rolling window that keeps only the last N trace entries. Alternatively, store the full trace in a separate trace table with foreign keys to the request, and only store metadata in the request row.

**Research Cache Embedding Computation On Every Lookup:**
- Problem: The research cache uses sentence transformers to embed incoming research text and compute cosine similarity against cached embeddings. For each generation request, this embedding computation happens sequentially and can be slow (1-5 seconds per request).
- Files: `backend/src/chronocanvas/memory/embedder.py`, `backend/src/chronocanvas/db/repositories/research_cache.py`
- Cause: No batching of embedding requests; no GPU acceleration by default.
- Improvement path: (1) Add a GPU-enabled embedding service or use a cloud embedding API. (2) Pre-compute and cache embeddings for common historical figures. (3) Use a faster embedding model like MiniLM.

**Redis Pub/Sub Broadcast to All Subscribers:**
- Problem: Progress events are published to Redis with no filtering. If many clients are subscribed to the same request ID, each message must be serialized and sent to every subscriber, which scales poorly under high concurrency.
- Files: `backend/src/chronocanvas/redis_client.py`, `backend/src/chronocanvas/api/websocket.py`
- Cause: Redis pub/sub is inherently broadcast-only.
- Improvement path: Switch to Redis Streams (XREAD) so each client maintains its own position in a durable stream, or use a message queue with consumer groups (NATS, RabbitMQ).

**Image Generation Output Directory Not Pruned:**
- Problem: Generated images and attempts accumulate in `OUTPUT_DIR` indefinitely. For a long-running system, this grows without bound and fills disk.
- Files: Pipeline outputs written to `Path(settings.output_dir) / request_id` in multiple nodes
- Cause: No lifecycle policy on output files.
- Improvement path: Implement a scheduled job that deletes completed request output directories after a retention window (e.g., 90 days). Offload to object storage (S3) with automatic lifecycle deletion.

---

## Fragile Areas

**Validation Node Depends on Exact JSON Schema from LLM:**
- Files: `backend/src/chronocanvas/agents/nodes/validation.py` (lines 85-111)
- Why fragile: The validation prompt asks the LLM to return JSON with fields `results`, `overall_score`, and `passed`. If the LLM responds with a slightly different schema or omits fields, the parsing logic fails silently (defaults to pass). The weighted scoring logic (lines 102-111) assumes `results` is a list of dicts with `category` and `score` keys; if any entry is malformed, the weighted sum may divide by zero or produce NaN.
- Safe modification: (1) Add schema validation with Pydantic after parsing JSON. (2) Use structured output (Claude native, GPT-4o JSON mode) to guarantee schema compliance. (3) Add explicit checks for zero-weight division before computing `overall_score`.
- Test coverage: No existing tests validate malformed validation responses or weighted score edge cases.

**Retry State Reconstruction Assumes Checkpoint Precedence Chain:**
- Files: `backend/src/chronocanvas/services/retry.py` (lines 56-70), `_PREDECESSOR_NODE` map at top of file
- Why fragile: The `_PREDECESSOR_NODE` mapping must stay in sync with the actual graph edges. If a node is added or an edge is changed without updating this map, retry from a later stage will use the wrong predecessor, and state reconstruction will pull from the wrong trace entry.
- Safe modification: (1) Sync `_PREDECESSOR_NODE` with `graph.py` edges any time edges change. (2) Add an invariant check that validates `_PREDECESSOR_NODE` against the actual graph structure at startup.
- Test coverage: `tests/test_integration/test_checkpoint_recovery.py` covers the happy path but not edge cases like missing trace entries.

**Facial Compositing Continues on Failure Without User Awareness:**
- Files: `backend/src/chronocanvas/agents/nodes/facial_compositing.py` (lines 100-115)
- Why fragile: If face swapping fails (e.g., FaceFusion crashes), the node logs an exception and returns success with the original image. The user is not notified that face swapping was skipped; they may think their portrait was composited when it was not.
- Safe modification: (1) Set a flag `compositing_attempted` in the return state. (2) Include a warning in the audit trace visible to the user. (3) Consider making compositing failure terminal only for explicit (non-mock) providers.
- Test coverage: `tests/test_agents/test_face_swap.py` and `tests/test_agents/test_export_face_swap.py` test the happy path and mock failures, but not real FaceFusion errors.

---

## Scaling Limits

**Single-Instance Redis for Checkpoints and Pub/Sub:**
- Current capacity: Redis can handle ~10k requests in-flight on a single 4GB instance (rough estimate based on typical state sizes).
- Limit: Exceeding memory leads to eviction or OOM kills. No replication or persistence by default (unless AOF is enabled manually).
- Scaling path: (1) Use Redis Cluster for sharding. (2) Enable AOF persistence and replication. (3) Migrate checkpoints to durable Postgres (already supported). Keep only real-time progress in Redis.

**Synchronous Image Generation Serializes Requests:**
- Current capacity: With a single ComfyUI/Stable Diffusion instance, generation throughput is ~1 image per 10-30 seconds depending on model.
- Limit: Queued requests wait linearly for GPU availability. With 100 concurrent requests, average latency becomes minutes.
- Scaling path: (1) Add GPU worker pools or use a managed image generation API (Replicate, BedRock). (2) Implement request prioritization or batch generation. (3) Cache generated images if prompts are similar.

**LangGraph Checkpoints Stored Per-Thread:**
- Current capacity: Each request gets its own thread_id in the checkpoint. Checkpointers are not tested for concurrent access to the same thread_id (i.e., simultaneous retries of the same request).
- Limit: Concurrent state updates to the same request_id may overwrite or lose intermediate changes.
- Scaling path: (1) Implement request-level locking before retry_generation_pipeline. (2) Add a "request is locked" flag to the database. (3) Test concurrent retry scenarios.

---

## Dependencies at Risk

**LangGraph Checkpoint API Stability:**
- Risk: The checkpoint interface is relatively new and may change between minor LangGraph versions. The custom logic in `RetryCoordinator.rebuild_state_from_db()` and the raw `aget_state()` / `aupdate_state()` calls assume a stable API.
- Impact: LangGraph version bumps could break state recovery.
- Migration plan: (1) Pin LangGraph version in `requirements.txt` (already pinned). (2) Add integration tests that exercise checkpoint recovery on every version bump. (3) Keep a separate legacy checkpoint handler in case the API changes.

**ComfyUI & Stable Diffusion API Contracts:**
- Risk: ComfyUI and Stable Diffusion are rapidly evolving. The `comfyui_client.py` constructs workflow JSON by hand; any change to the API or node structure will break image generation.
- Impact: Environment upgrades (e.g., new SD models) may require code changes.
- Migration plan: (1) Version-pin the ComfyUI and SD installations. (2) Maintain separate client implementations for major versions (e.g., `comfyui_client_v2.py`). (3) Add health checks that validate the API is in a known state.

**FaceFusion Provider Not Standardized:**
- Risk: FaceFusion (`facial_compositing_client.py`) is called directly with source and target image paths. No standardization or fallback if the provider fails or changes its interface.
- Impact: If FaceFusion becomes unavailable or changes its API, there is no graceful degradation (other than silently returning the original image).
- Migration plan: (1) Add a provider abstraction with a no-op/mock implementation. (2) Make the provider pluggable via settings (already partially done). (3) Add health checks that validate the provider is alive.

**Anthropic & OpenAI API Deprecations:**
- Risk: Model versions and API endpoints change frequently. The system hard-codes `claude-sonnet-4-5-20250929` and `gpt-4o`; these may become deprecated.
- Impact: Requests fail when the model is removed from the provider's API.
- Migration plan: (1) Add a deprecation check at startup that validates all configured models are available. (2) Implement automatic fallback to newer model versions. (3) Add alerts when using deprecated models.

---

## Missing Critical Features

**No Rate Limiting by User/Organization:**
- Problem: The rate limiter in `config.py` is global (RPM-based). If multi-tenant or multi-user, there is no way to limit per-user request quotas or billing-based limits.
- Blocks: SaaS deployment, cost control, fair-use policies.
- Gap: Add a user-to-quota mapping in the database; check it before enqueuing jobs.

**No Persistent Background Job Queue Fallback:**
- Problem: If Redis goes down, ARQ (the job queue) loses all enqueued jobs. Unlike a durable queue (e.g., RabbitMQ, AWS SQS), there is no recovery mechanism.
- Blocks: High-availability deployments.
- Gap: Implement a database-backed job queue or use a managed queue service. Alternatively, add a health check that alerts if Redis is down.

**No Audit Trail for Admin Actions:**
- Problem: The admin routes that accept/reject validations do not log who made the decision, when, or why.
- Blocks: Compliance audits (HIPAA, GDPR).
- Gap: Add an audit log table for admin actions with user ID, timestamp, and decision.

**No Graceful Shutdown for In-Flight Pipelines:**
- Problem: If the API or worker process is shut down, in-flight generation requests are abandoned. The client loses WebSocket connection and has no way to resume or check status.
- Blocks: Zero-downtime deployments.
- Gap: Implement a graceful shutdown handler that waits for in-flight jobs to complete or checkpoints them for later recovery.

---

## Test Coverage Gaps

**Untested LLM Provider Fallback Logic:**
- What's not tested: The LLM router's fallback behavior when the primary provider fails (e.g., Anthropic API returns 503, falls back to OpenAI).
- Files: `backend/src/chronocanvas/llm/router.py`
- Risk: Fallback logic may have subtle bugs (e.g., model config not applied to fallback, token counting incorrect). These are caught only in production.
- Priority: High — this is a critical execution path.

**No Tests for Concurrent Retry Scenarios:**
- What's not tested: What happens if two users retry the same request simultaneously from different nodes? Does state get corrupted?
- Files: `backend/src/chronocanvas/services/generation.py`, `backend/src/chronocanvas/services/retry.py`
- Risk: Race conditions in state updates or checkpointer locking are not detected.
- Priority: Medium — high concurrency is not the current use case, but may be in future deployments.

**WebSocket Backpressure Under Load:**
- What's not tested: What happens if many clients (1000+) connect to watch different requests? Does the WebSocket manager or Redis pub/sub degrade gracefully or crash?
- Files: `backend/src/chronocanvas/api/websocket.py`, `backend/src/chronocanvas/redis_client.py`
- Risk: Memory leaks or connection pool exhaustion under high load.
- Priority: Medium — not critical until user base scales.

**Malformed Database State Recovery:**
- What's not tested: What happens if the `agent_trace` JSON is corrupted or incomplete? Does the retry system handle it gracefully or crash?
- Files: `backend/src/chronocanvas/services/retry.py`
- Risk: A single corrupt request in the database can crash the retry handler.
- Priority: Low — but add explicit validation and error handling.

---

*Concerns audit: 2026-02-27*
