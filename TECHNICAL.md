# ChronoCanvas — Technical Reference

This document covers the full architecture, agent pipeline, configuration, and service dependencies. For REST/WebSocket API reference see [docs/api.md](docs/api.md). For development setup and contribution guide see [docs/development.md](docs/development.md).

---

## Architecture

| Component | Technology | Role |
|---|---|---|
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS | Web UI |
| Backend | FastAPI + LangGraph + SQLAlchemy (asyncpg) | API server + agent orchestration |
| Database | PostgreSQL 16 | Persistent storage (requests, figures, images, audit log) |
| Cache | Redis 7 | Agent state checkpointing + pub/sub for real-time streaming |
| Image generation | Mock / ComfyUI (SDXL or FLUX) / FaceFusion | Portrait generation backend |
| CLI | Typer + Rich | Command-line automation interface |

All components run as Docker services defined in `docker-compose.dev.yml`. The frontend communicates with the backend over HTTP and WebSocket; the backend is the only service that touches the database and Redis directly.

---

## Agent pipeline

The pipeline is a LangGraph state machine. Each agent node receives the full `AgentState` dict, does its work, and returns a partial state update. The orchestrator decides execution order; the validation agent can loop the pipeline back to prompt generation on failure.

| # | Agent | Default LLM | What it does |
|---|---|---|---|
| 1 | **Orchestrator** | Ollama | Reads the input, creates an execution plan, delegates to downstream agents |
| 2 | **Extraction** | Ollama | Parses free-text input into a structured figure JSON (name, era, region, role) |
| 3 | **Research** | Claude | Enriches the figure with historical context; streams tokens to the UI in real time |
| 4 | **Face Search** | — | Searches for a reference face image via SerpAPI; skipped if a face is uploaded manually |
| 5 | **Prompt Generation** | Claude | Constructs a period-accurate SDXL/FLUX prompt from the research data; streams tokens |
| 6 | **Image Generation** | — | Calls the configured image backend (ComfyUI or FaceFusion) to produce the portrait |
| 7 | **Validation** | Ollama | Scores the portrait 0–100 for historical accuracy; triggers retry if score < 70 (max 2 retries) |
| 8 | **Facial Compositing** | — | Composites the source face onto the generated portrait using FaceFusion, if a face is available |
| 9 | **Export** | — | Packages the final PNG and a JSON metadata file for download |

LLM provider assignments are configurable per task type in `backend/src/chronocanvas/llm/router.py`.

---

## Configuration

All configuration is via environment variables. Copy `.env.example` to `.env` to get started — the example file documents every variable with safe defaults.

**Never commit `.env` to version control.**

### LLM providers

| Variable | Description | Default |
|---|---|---|
| `DEFAULT_LLM_PROVIDER` | Fallback provider when no task-specific routing applies | `ollama` |
| `OLLAMA_BASE_URL` | Ollama endpoint | `http://localhost:11434` |
| `OLLAMA_MODEL` | Model name for Ollama | `llama3.1:8b` |
| `ANTHROPIC_API_KEY` | Anthropic API key (required for Claude) | — |
| `CLAUDE_MODEL` | Claude model ID | `claude-sonnet-4-6` |
| `OPENAI_API_KEY` | OpenAI API key | — |
| `OPENAI_MODEL` | OpenAI model | `gpt-4o` |

### Image generation

| Variable | Description | Default |
|---|---|---|
| `IMAGE_PROVIDER` | `mock`, `comfyui`, or `facefusion` | `mock` |
| `COMFYUI_API_URL` | ComfyUI API endpoint | `http://localhost:8188` |
| `COMFYUI_MODEL` | `sdxl` or `flux` | `sdxl` |
| `COMFYUI_SDXL_CHECKPOINT` | SDXL checkpoint filename | — |
| `FACEFUSION_API_URL` | FaceFusion API endpoint | `http://localhost:7861` |

### Database and cache

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (asyncpg format) |
| `REDIS_URL` | Redis connection string |

### Application

| Variable | Description | Default |
|---|---|---|
| `OUTPUT_DIR` | Directory for generated images | `./output` |
| `UPLOAD_DIR` | Directory for uploaded face images | `./uploads` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `CORS_ORIGINS` | Comma-separated allowed origins | `http://localhost:3000` |
| `SERPAPI_KEY` | SerpAPI key for face image web search (optional) | — |

---

## Service dependencies

### PostgreSQL

The backend uses SQLAlchemy with asyncpg. Migrations are managed with Alembic.

```bash
make migrate    # run pending migrations
make seed       # load 100+ seed figures and periods
```

The database schema is in `backend/src/chronocanvas/db/models/`.

### Redis

Used for two purposes:

1. **Agent state checkpointing** — LangGraph persists agent state to Redis between steps, enabling resume on failure
2. **Pub/sub streaming** — the backend publishes LLM tokens and progress events to per-request Redis channels; the WebSocket relay subscribes and forwards to the browser

### ComfyUI

ComfyUI runs as a separate process (not included in the Docker Compose stack — start it independently). Configure `COMFYUI_API_URL` in `.env`. The backend submits workflows via ComfyUI's `/prompt` HTTP endpoint and tracks progress via its WebSocket.

Required models (place in ComfyUI's `models/` directory):

- **SDXL mode:** your chosen SDXL checkpoint (set `COMFYUI_SDXL_CHECKPOINT`)
- **FLUX mode:** `flux1-dev-Q4_K_S.gguf`, `clip_l.safetensors`, `t5xxl_fp8_e4m3fn.safetensors`, `ae.safetensors`

### FaceFusion

FaceFusion runs via a thin FastAPI wrapper (`docker/facefusion_server.py`) that exposes a REST interface over FaceFusion's Python API. It is included in the Docker Compose dev stack.

The FaceFusion source tree is bind-mounted at runtime from `FACEFUSION_SOURCE_DIR` (set in `.env`). ONNX models are downloaded automatically on first use and persisted in a named Docker volume.

---

## Security

The following controls are active:

- **SSRF prevention** — `security.py:is_safe_url()` blocks outbound requests to private, loopback, link-local, and cloud-metadata IP ranges before any image URL is fetched
- **Magic-byte validation** — uploaded and downloaded images are validated against known file signatures (JPEG, PNG, WebP), independent of the declared `Content-Type`
- **Download size cap** — face images downloaded from web search are capped at 5 MB
- **Security headers** — all responses carry `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, and `Referrer-Policy: strict-origin-when-cross-origin`
- **Input length limits** — search queries and text inputs are bounded at the API layer

Authentication and authorisation are not currently implemented. ChronoCanvas is designed for trusted local or private network deployment. Do not expose it to the public internet without adding an auth layer.

---

## API reference

See [docs/api.md](docs/api.md).

---

## Development

See [docs/development.md](docs/development.md).
