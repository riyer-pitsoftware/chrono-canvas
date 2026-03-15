# ChronoCanvas — Development Guide

---

## Prerequisites

- Docker and Docker Compose
- Node.js 20+ (for frontend development outside Docker)
- Python 3.11+ (for backend development outside Docker)
- 8 GB RAM minimum; 16 GB recommended if running local LLMs

### FaceFusion (optional)

Face compositing is handled by a locally cloned copy of [FaceFusion](https://github.com/facefusion/facefusion). It is independent of the `IMAGE_PROVIDER` setting — you can use ComfyUI for portrait generation and FaceFusion for face compositing simultaneously.

1. Clone FaceFusion somewhere on your machine:
   ```bash
   git clone https://github.com/facefusion/facefusion.git ~/code/facefusion
   ```
2. Set `FACEFUSION_SOURCE_PATH` in your `.env` to the absolute path of that clone:
   ```
   FACEFUSION_SOURCE_PATH=/home/yourname/code/facefusion
   ```
3. Set `FACEFUSION_ENABLED=true` in `.env`.

The directory is bind-mounted into the `facefusion` Docker service at `/facefusion`. ONNX models are downloaded on first use into the `ff_models` Docker volume and persisted across restarts. Leave `FACEFUSION_ENABLED=false` (the default) to use a mock overlay instead.

The FaceFusion Docker service uses a compose profile and does not start by default. To include it:
```bash
docker compose -f docker-compose.dev.yml --profile facefusion up -d
```

---

## Starting the dev stack

```bash
cp .env.example .env       # configure once
make dev                   # starts db, redis, api (Docker Compose)
make frontend              # starts Vite dev server (localhost:3000)
make seed                  # loads seed figures and periods into the database
```

All Docker services are defined in `docker-compose.dev.yml`. The API server runs with hot reload enabled.

### Access points

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| API / Swagger | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

---

## Common commands

```bash
# Lifecycle
make start      # build + start all services (alias: make dev)
make stop       # stop all services (alias: make down)
make restart    # stop + start
make fresh      # full reset: volumes wiped, rebuilt, re-seeded

# Monitoring
make status     # show running containers
make logs       # tail all service logs
make logs-api   # tail API logs only
make logs-worker    # tail worker logs only
make logs-frontend  # tail frontend logs only
make health     # curl health endpoints for API and frontend

# Shell access
make shell-api  # bash into the API container
make db-shell   # psql into the database

# Development
make backend    # run API server with hot reload (outside Docker)
make frontend   # run Vite dev server
make test       # run all tests
make seed       # load seed data
make migrate    # run Alembic database migrations
make up         # start all Docker services
make down       # stop all Docker services
make build      # rebuild Docker images
make clean      # full clean including volumes and generated output
```

---

## Docker entrypoint & service startup

Both the `api` and `worker` containers use a shared entrypoint script (`docker/entrypoint.sh`) that runs before the main process:

1. **Wait for PostgreSQL** — TCP check on `db:5432` with 30-second timeout
2. **Wait for Redis** — TCP check on `redis:6379` with 30-second timeout
3. **Run Alembic migrations** — only when `RUN_MIGRATIONS=true` (set for `api`, not `worker`)
4. **Exec into the command** — `uvicorn` for api, `arq` for worker

The TCP checks use `docker/wait-for-it.sh`, a lightweight netcat-based utility. This provides a safety net on top of Docker Compose's `depends_on: condition: service_healthy` — if a service becomes briefly unavailable after its health check passes, the entrypoint will wait rather than crash.

Environment variables:

| Variable | Default | Description |
|---|---|---|
| `RUN_MIGRATIONS` | `false` | Set to `true` to run `alembic upgrade head` on startup |
| `DB_HOST` | `db` | PostgreSQL hostname for wait check |
| `DB_PORT` | `5432` | PostgreSQL port for wait check |
| `REDIS_HOST` | `redis` | Redis hostname for wait check |
| `REDIS_PORT` | `6379` | Redis port for wait check |

---

## Running tests

```bash
make test                            # all tests
pytest backend/tests/ -v             # backend only
pytest backend/tests/test_face_swap.py -v  # single file
npm test --prefix frontend           # frontend only
```

The backend test suite uses `pytest-asyncio`. Tests that require database access use an in-memory SQLite fixture; tests that require LLM calls mock the provider.

The narration pipeline has dedicated tests in `backend/tests/test_narration_audio.py` (7 tests) covering parallel TTS generation, per-panel failure isolation, audio format validation, and timeout handling.

---

## Project structure

```
chrono-canvas/
├── frontend/                   # React + TypeScript + Vite
│   └── src/
│       ├── pages/              # One file per UI page (incl. LiveStory.tsx, LiveSession.tsx)
│       ├── components/         # Shared UI components (ConfigHUD, StoryboardView, TrustCard)
│       └── api/                # React Query hooks + WebSocket client
├── backend/
│   └── src/chronocanvas/
│       ├── agents/
│       │   ├── nodes/          # Portrait pipeline nodes (10 nodes)
│       │   ├── graph.py        # Portrait pipeline LangGraph state machine
│       │   └── story/
│       │       ├── graph.py    # Story Director LangGraph state machine (13 nodes)
│       │       ├── state.py    # StoryState TypedDict
│       │       └── nodes/      # Story pipeline nodes
│       │           ├── story_orchestrator.py
│       │           ├── image_to_story.py
│       │           ├── reference_image_analysis.py
│       │           ├── character_extraction.py
│       │           ├── scene_decomposition.py
│       │           ├── scene_prompt_generation.py
│       │           ├── prompt_validation.py
│       │           ├── scene_image_generation.py
│       │           ├── storyboard_coherence.py
│       │           ├── narration_script.py
│       │           ├── narration_audio.py
│       │           ├── video_assembly.py
│       │           ├── storyboard_export.py
│       │           └── json_repair.py    # Shared 8-strategy JSON extraction
│       ├── llm/                # LLM router, provider implementations, cost tracker
│       ├── imaging/            # Image generation backends (Imagen, ComfyUI, FaceFusion, mock)
│       ├── api/
│       │   ├── routes/         # FastAPI routes
│       │   │   ├── live_story.py     # Live Story SSE endpoint
│       │   │   ├── live_session.py   # Live Session WebSocket proxy
│       │   │   ├── live_video.py     # Live Video (Veo) endpoints
│       │   │   └── live_voice.py     # Live Voice TTS + prompting
│       │   ├── schemas/        # Pydantic models
│       │   └── middleware/     # Auth gate, CORS, security headers
│       ├── db/                 # SQLAlchemy models, repositories, Alembic migrations
│       ├── security.py         # SSRF prevention, magic-byte validation, input sanitisation
│       └── content_moderation.py  # Input safety checks
├── cli/                        # Typer CLI
├── seed/                       # Seed data JSON + loader script
├── docker/                     # Dockerfiles and FaceFusion server wrapper
├── deploy/
│   ├── cloudrun/               # Cloud Run deployment scripts
│   └── gke/                    # GKE Kubernetes manifests
├── docs/                       # This documentation
├── docker-compose.dev.yml
├── Makefile
└── .env.example
```

---

## Story Pipeline module structure

The Story Director pipeline (`backend/src/chronocanvas/agents/story/`) contains 13 LangGraph nodes:

| # | Node | What it does |
|---|---|---|
| 1 | `story_orchestrator` | Validates story input, routes to image-to-story or standard flow |
| 2 | `image_to_story` | *Optional.* Extracts story concept from uploaded image via Gemini multimodal |
| 3 | `reference_image_analysis` | *Optional.* Analyzes style/location/character reference images |
| 4 | `character_extraction` | Extracts character names, physical attributes, descriptions |
| 5 | `scene_decomposition` | Breaks story into 3-8 scenes with continuity state tracking |
| 6 | `scene_prompt_generation` | Generates Imagen prompts per scene with character visual anchors |
| 7 | `prompt_validation` | Scores prompts on 4 axes, auto-repairs those scoring < 0.7 |
| 8 | `scene_image_generation` | Parallel Imagen calls via `asyncio.gather` with retry |
| 9 | `storyboard_coherence` | Gemini multimodal reviews ALL images for character/style consistency |
| 10 | `narration_script` | Gemini generates noir voiceover per panel (vision-enhanced or text-only) |
| 11 | `narration_audio` | Parallel TTS via `asyncio.gather` using Gemini TTS |
| 12 | `video_assembly` | ffmpeg stitches images + audio into MP4 (854x480 @12fps, 120s timeout) |
| 13 | `storyboard_export` | Packages images, audio, video, metadata JSON; GCS upload on Cloud Run |

**`json_repair.py`** — shared utility used by all story nodes that parse LLM JSON output. Implements 8 recovery strategies: direct parse, markdown fence extraction, trailing comma removal, unescaped control char stripping, single→double quote conversion, bare key quoting, json5 fallback, and truncation repair. This exists because Gemini 2.5 Flash thinking tokens consume the `max_output_tokens` budget, silently truncating JSON output.

---

## Live features development

### Live Story (SSE)

Live Story is an SSE endpoint (`POST /api/live-story/generate`). It works with just the API server running — no special configuration beyond `GOOGLE_API_KEY`.

```bash
# Test with curl
curl -N -X POST http://localhost:8000/api/live-story/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "A detective follows a cold trail", "num_scenes": 2}'
```

### Live Session (WebSocket)

Live Session requires the Vite dev server to proxy WebSocket connections. In `frontend/vite.config.ts`, the proxy for `/api/live-session` must have `ws: true`:

```typescript
'/api/live-session': {
  target: 'http://localhost:8000',
  ws: true,
}
```

The backend proxies to Gemini Live API using `gemini-2.5-flash-native-audio-latest`. Requires `GOOGLE_API_KEY` with Live API access.

### Live Video (Veo)

Requires `GOOGLE_API_KEY` with Veo access (`veo-3.1-generate-preview`). Cost: $0.90/scene (6s clips). Test via the frontend or:

```bash
curl -N -X POST http://localhost:8000/api/live-video/generate \
  -H "Content-Type: application/json" \
  -d '{"scenes": [{"image": "base64...", "text": "Scene description", "index": 0}]}'
```

### Live Voice

Test narration with curl:

```bash
curl -X POST http://localhost:8000/api/live-voice/narrate \
  -H "Content-Type: application/json" \
  -d '{"text": "The rain fell like a confession nobody asked for."}' \
  --output narration.wav
```

---

## SDK pins and constraints

### google-genai < 1.67

The `google-genai` SDK is pinned to `<1.67`. Version 1.67 drops `thought_signature` from chat history objects, which breaks multi-turn image generation in Live Story. This pin is in `requirements.txt`.

### Thinking config suppresses image generation

Gemini's `thinking_config` parameter (used for chain-of-thought reasoning) suppresses image output when enabled. Never use `thinking_config` in calls that expect image generation. Live Story uses `thinking_level="MINIMAL"` only for gemini-3.1+ models.

### Thinking tokens consume max_output_tokens

Gemini 2.5 Flash's internal thinking tokens count against the `max_output_tokens` budget. If you request 2000 max tokens and the model "thinks" for 1500 tokens, only 500 tokens remain for the actual response — often truncating JSON output mid-value. All story pipeline nodes use 4096-8192 max_tokens to accommodate this, and all JSON parsing goes through `json_repair.extract_and_parse_json()`.

---

## Database migrations

Migrations are managed with Alembic.

```bash
# Apply pending migrations
make migrate

# Create a new migration after changing a SQLAlchemy model
docker compose -f docker-compose.dev.yml exec api \
  alembic revision --autogenerate -m "describe your change"
```

Migration files live in `backend/src/chronocanvas/db/migrations/versions/`.

---

## Adding a new LLM provider

1. Create `backend/src/chronocanvas/llm/providers/your_provider.py` implementing `LLMProvider`
2. Override `generate()` for standard completions
3. Override `generate_stream()` to enable token streaming — call `await on_token(chunk)` per token; the base class falls back to `generate()` if not overridden
4. Register the provider in `backend/src/chronocanvas/llm/router.py`
5. Add the required environment variables to `.env.example` with descriptions

---

## Adding a new agent node

1. Create `backend/src/chronocanvas/agents/nodes/your_agent.py`
   - Accept `state: AgentState` as input
   - Return a partial `AgentState` dict
   - Append an entry to `agent_trace`
2. Register the node in `backend/src/chronocanvas/agents/graph.py`
3. If the agent needs LLM routing, add a `TaskType` entry in `backend/src/chronocanvas/llm/router.py`

---

## Adding a new image backend

1. Create `backend/src/chronocanvas/imaging/your_backend.py` implementing `ImageGenerator`
2. Override `generate()` returning `ImageResult`
3. Override `is_available()` to return a health check result
4. Register the backend in `backend/src/chronocanvas/imaging/__init__.py`
5. Add configuration variables to `.env.example`

---

## Not production-ready

ChronoCanvas is a prototype and research system. The following are explicitly out of scope:

- **Authentication / authorization** — optional password gate via `APP_PASSWORD` env var with HMAC-signed session cookies (7-day TTL), but no user accounts, no RBAC. Designed for demo/hackathon protection, not production auth.
- **Multi-tenant isolation** — single-user, single-instance. No data partitioning between users.
- **Secrets management** — API keys are stored in `.env` files. No vault integration, no rotation.
- **Queue durability** — ARQ jobs are enqueued to Redis with no persistence guarantees. A Redis restart loses pending jobs.
- **High availability / SLOs** — single-instance services, no health-based failover, no redundancy.
- **Storage** — local filesystem in Docker; GCS upload on Cloud Run deployment. No CDN.
- **Audit log retention** — `llm_calls` and `agent_trace` JSON columns grow unbounded. No archival or pruning.

ChronoCanvas is deployed on **Cloud Run** (API, worker, frontend) with Cloud SQL and Memorystore Redis for the hackathon, but the deployment is demo-grade — no auto-scaling policies, no monitoring alerts, no SLOs.

If you are evaluating ChronoCanvas as an architecture reference, these are the areas you would harden for production use.

---

## Code style

- Backend: Python 3.11+, `ruff` for linting and formatting, `mypy` for type checking
- Frontend: ESLint + Prettier with the project's `.eslintrc` config
- Commit messages: imperative mood, present tense, reference bead IDs where applicable

---

## CLI

The CLI is a separate package in `cli/`. Install it in development mode:

```bash
pip install -e cli/
```

```bash
chronocanvas add figure          # Add a historical figure
chronocanvas generate            # Generate a portrait from text
chronocanvas batch               # Batch generation from a JSON file
chronocanvas status <id>         # Check generation status
chronocanvas download <id>       # Download generated image
chronocanvas list figures        # List figures with search/filter
chronocanvas list generations    # List generation requests
chronocanvas validate <id>       # Show validation results
chronocanvas agents list         # List available agents
chronocanvas agents llm-status   # Check LLM provider availability
chronocanvas agents costs        # Show LLM cost summary
```
