# Codebase Structure

**Analysis Date:** 2026-02-27

## Directory Layout

```
chrono-canvas/
├── backend/                           # FastAPI server + worker
│   ├── src/chronocanvas/              # Main package (101 .py files)
│   │   ├── agents/                    # LangGraph pipeline
│   │   │   ├── nodes/                 # 9 agent node implementations
│   │   │   ├── graph.py               # Graph build & singleton compilation
│   │   │   ├── state.py               # AgentState TypedDict schema
│   │   │   ├── decisions.py           # Conditional edge functions
│   │   │   ├── invariants.py          # Runtime architecture validation
│   │   │   └── checkpointer.py        # State persistence (MemorySaver → AsyncPostgresSaver)
│   │   ├── api/                       # FastAPI routes & schemas
│   │   │   ├── routes/                # 9 route modules (health, figures, generation, etc.)
│   │   │   ├── schemas/               # Pydantic request/response models
│   │   │   ├── router.py              # API router registration
│   │   │   ├── middleware.py          # Audit logging middleware
│   │   │   └── websocket.py           # WebSocket handler for progress streaming
│   │   ├── db/                        # SQLAlchemy ORM
│   │   │   ├── models/                # Declarative models (Figure, GenerationRequest, Image, etc.)
│   │   │   ├── repositories/          # Async repository CRUD classes
│   │   │   ├── engine.py              # AsyncEngine + session factory
│   │   │   └── base.py                # Base class (UUIDMixin, TimestampMixin)
│   │   ├── services/                  # Business logic
│   │   │   ├── generation.py          # run_generation_pipeline, retry_generation_pipeline
│   │   │   ├── runner.py              # GenerationRunner (graph executor + state persister)
│   │   │   ├── retry.py               # RetryCoordinator (state recovery from checkpoints)
│   │   │   ├── progress.py            # ProgressPublisher (Redis pub/sub)
│   │   │   ├── state_projector.py     # AgentState → DB update kwargs mapper
│   │   │   ├── image_recorder.py      # ImageAttemptRecorder (captures images per attempt)
│   │   │   ├── validation.py          # Validation result persistence
│   │   │   └── batch.py               # Batch generation orchestration (if present)
│   │   ├── llm/                       # LLM routing & integration
│   │   │   ├── base.py                # TaskType enum, LLMResponse dataclass
│   │   │   └── router.py              # get_llm_router() — pluggable provider selection
│   │   ├── imaging/                   # Image generation & composition
│   │   │   ├── facefusion.py          # Face swap client
│   │   │   └── provider.py            # Image generation provider abstraction
│   │   ├── main.py                    # FastAPI app factory + lifespan
│   │   ├── worker.py                  # ARQ worker config + job task handlers
│   │   ├── config.py                  # Settings (pydantic-settings)
│   │   ├── security.py                # Path confinement, content moderation
│   │   ├── dependencies.py            # FastAPI dependency injection
│   │   ├── redis_client.py            # Redis client singleton
│   │   └── service_registry.py        # Service initialization (DI container)
│   ├── alembic/                       # Database migrations
│   │   ├── versions/                  # Migration files (001, 002, 003, ...)
│   │   └── env.py                     # Alembic environment config
│   ├── tests/                         # Test suite (152 passing tests)
│   │   ├── test_agents/               # Agent node & graph tests
│   │   ├── test_api/                  # API endpoint tests
│   │   ├── test_db/                   # Database & repository tests
│   │   ├── test_integration/          # End-to-end generation pipeline tests
│   │   ├── test_llm/                  # LLM mock & routing tests
│   │   └── conftest.py                # Pytest fixtures (session-scoped OUTPUT_DIR, async support)
│   ├── pyproject.toml                 # Poetry project, dependencies, pytest config
│   └── alembic.ini                    # Alembic config
├── frontend/                          # React + Vite
│   ├── src/                           # React source (38 .ts/.tsx files)
│   │   ├── pages/                     # Page components (Dashboard, Generate, Validate, Admin, AuditDetail, etc.)
│   │   ├── components/                # Reusable UI components (Layout, StatusBadge, ProgressGauge, etc.)
│   │   ├── api/                       # API client & TypeScript types
│   │   │   ├── client.ts              # Fetch wrapper (get, post, put, delete, upload)
│   │   │   └── types.ts               # TypeScript interfaces (GenerationResponse, AuditLog, etc.)
│   │   ├── stores/                    # Zustand stores (navigation, state management)
│   │   ├── lib/                       # Utilities (formatting, time parsing, etc.)
│   │   ├── App.tsx                    # Custom router (path-based, no react-router)
│   │   ├── main.tsx                   # React entry point
│   │   └── index.css                  # Tailwind imports
│   ├── package.json                   # npm dependencies (React Query, Tailwind, shadcn/ui)
│   ├── vite.config.ts                 # Vite build config
│   └── tsconfig.json                  # TypeScript config
├── deploy/                            # Deployment configurations
│   └── gke/                           # Google Kubernetes Engine manifests
│       ├── manifests/                 # K8s YAML (Deployments, Services, StatefulSets, ConfigMaps)
│       └── scripts/                   # Setup scripts (setup-gcp.sh)
├── docker/                            # Container definitions
│   ├── Dockerfile.api                 # FastAPI image
│   ├── Dockerfile.frontend            # React + nginx image
│   ├── Dockerfile.facefusion          # FaceFusion service image
│   ├── entrypoint.sh                  # Script to handle env var injection
│   ├── nginx.conf                     # Nginx reverse proxy config
│   └── facefusion_server.py           # FaceFusion wrapper server
├── docs/                              # Documentation
│   ├── architecture-invariants.md     # Executable invariants (state contracts)
│   ├── api.md                         # API endpoint reference
│   ├── development.md                 # Developer setup guide
│   ├── deployment-hardening.md        # Security & scaling hardening
│   ├── educator-playbooks/            # Teaching guides (inquiry-lesson, validation-debate, batch-comparison)
│   └── partner-demos/                 # Partner-facing documentation (digital-humanities-lab, heritage-digitization)
├── seed/                              # Database seeding
│   ├── figures.json                   # Historical figures seed data
│   ├── periods.json                   # Time periods seed data
│   ├── clothing.json                  # Clothing reference seed data
│   ├── timeline_figures.json          # Timeline figure relationships
│   ├── validation_rules.json          # Default validation categories + weights
│   └── load_seed.py                   # Script to load seed data
├── eval/                              # Evaluation framework
│   ├── evalset/                       # 30-case eval dataset
│   │   └── rubric.md                  # Assessment rubric for raters
│   ├── configs/                       # Eval run configurations
│   ├── raters/                        # Rater implementations (Claude vision, human, etc.)
│   ├── ratings/                       # Aggregated rating results
│   ├── runs/                          # Per-run output directories (audit logs, generated images, ratings)
│   └── scripts/                       # Eval orchestration scripts
├── output/                            # Generated images (filesystem storage)
│   └── {request_id}/                  # Per-request subdirectory
│       ├── generated.png              # Generated portrait
│       ├── swapped.png                # Face-swapped version (if face provided)
│       └── export.png                 # Final export
├── uploads/                           # Uploaded files
│   └── faces/                         # User-provided face images ({face_id}.jpg, etc.)
├── blog/                              # Blog post series (6 posts, gitignored)
│   ├── 01-the-vision.md
│   ├── 02-the-agent-pipeline.md
│   ├── 03-making-ai-write-like-a-historian.md
│   ├── 04-teaching-ai-to-see-faces.md
│   ├── 05-the-audit-trail.md
│   └── 06-running-it-all.md
├── notes/                             # Planning & design docs
│   ├── plan.md                        # Core development plan
│   ├── plan-gke-deployment.md         # K8s deployment strategy (gitignored)
│   ├── prd-*.md                       # Product requirement docs
│   └── code_review_*.md               # Code review summaries
├── scripts/                           # Utility scripts
│   └── check_env_keys.py              # Environment variable validation
├── .planning/                         # GSD planning artifacts
│   └── codebase/                      # Codebase analysis docs (ARCHITECTURE.md, STRUCTURE.md, etc.)
├── .github/workflows/                 # GitHub Actions CI/CD
│   └── cd-gke.yml                     # Auto-deploy to GKE on merge
└── README.md                          # Project overview
```

