# ChronoCanvas — Product Requirements Document

## Overview

ChronoCanvas is an open-source, agentic toolkit that generates historically-accurate portraits of historical figures using a 7-agent AI pipeline. It is built for educators, historians, and content creators who need visually compelling, period-accurate character depictions.

**Deployment model:** Local Docker Compose stack with no cloud dependency — runs entirely on your hardware with optional cloud LLM providers.

---

## Architecture

```
User (Web UI / CLI)
  │
  ▼
FastAPI Backend
  │
  ▼
LangGraph Orchestrator
  │
  ├─► Extraction Agent ──► Research Agent ──► Prompt Generation Agent
  │                                                │
  │                                                ▼
  │                                         Image Generation Agent
  │                                                │
  │                                                ▼
  │                                         Validation Agent
  │                                                │
  │                                                ▼
  └──────────────────────────────────────── Export Agent
```

| Component | Technology | Role |
|---|---|---|
| Frontend | React + TypeScript + Vite | Web interface for all user interactions |
| Backend | FastAPI + LangGraph | API server, agent orchestration, business logic |
| Database | PostgreSQL (asyncpg) | Persistent storage for figures, generations, metadata |
| Cache | Redis | Agent state checkpointing, task queues |
| Image | Pluggable (Mock / Stable Diffusion / FaceFusion) | Portrait generation and face consistency |

---

## Agent Pipeline

| # | Agent | What It Does | LLM Provider | Inputs → Outputs |
|---|---|---|---|---|
| 1 | **Orchestrator** | Receives requests, creates execution plan, delegates to agents | Ollama | User request → execution plan |
| 2 | **Extraction** | Parses text into structured figure data (name, period, traits) | Ollama | Raw text → structured figure JSON |
| 3 | **Research** | Enriches figure data with historical context and facts | Claude | Structured figure → enriched context |
| 4 | **Prompt Generation** | Creates period-accurate image generation prompts | Claude | Enriched context → SD prompt |
| 5 | **Image Generation** | Produces portrait via Stable Diffusion / FaceFusion | — | SD prompt → raw image |
| 6 | **Validation** | Scores historical accuracy (0–100) and flags anachronisms | Ollama | Image + context → score + notes |
| 7 | **Export** | Packages final portrait with metadata for download | — | Validated image → PNG + JSON |

> **Regeneration:** If validation scores below 70, the pipeline regenerates with a corrected prompt. Maximum 2 retries before marking as failed.

---

## Features

### Figures Library
Browse and search 100 pre-loaded historical figures spanning Ancient through Modern eras. Add custom figures via the UI or CLI.

### Generation
Enter a text description or select an existing figure → the autonomous 7-agent pipeline produces a portrait with real-time progress tracking at each stage.

### Validation
Automated historical accuracy scoring on a 0–100 scale. Figures scoring 70+ pass automatically. Flagged anachronisms are displayed for review.

### Export
Download the finished portrait as PNG alongside a JSON metadata file containing the figure data, prompt used, validation score, and generation parameters.

### Admin
Monitor agent health, LLM provider status, and cost tracking. View generation queue and system metrics.

---

## Configuration

All configuration is via environment variables in `.env`. Copy `.env.example` to get started.

### Database
| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (asyncpg) |
| `REDIS_URL` | Redis connection string for cache and agent state |

### LLM Providers
| Variable | Description |
|---|---|
| `OLLAMA_BASE_URL` | Ollama API endpoint (default: `http://localhost:11434`) |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude (optional) |
| `OPENAI_API_KEY` | OpenAI API key (optional) |
| `DEFAULT_LLM_PROVIDER` | Default provider when no routing match (`ollama`) |
| `OLLAMA_MODEL` | Ollama model to use (default: `llama3.1:8b`) |
| `CLAUDE_MODEL` | Claude model to use (default: `claude-sonnet-4-5-20250929`) |
| `OPENAI_MODEL` | OpenAI model to use (default: `gpt-4o`) |

### LLM Routing
Default task-to-provider mapping:

| Task | Default Provider | Reason |
|---|---|---|
| Extraction | Ollama | Fast, free, sufficient for structured parsing |
| Research | Claude | Best reasoning for historical enrichment |
| Prompt Generation | Claude | Strong creative + accurate prompt crafting |
| Validation | Ollama | Cost-effective for scoring checks |
| Orchestration | Ollama | Lightweight coordination logic |
| General | Ollama | Default fallback, no API cost |

