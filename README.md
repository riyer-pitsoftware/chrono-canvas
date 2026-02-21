# ChronoCanvas

Agentic historical education toolkit that generates historically accurate portraits using AI agents, multi-LLM routing, and image generation.

## Quick Start

```bash
cp .env.example .env
# Edit .env with your API keys
make dev
```

## Architecture

- **Backend**: FastAPI + SQLAlchemy + LangGraph agents
- **Frontend**: React + TypeScript + Tailwind + shadcn/ui
- **CLI**: Typer + Rich
- **Queue**: LangGraph async + Redis pub/sub
- **Image Gen**: Pluggable (mock/StableDiffusion/FaceFusion)

## Development

```bash
make backend    # Run API server locally
make frontend   # Run frontend dev server
make test       # Run all tests
make seed       # Load seed data
make migrate    # Run database migrations
```

## Docker

```bash
make up         # Start all services
make down       # Stop all services
make build      # Rebuild images
```
