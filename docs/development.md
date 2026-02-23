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

## Running tests

```bash
make test                            # all tests
pytest backend/tests/ -v             # backend only
pytest backend/tests/test_face_swap.py -v  # single file
npm test --prefix frontend           # frontend only
```

The backend test suite uses `pytest-asyncio`. Tests that require database access use an in-memory SQLite fixture; tests that require LLM calls mock the provider.

---

## Project structure

```
chrono-canvas/
├── frontend/                   # React + TypeScript + Vite
│   └── src/
│       ├── pages/              # One file per UI page
│       ├── components/         # Shared UI components
│       └── api/                # React Query hooks + WebSocket client
├── backend/
│   └── src/chronocanvas/
│       ├── agents/             # LangGraph graph, agent nodes, state definition
│       ├── llm/                # LLM router, provider implementations, cost tracker
│       ├── imaging/            # Image generation backends (ComfyUI, FaceFusion, mock)
│       ├── api/                # FastAPI routes, schemas, WebSocket relay, middleware
│       ├── db/                 # SQLAlchemy models, repositories, Alembic migrations
│       ├── security.py         # SSRF prevention, magic-byte validation, input sanitisation
│       └── content_moderation.py  # Input safety checks
├── cli/                        # Typer CLI
├── seed/                       # Seed data JSON + loader script
├── docker/                     # Dockerfiles and FaceFusion server wrapper
├── docs/                       # This documentation
├── docker-compose.dev.yml
├── Makefile
└── .env.example
```

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

- **Authentication / authorization** — no user accounts, no auth middleware, no RBAC. Designed for trusted local networks only.
- **Multi-tenant isolation** — single-user, single-instance. No data partitioning between users.
- **Secrets management** — API keys are stored in `.env` files. No vault integration, no rotation.
- **Queue durability** — ARQ jobs are enqueued to Redis with no persistence guarantees. A Redis restart loses pending jobs.
- **High availability / SLOs** — single-instance services, no health-based failover, no redundancy.
- **Storage** — local filesystem only. No object storage (S3, GCS), no CDN.
- **Audit log retention** — `llm_calls` and `agent_trace` JSON columns grow unbounded. No archival or pruning.

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
