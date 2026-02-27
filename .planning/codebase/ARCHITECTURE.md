# Architecture

**Analysis Date:** 2026-02-27

## Pattern Overview

**Overall:** Multi-tier agentic system with event-driven orchestration

**Key Characteristics:**
- LangGraph-based orchestrator running 9 sequential/conditional agent nodes
- FastAPI REST API with async SQLAlchemy + PostgreSQL (Alembic migrations)
- Redis-backed job queue (ARQ) + WebSocket progress streaming
- React + TypeScript frontend with custom Zustand router
- Durable state checkpointing (in-memory MemorySaver → PostgreSQL AsyncPostgresSaver at startup)
- Content moderation gate + human-in-the-loop validation review

## Layers

**Agent Layer (LangGraph Pipeline):**
- Purpose: Stateful orchestration of 9 sequential nodes coordinating AI tasks and historical portrait generation
- Location: `backend/src/chronocanvas/agents/`
- Contains: State TypedDict, compiled graph, 9 node implementations, decision edges, invariant checks
- Depends on: LLM router, database repositories, image services
- Used by: GenerationRunner service via graph.astream()

**Service Layer (Business Logic):**
- Purpose: Coordinate graph execution, retry logic, state persistence, validation workflow
- Location: `backend/src/chronocanvas/services/`
- Contains: GenerationRunner (streams graph + publishes progress), RetryCoordinator (rebuilds state from DB), ProgressPublisher (Redis pub/sub), RequestStateProjector (flattens state → DB update kwargs)
- Depends on: Agent graph, database repositories, Redis client
- Used by: API routes (via worker tasks or direct invocation)

**API Layer (Request Handling):**
- Purpose: Expose HTTP endpoints and WebSocket for generation requests, validation, admin, metadata
- Location: `backend/src/chronocanvas/api/`
- Contains: 9 route modules (health, figures, timeline, generation, validation, admin, export, agents, memory), middleware (audit logging, security headers)
- Depends on: FastAPI, services, database repositories
- Used by: HTTP/WebSocket clients (React frontend)

**Database Layer (Persistence):**
- Purpose: Store historical figures, generation requests, images, validation results, audit logs, feedback
- Location: `backend/src/chronocanvas/db/`
- Contains: SQLAlchemy ORM models (Figure, GenerationRequest, GeneratedImage, ValidationResult, AuditLog, AuditFeedback), async repositories, engine factory
- Depends on: PostgreSQL, Alembic for migrations
- Used by: Services and API routes for CRUD

**Worker Layer (Background Jobs):**
- Purpose: Asynchronously execute generation and retry pipelines outside request/response cycle
- Location: `backend/src/chronocanvas/worker.py` + ARQ configuration
- Contains: WorkerSettings (job timeout 10 min, max 5 concurrent jobs), startup/shutdown hooks, task handlers
- Depends on: Redis, agent graph, services
- Used by: API routes enqueue jobs via app.state.arq_pool

**Frontend Layer (UI):**
- Purpose: Single-page app for interacting with generation, validation, figure library, audit trails, admin settings
- Location: `frontend/src/`
- Contains: Custom router (Zustand), page components, API client, React Query hooks
- Depends on: React, TypeScript, Tailwind, shadcn/ui, Vite
- Used by: Web browsers

## Data Flow

**Generation Request Flow:**

1. **Frontend:** User submits figure name + optional face image → POST /api/generate
2. **API:** Content moderation check → Create GenerationRequest DB entry → Enqueue ARQ job → Return request_id
3. **Worker:** ARQ executes `run_generation_pipeline_task(request_id, input_text, source_face_path)`
4. **Service (GenerationRunner):** Loads validation rules from DB → Creates initial AgentState → Calls graph.astream()
5. **Graph Nodes:** Sequential execution:
   - `orchestrator` — validate request, content check
   - `extraction` — LLM extracts figure metadata (name, period, region, etc.)
   - `research` — LLM researches historical context + clothing + art style
   - `face_search` — identity provider lookup (optional)
   - `prompt_generation` — LLM synthesizes image generation prompt
   - `image_generation` — Stable Diffusion/other provider generates image
   - `validation` — LLM scores image against 4-7 historical plausibility categories
   - `facial_compositing` — FaceFusion swaps face (if source face provided)
   - `export` — Save final image to /output/{request_id}/
6. **After Each Node:** GenerationRunner:
   - Projects state → DB update kwargs
   - Persists state snapshot to generation_requests.agent_trace (JSONB)
   - Publishes progress event to Redis channel generation:{request_id}
7. **WebSocket:** Frontend subscribes to /ws/generation/{request_id} → receives real-time updates
8. **Validation Failure:** If validation fails, conditional edge → `regenerate` loops back to prompt_generation (up to 2 retries)
9. **Completion:** Export node writes final image → mark request COMPLETED
10. **Human Review:** Separate workflow — failed validations appear in /api/admin/validation/queue, human can review + accept/reject

**Retry Flow (after pipeline completion):**
1. Frontend or admin triggers retry via POST /api/generate/{id}/retry?from_step={step_name}
2. API enqueues `retry_generation_pipeline_task(request_id, from_step)`
3. Worker invokes RetryCoordinator.rebuild_state_from_db() → loads prior state from agent_trace
4. Resumes graph from specified step (clear images if needed)

**State Management:**
- **Initial State:** Constructed in `run_generation_pipeline()` from request_id + input_text + optional source_face_path + loaded validation_rule_weights + pass_threshold
- **State Mutations:** Each node returns AgentState updates → LangGraph merges updates
- **State Persistence:** ProjectRequestStateProjector flattens current_agent + domain namespace data → RequestRepository.update() persists to JSONB columns
- **State Recovery:** RetryCoordinator deserializes agent_trace snapshots to resume from checkpoint

