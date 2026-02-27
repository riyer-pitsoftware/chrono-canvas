# Technology Stack

**Analysis Date:** 2026-02-27

## Languages

**Primary:**
- Python 3.11+ - Backend API and agentic pipeline (FastAPI, LangGraph, async SQLAlchemy)
- TypeScript 5.7 - Frontend with React 19 and strict type checking
- SQL - PostgreSQL database with pgvector extension for semantic search

**Secondary:**
- JavaScript/Node 20 - Build tooling (Vite) and npm package management
- Shell - Docker entrypoint scripts and deployment automation

## Runtime

**Environment:**
- Python 3.11 (backend production container: `python:3.11-slim`)
- Node.js 20 (frontend build container: `node:20-alpine`)

**Package Manager:**
- pip (Python) - Backend dependencies via pyproject.toml, Hatchling build system
- npm (Node.js) - Frontend dependencies via package.json and package-lock.json
- Lockfiles: `package-lock.json` present (git committed)

## Frameworks

**Core:**
- FastAPI 0.115.0+ - REST API framework, async/await, auto-documentation
- React 19.0.0 - Frontend UI library with hooks
- SQLAlchemy 2.0.0+ with asyncio - Async ORM for PostgreSQL
- LangGraph 0.2.0+ - Agent orchestration framework for multi-step pipeline
- Pydantic 2.10.0+ - Data validation and settings management (v2 with Field factories)

**Agent/LLM:**
- LangGraph - Stateful graph-based agent orchestration with checkpointing
- langchain-core 0.3.0+ - Base abstractions for LLM tools and agents
- anthropic 0.40.0+ - Claude API client (Sonnet 4.5 support)
- openai 1.60.0+ - GPT-4o integration
- httpx 0.28.0+ - Async HTTP client (for Ollama, ComfyUI, SerpAPI)

**Image Processing:**
- Pillow 11.0.0+ - Image manipulation and validation
- sentence-transformers 3.0.0+ - Semantic embeddings (`all-MiniLM-L6-v2` for research cache)
- pgvector 0.3.0+ - PostgreSQL vector type and similarity search

**Frontend UI:**
- Tailwind CSS 4.0.0 - Utility-first CSS with Vite integration
- shadcn/ui components via Radix UI - Button, Dialog, Select, Dropdown, Tabs, Progress
- Lucide React 0.469.0 - Icon library
- Zustand 5.0.0 - Client-side state management (custom router store)
- TanStack React Query 5.62.0 - Server state + data fetching with caching
- TanStack React Router 1.95.0 - Routing library (imported but not used; custom router in place)
- @xyflow/react 12.10.1 - Graph visualization for LangGraph trace display

**Build/Dev:**
- Vite 6.0.0 - Frontend build tool with hot module replacement
- TypeScript 5.7.0 - Type checking and transpilation
- ESLint 9.17.0 with typescript-eslint - Code quality and type-aware linting
- Tailwind CSS Vite plugin 4.0.0 - JIT CSS compilation
- Playwright 1.58.2 - E2E testing (test framework available, adoption TBD)

**Testing:**
- pytest 8.0.0+ - Python test runner with async support
- pytest-asyncio 0.24.0+ - Async test execution
- pytest-cov 6.0.0+ - Coverage reporting
- aiosqlite 0.20.0+ - SQLite for test isolation (JSONB limitations noted)
- opencv-python-headless 4.9.0+ - Image processing in tests

**Linting/Formatting:**
- Ruff 0.8.0+ - Fast Python linter (E, F, I, N, W rules; 100-char line length)
- Hatchling - Build backend for Python package

## Key Dependencies

**Critical:**
- fastapi + uvicorn - HTTP server + async ASGI runtime
- sqlalchemy[asyncio] + asyncpg - Async database access (PostgreSQL)
- langgraph + langgraph-checkpoint-postgres - Agent state management with durable checkpointing
- redis 5.2.0+ - Pub/sub for WebSocket progress, ARQ job queue backend
- arq 0.25.0+ - Background job queue (message-based via Redis)
- pydantic-settings - Environment-based configuration management
- aiofiles 24.1.0+ - Async file I/O for uploads/downloads
- websockets 10.4+ - WebSocket support for real-time progress streaming

**LLM/AI:**
- anthropic - Claude Sonnet 4.5 and other models
- openai - GPT-4o
- langchain-core - Shared LLM abstractions
- sentence-transformers - Semantic search embeddings (cache hits)

**Image Generation:**
- comfyui_client (custom) - Advanced Stable Diffusion orchestration via ComfyUI
- sd_client (custom) - Stable Diffusion API wrapper
- facefusion_client (custom) - Face-swapping via FaceFusion API or Docker
- mock_generator (custom) - Development-only image stub

**Security:**
- python-jose[cryptography] 3.3.0+ - JWT token handling (not fully implemented; reserved)
- pydantic-settings - Env var validation and schema

## Configuration

**Environment:**
- Loaded from `.env` file via `pydantic_settings.BaseSettings`
- Settings class: `chronocanvas.config.Settings` at `backend/src/chronocanvas/config.py`
- Key configs: DATABASE_URL, REDIS_URL, LLM provider keys (ANTHROPIC_API_KEY, OPENAI_API_KEY, SERPAPI_KEY), IMAGE_PROVIDER selection, FACEFUSION_ENABLED, VALIDATION_RETRY_ENABLED, FACE_SEARCH_ENABLED

**Build:**
- Frontend: `vite.config.ts` with Tailwind + React plugins, aliases (`@/` → `./src/`)
- Backend: `pyproject.toml` with dependencies, test config, ruff linting rules
- Docker: Multi-stage builds in `Dockerfile.api` (dependencies cached) and `Dockerfile.frontend` (Node 20 builder → nginx)

## Platform Requirements

**Development:**
- Python 3.11+
- Node.js 20
- PostgreSQL 16+ with pgvector extension (docker-compose default: `pgvector/pgvector:pg16`)
- Redis 7+ (docker-compose default: `redis:7-alpine`)
- Optional: ComfyUI API (port 8188), FaceFusion API (port 7861), Ollama (port 11434)

**Production:**
- PostgreSQL 16+ with pgvector for vector storage and semantic search
- Redis 7+ for pub/sub and ARQ job queue
- Docker-compatible container runtime
- GPU optional for image generation (ComfyUI nodes support CUDA/ROCm)
- GKE deployment supported: StatefulSet for Postgres + pgvector, Deployment for API/Worker/Frontend with HPA

## Data Storage

**Primary Database:**
- PostgreSQL 16+ with pgvector extension
- Connection: `postgresql+asyncpg://user:pass@host:5432/db`
- Checkpointer: LangGraph AsyncPostgresSaver (durable state snapshots)
- Fallback: In-memory MemorySaver if Postgres unavailable (tests, early startup)
- Migrations: Alembic 1.14.0+ in `backend/alembic/versions/` (007 current: audit_feedback)

**File Storage:**
- Local filesystem: `./output/` for generated images, `./uploads/` for user uploads
- Served via FastAPI StaticFiles mount at `/output` and `/uploads` routes
- Docker volumes: `output` and `uploads` volumes persist data across restarts
- Scaled deployment: Plan for Filestore (ReadWriteMany PVC) to support multi-replica API

---

*Stack analysis: 2026-02-27*