### Image Generation
| Variable | Description |
|---|---|
| `IMAGE_PROVIDER` | Image backend: `mock` (default), `stable_diffusion`, or `facefusion` |
| `SD_API_URL` | Stable Diffusion API endpoint |
| `FACEFUSION_API_URL` | FaceFusion API endpoint |

### Rate Limiting
| Variable | Description |
|---|---|
| `RATE_LIMIT_RPM` | API requests per minute (default: `60`) |
| `LLM_MAX_CONCURRENT` | Max concurrent LLM calls (default: `5`) |

### Storage
| Variable | Description |
|---|---|
| `UPLOAD_DIR` | Directory for user uploads (default: `./uploads`) |
| `OUTPUT_DIR` | Directory for generated output (default: `./output`) |

---

## Interfaces

### Web UI

| Page | Purpose |
|---|---|
| Dashboard | Overview: recent generations, queue status, cost summary |
| Figures | Browse/search/add historical figures |
| Generate | Text input → pipeline execution with progress tracking |
| Validate | Review validation scores and anachronism flags |
| Export | Download portraits and metadata |
| Guide | In-app documentation and reference |
| Admin | Agent health, LLM metrics, cost tracking |

### CLI

| Command | Description |
|---|---|
| `chronocanvas add figure` | Add a historical figure to the database |
| `chronocanvas generate` | Generate a portrait from a text description |
| `chronocanvas batch` | Run batch generation from a JSON file |
| `chronocanvas status` | Check the status of a generation request |
| `chronocanvas download` | Download the generated image |
| `chronocanvas list figures` | List historical figures with search/filter |
| `chronocanvas list generations` | List generation requests |
| `chronocanvas validate` | Show validation results for a generation |
| `chronocanvas agents list` | List all available agents |
| `chronocanvas agents llm-status` | Check LLM provider availability |
| `chronocanvas agents costs` | Show LLM cost summary |

### API

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/generate` | Start a new generation from text or figure ID |
| `GET` | `/api/generate/{id}` | Get generation status and progress |
| `GET` | `/api/generate/{id}/results` | Get completed generation results |
| `GET` | `/api/figures` | List figures (supports search, filter by period) |
| `GET` | `/api/figures/{id}` | Get full figure details |
| `POST` | `/api/figures` | Create a new figure |
| `GET` | `/api/export/{id}` | Download portrait + metadata |
| `GET` | `/api/agents/status` | Agent health status |
| `GET` | `/api/agents/metrics` | LLM usage and cost metrics |

---

## Deployment

### Quick Start

```bash
cp .env.example .env      # Configure environment
make dev                   # Start all services via Docker Compose
open http://localhost:3000  # Open the web UI
```

### Requirements

- **Docker** and Docker Compose
- **8 GB RAM** minimum
- **API keys optional** — Ollama-only mode works for all tasks (set `DEFAULT_LLM_PROVIDER=ollama`)

---

## Contributing

### Project Structure

```
chrono-canvas/
├── frontend/          # React + TypeScript + Vite
│   └── src/
│       ├── pages/     # One file per page
│       ├── components/# Shared UI components
│       └── api/       # API hooks
├── backend/           # FastAPI + LangGraph
│   └── src/chronocanvas/
│       ├── agents/    # Agent implementations
│       ├── llm/       # LLM router and providers
│       └── api/       # REST endpoints
├── cli/               # CLI tool (Click-based)
│   └── src/chronocanvas_cli/
│       └── commands/  # One file per command group
└── docker-compose.yml
```

### How to Add a New Agent

1. Create `backend/src/chronocanvas/agents/your_agent.py` implementing the `BaseAgent` interface
2. Register it in the LangGraph workflow in `backend/src/chronocanvas/agents/workflow.py`
3. Add a task type to `backend/src/chronocanvas/llm/router.py` if it needs LLM routing

### How to Add a New LLM Provider

1. Implement the provider interface in `backend/src/chronocanvas/llm/providers/`
2. Add it to the provider registry in `backend/src/chronocanvas/llm/router.py`
3. Add env vars to `.env.example`

### Running Tests

```bash
make test           # Run all tests
make test-backend   # Backend tests only
make test-frontend  # Frontend tests only
```