## Key Abstractions

**AgentState (TypedDict):**
- Purpose: Type-safe schema for all state flowing through the graph
- Location: `backend/src/chronocanvas/agents/state.py`
- Contains: Input (request_id, input_text), domain namespaces (extraction, research, prompt, image, validation, face, compositing, export), audit fields (llm_calls, agent_trace), control (current_agent, error, retry_count, should_regenerate)
- Pattern: Namespaced sub-dicts per domain (e.g., extraction: {figure_name, time_period, occupation, ...})

**RequestRepository:**
- Purpose: Async CRUD for GenerationRequest model, with typed update kwargs
- Location: `backend/src/chronocanvas/db/repositories/requests.py`
- Pattern: Inject session, use async context managers, return model instances or None
- Example: `await repo.update(request_id, status=..., agent_trace=..., extracted_data=...)`

**GenerationRunner:**
- Purpose: Execute graph.astream(), capture events, persist incremental state, publish progress
- Location: `backend/src/chronocanvas/services/runner.py`
- Pattern: Injected graph + repositories + publisher; async for loop over events; on each node completion → persist + broadcast
- Resilience: Catches and logs persistence errors so graph is never blocked

**ProgressPublisher:**
- Purpose: Redis pub/sub adapter for real-time WebSocket updates
- Location: `backend/src/chronocanvas/services/progress.py`
- Pattern: publish_agent() publishes {status, agent, message, ...} to generation:{request_id} channel
- Used by: GenerationRunner after each node, WebSocket handler forwards to frontend

**RequestStateProjector:**
- Purpose: Transform full AgentState → RequestRepository update kwargs (flatten namespaces)
- Location: `backend/src/chronocanvas/services/state_projector.py`
- Pattern: Extract data from nested state → map to DB column names (extracted_data, research_data, generated_prompt, etc.)

## Entry Points

**HTTP Server:**
- Location: `backend/src/chronocanvas/main.py` → create_app()
- Triggers: uvicorn startup
- Responsibilities: Initialize FastAPI, register routers, mount static file dirs (/output, /uploads), configure middleware, initialize Redis + checkpointer at lifespan

**Worker:**
- Location: `backend/src/chronocanvas/worker.py` → WorkerSettings
- Triggers: `arq worker chronocanvas.worker.WorkerSettings` command
- Responsibilities: Long-lived process that dequeues ARQ jobs, executes run/retry pipeline tasks, manages Redis connection pool

**Frontend:**
- Location: `frontend/src/main.tsx` → ReactDOM.render(App, #root)
- Triggers: Browser navigates to /
- Responsibilities: Mount React app, initialize Zustand stores, render initial page from custom router

**Batch Processing Script:**
- Location: `backend/src/chronocanvas/services/batch.py` (if exists) or ad-hoc CLI
- Triggers: Manual CLI invocation
- Responsibilities: Enqueue multiple generation tasks, poll for completion

## Error Handling

**Strategy:** Graceful degradation with audit logging

**Patterns:**

1. **Content Moderation Gate (Orchestrator):**
   - check_input() returns (is_safe, reason)
   - If unsafe, orchestrator sets state.error → conditional edge → END
   - Request marked FAILED with error_message

2. **LLM JSON Parsing Fallback (Extraction, Validation, Prompt):**
   - Try json.loads(response.content)
   - On JSONDecodeError → use sensible defaults (e.g., extraction falls back to {figure_name: input_text, ...})
   - Log warning but do not block pipeline

3. **Image Generation Timeout:**
   - Provider client may timeout
   - If error → state.error set → should_continue_after_image() → END
   - Request marked FAILED

4. **Database Persistence Errors:**
   - In GenerationRunner.run(), try/except around repo.update()
   - Log exception but continue graph execution (don't block on DB failures)
   - Upstream services responsible for eventual consistency checks

5. **Validation Node Failures:**
   - LLM scores fail validation → state.should_regenerate = True
   - Edge should_continue_after_validation() checks should_regenerate → routes to "regenerate" edge
   - Loop back to prompt_generation up to 2 retries
   - If retries exhausted → continue to facial_compositing anyway (non-blocking validation)

6. **Retry Recovery:**
   - If retry_generation_pipeline() fails to rebuild state → raise, logged, request left in incomplete state
   - Frontend should show "retry failed" and allow manual re-attempt

## Cross-Cutting Concerns

**Logging:**
- Logger per module (`logger = logging.getLogger(__name__)`)
- Log level configurable via SETTINGS.LOG_LEVEL env var
- Error handling includes logger.exception() for full tracebacks

**Validation:**
- Content moderation via check_input(text) — checks against policy keywords
- Architecture invariants via checked() decorator — runtime precondition/postcondition checks (per docs/architecture-invariants.md)
- Historical plausibility scoring via validation_node LLM

**Authentication:**
- Not fully implemented (no auth system)
- X-User-ID header available for future audit enrichment
- Framework ready: middleware can extract user context

**Audit Trail:**
- AuditLog model captures HTTP request/response metadata (method, path, status, user_id, timestamp)
- AuditFeedback model captures per-step human comments (step_name, comment, author, created_at)
- Agent trace stored as JSONB snapshots after each node → queryable for debugging
- LLM calls logged in state.llm_calls (cost tracking, prompt/response audit)

---

*Architecture analysis: 2026-02-27*