## Directory Purposes

**backend/src/chronocanvas/agents/**
- Purpose: LangGraph-based agentic orchestration
- Contains: 9 node implementations, graph builder, state schema, conditional routing logic, runtime invariant checks
- Key files: `graph.py` (build_graph + singleton), `state.py` (AgentState TypedDict), `nodes/*.py` (9 agent implementations)

**backend/src/chronocanvas/api/**
- Purpose: HTTP API and WebSocket handler
- Contains: 9 route modules, Pydantic schemas, FastAPI middleware, WebSocket handler
- Key files: `router.py` (route registration), `routes/generation.py` (POST /api/generate), `routes/admin.py` (validation admin)

**backend/src/chronocanvas/db/**
- Purpose: SQLAlchemy ORM, migrations, persistence
- Contains: 12+ ORM models, async repository classes, engine factory, migration versions
- Key files: `models/request.py` (GenerationRequest), `repositories/requests.py` (CRUD), `engine.py` (AsyncSession factory)

**backend/src/chronocanvas/services/**
- Purpose: Business logic orchestration
- Contains: Graph executor, retry logic, state persistence, progress publishing, image recording
- Key files: `generation.py` (entry point functions), `runner.py` (streaming executor), `retry.py` (state recovery)

**backend/tests/**
- Purpose: Automated test suite
- Contains: 152 passing tests across 4 categories
- Key files: `conftest.py` (shared fixtures, temp directories), `test_integration/` (pipeline tests)

**frontend/src/pages/**
- Purpose: Top-level page components (routed by App.tsx)
- Contains: Dashboard, Generate, Validate, Admin, AuditDetail, AuditList, Timeline, FigureLibrary, etc.
- Naming: PascalCase component names (e.g., Generate.tsx, AdminPanel.tsx)

**frontend/src/api/**
- Purpose: API client and type definitions
- Contains: Fetch wrapper (api.get/post/put/delete/upload), TypeScript interfaces for all responses
- Key files: `client.ts` (fetch wrapper with error handling), `types.ts` (TypeScript interfaces)

**frontend/src/stores/**
- Purpose: Zustand state management
- Contains: Navigation store (useNavigation), other global state (if any)
- Pattern: create() factory per store, exported as useStoreName hook

**docs/**
- Purpose: Developer and user-facing documentation
- Contains: Architecture specs, API reference, deployment hardening, educator playbooks, partner demos
- Key files: `architecture-invariants.md` (executable contracts), `development.md` (setup), `api.md` (endpoint ref)

**deploy/gke/**
- Purpose: Google Kubernetes Engine infrastructure
- Contains: K8s manifests (Deployments, StatefulSets, Services, ConfigMaps, Ingress, ManagedCertificate), setup scripts
- Key files: `manifests/` (YAML files), `scripts/setup-gcp.sh` (cluster bootstrap)

**eval/**
- Purpose: Evaluation framework for generated images
- Contains: 30-case evaluation dataset, rater implementations, rating aggregations, run logs
- Key files: `evalset/` (test cases), `raters/` (Claude vision + human), `runs/` (per-run outputs)

## Key File Locations

**Entry Points:**

- **Backend HTTP Server:** `backend/src/chronocanvas/main.py` → create_app() → FastAPI instance
- **Backend Worker:** `backend/src/chronocanvas/worker.py` → WorkerSettings (ARQ configuration)
- **Frontend:** `frontend/src/main.tsx` → ReactDOM.render(App) + `frontend/src/App.tsx` (custom router)
- **Graph Execution:** `backend/src/chronocanvas/services/generation.py` → run_generation_pipeline()

**Configuration:**

- `backend/src/chronocanvas/config.py` — Pydantic Settings (database URL, Redis URL, output dirs, log level, feature flags)
- `frontend/package.json` — npm dependencies, build scripts
- `backend/pyproject.toml` — Poetry dependencies, test config
- `docker/entrypoint.sh` — Env var injection for containerized deployments
- `deploy/gke/manifests/` — K8s ConfigMaps (database URL, Redis URL, image endpoints)

**Core Logic:**

- **Graph Definition:** `backend/src/chronocanvas/agents/graph.py` → build_graph() + get_compiled_graph()
- **State Schema:** `backend/src/chronocanvas/agents/state.py` → AgentState TypedDict with domain namespaces
- **Pipeline Runner:** `backend/src/chronocanvas/services/runner.py` → GenerationRunner.run(initial_state, config, channel)
- **Retry Logic:** `backend/src/chronocanvas/services/retry.py` → RetryCoordinator.rebuild_state_from_db()
- **Validation Admin:** `backend/src/chronocanvas/api/routes/admin.py` → GET/PUT /api/admin/validation/rules, queue, accept/reject

**Testing:**

- **Test Fixtures:** `backend/tests/conftest.py` — Session-scoped temp dirs, async fixtures, mocked services
- **Integration Tests:** `backend/tests/test_integration/test_generation_pipeline.py` — Full pipeline execution
- **Agent Tests:** `backend/tests/test_agents/` — Individual node tests

## Naming Conventions

**Python Files:**
- Module names: `snake_case.py` (e.g., `generation.py`, `state_projector.py`)
- Class names: `PascalCase` (e.g., `GenerationRunner`, `RequestRepository`, `AgentState`)
- Function names: `snake_case` (e.g., `run_generation_pipeline()`, `should_continue_after_validation()`)
- Private methods/functions: `_snake_case` (e.g., `_make_runner()`, `_rebuild_state_from_db()`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `VALID_RETRY_STEPS`, `EXTRACTION_PROMPT`)

**TypeScript/React Files:**
- Component files: `PascalCase.tsx` (e.g., `Generate.tsx`, `Admin.tsx`, `AuditDetail.tsx`)
- Utility/hook files: `camelCase.ts` (e.g., `client.ts`, `utils.ts`, `useGeneration.ts`)
- Store files: `camelCase.ts` with `use` prefix for hooks (e.g., `useNavigation()`)
- Interface/type names: `PascalCase` (e.g., `GenerationResponse`, `AuditLog`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `BASE_URL`)

**API Routes:**
- Endpoint pattern: `/api/{resource}/{id?}/{action?}`
- HTTP methods: POST (create), GET (read), PUT (update), DELETE (delete)
- Examples: `POST /api/generate`, `GET /api/generate/{id}`, `PUT /api/admin/validation/rules`

## Where to Add New Code

**New Feature (e.g., new agent node):**
1. **Agent Node:** Create `backend/src/chronocanvas/agents/nodes/{node_name}.py`
   - Implement async function `{node_name}_node(state: AgentState) -> AgentState`
   - Update `backend/src/chronocanvas/agents/state.py` with new TypedDict sub-state if needed
2. **Graph Integration:** Update `backend/src/chronocanvas/agents/graph.py`
   - Import new node
   - Add graph.add_node() call
   - Add graph.add_edge() or add_conditional_edges()
3. **Tests:** Create `backend/tests/test_agents/test_{node_name}.py`

**New API Route:**
1. Create `backend/src/chronocanvas/api/routes/{resource}.py`
   - Define APIRouter with appropriate prefix
   - Import from `api/schemas/` for Pydantic models
2. Register in `backend/src/chronocanvas/api/router.py` → api_router.include_router()
3. Create `backend/src/chronocanvas/api/schemas/{resource}.py` for request/response models
4. Add tests in `backend/tests/test_api/test_{resource}.py`

**New Database Model:**
1. Create `backend/src/chronocanvas/db/models/{entity}.py`
   - Inherit from Base, UUIDMixin, TimestampMixin as appropriate
   - Use SQLAlchemy ORM mapped_column with type hints
2. Create `backend/src/chronocanvas/db/repositories/{entity}.py`
   - Implement async CRUD methods
3. Create Alembic migration: `alembic revision -m "add {entity} table"` → populate `alembic/versions/{version}_{message}.py`
4. Update `backend/tests/conftest.py` to create table in test fixtures if needed

**New Frontend Page:**
1. Create `frontend/src/pages/{PageName}.tsx`
   - Export default component matching filename
2. Import in `frontend/src/App.tsx` → add to getPage() switch
3. Define route: Add case in getPage() switch statement
4. Create `frontend/src/api/types.ts` entries for API response types
5. Use `api.get()` / `api.post()` in component for data fetching

**New Validation Category (admin feature):**
1. Add category name to `seed/validation_rules.json`
2. Update `backend/src/chronocanvas/agents/nodes/validation.py` → _DEFAULT_CATEGORY_DESCRIPTIONS
3. Seed DB: `python backend/src/load_seed.py` or create migration to insert
4. Frontend automatically picks up from API response (no hardcoding needed)

**Utility/Service:**
- Non-domain-specific: `backend/src/chronocanvas/{module_name}.py`
- Domain-specific: `backend/src/chronocanvas/services/{service_name}.py`
- Example: `security.py`, `content_moderation.py`, `progress.py`

## Special Directories

**backend/output/:**
- Purpose: Filesystem storage for generated images
- Generated: Yes (created by export node, served as StaticFiles)
- Committed: No (gitignored, ephemeral)
- Cleanup: Manual or by deployment process; images older than N days can be purged

**backend/uploads/faces/:**
- Purpose: Temporary storage for user-uploaded face images
- Generated: Yes (users upload via POST /api/faces)
- Committed: No (gitignored)
- Cleanup: After generation completes or explicit user deletion

**backend/alembic/versions/:**
- Purpose: Database migration history
- Generated: Yes (via `alembic revision` command)
- Committed: Yes (all migrations tracked in git)
- Pattern: Each file is {version}_{description}.py with up()/down() functions

**eval/runs/**
- Purpose: Evaluation run outputs (per-case audit logs, generated images, ratings)
- Generated: Yes (created by eval scripts)
- Committed: No (gitignored, evaluation artifacts only)
- Naming: Timestamp + config ID (e.g., 2026-02-27T12-18-21Z_CCV1-001_baselineA)

**frontend/dist/:**
- Purpose: Built static assets (HTML, CSS, JS bundles)
- Generated: Yes (via `npm run build`)
- Committed: No (gitignored, rebuilt on deploy)

**.planning/codebase/:**
- Purpose: GSD codebase analysis documents
- Generated: Yes (created by /gsd:map-codebase)
- Committed: Yes (tracked in git for reference)
- Contains: ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, STACK.md, INTEGRATIONS.md, CONCERNS.md

---

*Structure analysis: 2026-02-27*
