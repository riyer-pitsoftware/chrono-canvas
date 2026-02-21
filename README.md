# ChronoCanvas

Agentic historical education toolkit that generates historically accurate portraits of historical figures using a 7-agent AI pipeline, multi-LLM routing, and pluggable image generation.

Built for educators, historians, and content creators who need visually compelling, period-accurate character depictions — runs entirely on your own hardware with no cloud dependency.

---

## Features

- **7-Agent Pipeline** — Orchestrator → Extraction → Research → Prompt Generation → Image Generation → Validation → Export
- **Multi-LLM Routing** — Route tasks to Claude, OpenAI, or Ollama by task type; automatic fallback chain if a provider is unavailable
- **Real-time Token Streaming** — LLM responses stream token-by-token to the UI via WebSocket, with a blinking cursor while the model generates
- **Historical Accuracy Validation** — Automated 0–100 scoring; generations below 70 are automatically retried (up to 2 times) with a corrected prompt
- **Face Swap** — Upload a reference photo to replace the generated face using FaceFusion
- **Figures Library** — 100 pre-loaded historical figures across Ancient through Modern eras; add custom figures via UI or CLI
- **Full Audit Trail** — Every LLM call (prompt, response, tokens, cost, latency) is logged and viewable in the audit detail page
- **Pluggable Image Backend** — Switch between mock, Stable Diffusion, or FaceFusion via a single env var
- **CLI** — Full command-line interface for automation and batch generation

---

## Quick Start

```bash
cp .env.example .env   # configure API keys and providers
make dev               # start all services via Docker Compose
open http://localhost:3000
```

**Requirements:** Docker, Docker Compose, 8 GB RAM minimum. API keys are optional — Ollama-only mode works for all tasks.

---

## Architecture

| Component | Technology | Role |
|---|---|---|
| Frontend | React + TypeScript + Vite + Tailwind + shadcn/ui | Web UI |
| Backend | FastAPI + LangGraph + SQLAlchemy (asyncpg) | API server + agent orchestration |
| Database | PostgreSQL 16 | Persistent storage |
| Cache | Redis 7 | Agent state checkpointing + pub/sub for streaming |
| Image Gen | Mock / Stable Diffusion / FaceFusion | Portrait generation |
| CLI | Typer + Rich | Command-line interface |

---

## Agent Pipeline

| # | Agent | Provider | What It Does |
|---|---|---|---|
| 1 | Orchestrator | Ollama | Creates execution plan, delegates to agents |
| 2 | Extraction | Ollama | Parses input text → structured figure JSON |
| 3 | Research | Claude | Enriches figure with historical context (streams tokens) |
| 4 | Prompt Generation | Claude | Crafts period-accurate SDXL prompt (streams tokens) |
| 5 | Image Generation | — | Produces portrait via configured image backend |
| 6 | Validation | Ollama | Scores historical accuracy 0–100; triggers retry if < 70 |
| 7 | Export | — | Packages PNG + JSON metadata for download |

---

## Configuration

All configuration is via `.env`. Copy `.env.example` to get started.

### LLM Providers

| Variable | Description |
|---|---|
| `OLLAMA_BASE_URL` | Ollama endpoint (default: `http://localhost:11434`) |
| `OLLAMA_MODEL` | Model name (default: `llama3.1:8b`) |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude |
| `CLAUDE_MODEL` | Claude model (default: `claude-sonnet-4-5-20250929`) |
| `OPENAI_API_KEY` | OpenAI API key |
| `OPENAI_MODEL` | OpenAI model (default: `gpt-4o`) |
| `DEFAULT_LLM_PROVIDER` | Fallback provider (`ollama`) |

### Image Generation

| Variable | Description |
|---|---|
| `IMAGE_PROVIDER` | `mock` (default), `stable_diffusion`, or `facefusion` |
| `SD_API_URL` | Stable Diffusion API endpoint |
| `FACEFUSION_API_URL` | FaceFusion API endpoint |

### Database & Cache

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (asyncpg) |
| `REDIS_URL` | Redis connection string |

---

## Web UI

| Page | Purpose |
|---|---|
| Dashboard | Recent generations, queue status, cost summary |
| Figures | Browse, search, and add historical figures |
| Generate | Text input → pipeline with live token streaming + progress |
| Validate | Review accuracy scores and anachronism flags |
| Export | Download portraits and metadata |
| Audit | Per-generation LLM call log with prompts, tokens, and cost |
| Admin | Agent health, LLM provider status, cost tracking |

---

## CLI

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

---

## API

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/generate` | Start a generation from text or figure ID |
| `GET` | `/api/generate/{id}` | Get generation status and progress |
| `GET` | `/api/generate/{id}/results` | Get completed results |
| `GET` | `/api/figures` | List figures (search, filter by period) |
| `GET` | `/api/figures/{id}` | Get figure details |
| `POST` | `/api/figures` | Create a figure |
| `GET` | `/api/export/{id}` | Download portrait + metadata |
| `GET` | `/api/agents/status` | Agent health |
| `GET` | `/api/agents/metrics` | LLM usage and cost metrics |
| `WS` | `/ws/generation/{id}` | Real-time events (token stream, image steps) |

### WebSocket Message Types

| `type` | Fields | Description |
|---|---|---|
| `llm_token` | `agent`, `token` | Single streamed token from an LLM call |
| `llm_stream_end` | `agent` | LLM stream complete for this agent |
| `image_progress` | `step`, `total` | Diffusion step progress |
| `completed` / `failed` | `status` | Terminal generation event |

---

## Development

```bash
make backend    # Run API server (uvicorn, hot reload)
make frontend   # Run Vite dev server
make test       # Run all tests
make seed       # Load 100 seed figures into the database
make migrate    # Run Alembic database migrations
```

### Docker

```bash
make up     # Start all services (db, redis, api, frontend)
make down   # Stop all services
make build  # Rebuild images
make clean  # Full clean including volumes
```

---

## Project Structure

```
chrono-canvas/
├── frontend/              # React + TypeScript + Vite
│   └── src/
│       ├── pages/         # One file per page
│       ├── components/    # Shared UI components
│       └── api/           # React Query hooks + WebSocket
├── backend/               # FastAPI + LangGraph
│   └── src/chronocanvas/
│       ├── agents/        # Agent nodes + LangGraph workflow
│       ├── llm/           # LLM router, providers, cost tracker
│       ├── api/           # REST endpoints + WebSocket relay
│       └── db/            # SQLAlchemy models + migrations
├── cli/                   # CLI (Typer)
├── seed/                  # Seed data (102 figures, 12 periods)
├── docker/                # Dockerfiles
└── docker-compose.yml
```

### Adding a New LLM Provider

1. Create `backend/src/chronocanvas/llm/providers/your_provider.py` implementing `LLMProvider`
2. Override `generate()` for standard completions
3. Override `generate_stream()` to enable token streaming — call `await on_token(chunk)` per token; the base class falls back to `generate()` if not overridden
4. Register it in `backend/src/chronocanvas/llm/router.py`
5. Add env vars to `.env.example`

### Adding a New Agent

1. Create `backend/src/chronocanvas/agents/nodes/your_agent.py`
2. Register the node in `backend/src/chronocanvas/agents/graph.py`
3. Add a `TaskType` entry to `backend/src/chronocanvas/llm/router.py` if it needs LLM routing

---

## Access Points

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| API / Swagger | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |
