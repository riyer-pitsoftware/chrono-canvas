# ChronoCanvas — Product Overview

ChronoCanvas is an AI-powered visual storytelling platform that transforms text prompts into illustrated storyboards with narrated audio and assembled video. It orchestrates multiple Google AI services — Gemini 2.5 Flash, Imagen 4, and Gemini TTS — through LangGraph agent pipelines with full cost, token, and latency observability at every step.

**Target users:** Creative professionals, educators, and anyone who wants to turn a story concept into a visual narrative without manual illustration or video editing.

**Core value proposition:** End-to-end story-to-storyboard generation with a noir creative director persona ("Dash"), cross-panel coherence review, voice narration, video assembly, and a complete audit trail proving every AI decision.

---

## Features

### Story Director (Primary Mode)

The Story Director is a 13-node LangGraph agent pipeline that takes a text story (or an uploaded image) and produces a complete illustrated storyboard with narration.

**Pipeline flow:**

```
Story Orchestrator
    → [Image-to-Story]*
    → [Reference Image Analysis]*
    → Character Extraction
    → Scene Decomposition
    → Scene Prompt Generation
    → Prompt Pre-Validation (score + auto-repair)
    → Scene Image Generation (Imagen 4)
    → Storyboard Coherence Review (Gemini multimodal)
    → [Regen loop if consistency < threshold]*
    → Narration Script
    → Narration Audio (Gemini TTS)
    → Video Assembly (ffmpeg)
    → Storyboard Export

* = conditional nodes, activated by input type or config
```

Each node receives a typed `StoryState` dict, performs its work, and returns a partial state update. The full state flows through the pipeline and is persisted for audit.

**Noir creative director persona ("Dash"):** All LLM prompts in the story pipeline are voiced through Dash — a noir creative director who thinks in shots, not paragraphs. Dash evaluates scene composition, continuity, and narrative flow with the economy of Hammett and the poetry of Chandler. This persona shapes both the narration text and the internal quality judgments (coherence review, prompt validation).

### Historical Lens (Portrait Mode)

A 10-node pipeline for generating historically-informed portraits of named figures:

```
Orchestrator → Extraction → Research (Google Search grounding)
    → Face Search → Prompt Generation → Image Generation
    → Validation (score 0-100, retry loop ≤2x)
    → Multimodal Validation → Facial Compositing → Export
```

The research node uses Gemini with Google Search grounding to enrich prompts with period-specific clothing, cultural markers, and art style details. Validation scores portraits across 4 weighted criteria (clothing accuracy, cultural accuracy, temporal plausibility, artistic plausibility) and triggers automatic prompt correction and regeneration when scores fall below threshold.

### Image-to-Story

Upload an image instead of typing a prompt. Gemini multimodal analyzes the image and extracts a story concept — title, synopsis, characters, settings, and mood — which then flows through the full Story Director pipeline.

### Reference Image Analysis

Upload up to 5 reference images (style guides, location photos, mood boards). Gemini multimodal extracts visual style, color palette, era cues, and key elements from each reference. These analysis results are injected into scene prompt generation for style-consistent output.

### Prompt Pre-Validation

Before expensive image generation, each scene prompt is scored on 4 axes:
- **Identity clarity** — are characters physically specific enough to draw?
- **Era plausibility** — do objects and clothing match the time period?
- **Composition completeness** — are camera angle, lighting, and framing specified?
- **Contradiction-free** — are there conflicting descriptors?

Prompts scoring below 0.7 are automatically rewritten by LLM while preserving creative intent.

### Storyboard Coherence Review

After all scene images are generated, Gemini multimodal receives every image plus its text description for holistic assessment:
- Character consistency across panels
- Art style and noir visual language uniformity
- Color palette harmony
- Narrative flow and scene ordering
- Continuity tracking (expected vs. established state between scenes)

Low-scoring storyboards trigger selective scene regeneration (bottom half of worst-scoring panels, up to 1 retry).

### Voice Narration

Two-stage narration pipeline:
1. **Narration script** — Gemini generates cinematic voiceover text per panel. When `vision_narration_enabled=true`, uses Gemini multimodal to reference actual visual details in the generated images.
2. **Narration audio** — Gemini TTS (`gemini-2.5-flash-preview-tts`, voice: Kore) synthesizes WAV audio for each panel.

### Video Assembly

After narration audio is generated, ffmpeg stitches scene images into a Ken Burns slideshow with crossfade transitions, then muxes narration audio to produce an MP4 video. Optional — requires ffmpeg and `video_assembly_enabled=true`.

### Voice Input

Users can speak their story prompt instead of typing. Audio is uploaded to the `/api/voice/transcribe` endpoint, where Gemini multimodal (audio + text) transcribes it. Supports WebM, WAV, OGG, MPEG, and MP4 audio formats up to 25MB.

### Scene Editing

After a storyboard is generated, users can edit individual scenes by providing natural language instructions via `POST /api/generate/{id}/scenes/{index}/edit`. The instruction is processed through the story pipeline to regenerate that specific scene.

### ConfigHUD

A pre-generation mixing board UI that lets users select providers and toggle features per channel before starting a run:

- **LLM provider** — Gemini, Claude, OpenAI, or Ollama
- **LLM model** — model-specific options per provider
- **Image provider** — Imagen, ComfyUI, Stable Diffusion, or Mock
- **Voice/TTS** — enable/disable, voice selection
- **Vision features** — image-to-story, vision narration
- **Post-processing** — FaceFusion, validation retry, video assembly, scene editing

Selections are serialized as a `RuntimeConfig` and attached to the generation request. Each pipeline node checks runtime overrides before falling back to global settings. The ConfigHUD validates selections against server-side availability before submission via `POST /api/config/validate`.

Hidden in hackathon mode (`HACKATHON_MODE=true`).

### TrustCard

A real-time pipeline progress and audit visualization component shown during and after generation. Displays:

- Pipeline step sequence with completion status (portrait: 8 steps, story: 12 steps)
- Per-step provider badge (gemini, imagen, etc.) with color coding
- Token counts, cost, and latency per LLM call
- Validation scores and reasoning
- Expandable raw prompt/response inspection per step

### Audit Trail

Every LLM call is logged with:
- Agent name, provider, model
- Full system prompt and user prompt
- Raw response text
- Input/output token counts
- Computed cost (USD)
- Latency (ms)
- Whether fallback was used and from which provider

Browsable per generation via the audit detail view (`GET /api/generate/{id}/audit`). The `AuditProjector` aggregates all LLM calls into a response with total cost, total duration, validation scores, state snapshots, storyboard data, and narration audio URLs.

### Export Bundle

Download a zip containing:
- `citations.json` — structured citations from research grounding
- `story.md` — formatted story text with scene descriptions, characters, mood, and settings
- `frames/` — all generated scene images

Available via `GET /api/export/{id}/bundle`.

Additional export endpoints: individual image download, per-scene audio download, video download, and export metadata.

### Two-Mode Operation

- **Normal mode** (`HACKATHON_MODE=false`): Both Historical Lens and Story Director available, ConfigHUD visible, full sidebar navigation
- **Hackathon mode** (`HACKATHON_MODE=true`): Story Director is the default, sidebar reorders story-first, ConfigHUD hidden, root URL auto-redirects to story generation

Both modes use identical backend code — switching is purely a UI routing and feature visibility change controlled by a single environment variable. Nothing is deleted.

### Content Moderation

Input validation via keyword filtering (`content_moderation_enabled=true` by default). The story orchestrator responds in-character when content is blocked: "I don't touch stories that cross certain lines. Even in noir, there are rules."

### Research Cache

pgvector-based semantic similarity cache for historical research results. When a new research query is similar enough to a cached entry (cosine similarity > 0.85), the cached result is returned instead of making a new LLM call. Tracks hit counts and cost savings per entry. Browsable via `GET /api/memory/stats` and `GET /api/memory/entries`.

### Timeline Explorer

Interactive timeline slider for browsing 100+ curated historical figures across Ancient through Modern eras. Users can select a figure to pre-populate the generation prompt.

### Admin Dashboard

- Configure validation rule weights and pass threshold
- Review queue for generations needing human review
- CRUD operations on validation rules
- System overview with generation statistics

---

## Google AI Services Integration

### Gemini 2.5 Flash — LLM

All text generation in the story and portrait pipelines runs through the Gemini provider (`backend/src/chronocanvas/llm/providers/gemini.py`) using the `google-genai` Python SDK (`google.genai.Client`).

**SDK calls:**
- `client.aio.models.generate_content()` — standard generation with async support
- `client.aio.models.generate_content_stream()` — streaming generation with real-time token delivery via WebSocket

**Features used:**
- System instructions via `GenerateContentConfig.system_instruction`
- JSON mode via `response_mime_type="application/json"`
- Temperature and max token control
- Token usage metadata for cost tracking

**Pricing tracked:** $0.15/M input tokens, $0.60/M output tokens (Gemini 2.5 Flash).

### Gemini + Google Search Grounding

The research node calls `generate_with_search()` which configures Gemini with the Google Search tool:

```python
types.Tool(google_search=types.GoogleSearch())
```

Grounding citations are extracted from `candidate.grounding_metadata.grounding_chunks` and returned as structured citation objects with title, URL, and confidence score. These citations flow into the export bundle and audit trail.

### Gemini Multimodal (Vision)

Direct `google.genai.Client` calls (outside the LLM router) for tasks requiring image + text input:

- **Storyboard coherence** — sends all scene images + descriptions for holistic review
- **Image-to-story** — extracts story concept from uploaded image
- **Reference image analysis** — extracts style and visual cues from reference images
- **Voice transcription** — audio + text prompt for speech-to-text
- **Vision narration** — image + text for narration that references visual details

All multimodal calls use `types.Part.from_bytes()` for binary data and `types.Part.from_text()` for text, wrapped in `gemini_generate_with_timeout()` with a 120-second timeout.

### Gemini TTS

Narration audio synthesis via the TTS-specific Gemini model (`gemini-2.5-flash-preview-tts`):

```python
config=types.GenerateContentConfig(
    response_modalities=["AUDIO"],
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                voice_name="Kore",
            ),
        ),
    ),
)
```

Returns raw PCM audio (24kHz, mono, 16-bit) which is written as WAV files.

### Imagen 4

Image generation via `google.genai.Client` (`backend/src/chronocanvas/imaging/imagen_client.py`):

```python
client.aio.models.generate_images(
    model="imagen-4.0-fast-generate-001",
    prompt=prompt,
    config=types.GenerateImagesConfig(
        number_of_images=1,
        aspect_ratio=aspect_ratio,  # 1:1, 3:4, 4:3, 9:16, 16:9
    ),
)
```

Includes retry logic with exponential backoff (up to 3 retries) for rate limits and transient errors. Cost: $0.02/image.

### Cloud Run

Three Cloud Run services:
- **API** — FastAPI backend (uvicorn), handles HTTP + WebSocket
- **Worker** — arq job processor, runs portrait and story generation pipelines
- **Frontend** — nginx serving Vite SPA, proxies `/api/` to API service

### Cloud SQL (PostgreSQL)

Managed PostgreSQL 16 for persistent storage: generation requests, generated images, validation results, audit logs, research cache (pgvector), figures, timeline periods, validation rules, and admin settings.

### Memorystore (Redis)

Managed Redis 7.0 for:
- **Pub/sub streaming** — real-time pipeline progress and LLM token streams pushed to the frontend via WebSocket
- **ARQ job queue** — background job processing for generation pipelines
- **LangGraph checkpointing** — agent state persistence for pipeline recovery

---

## Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│  Frontend (React 18 + TypeScript + Vite + Tailwind)             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │ ConfigHUD│ │StoryBoard│ │ TrustCard│ │ Timeline │           │
│  │          │ │  View    │ │          │ │ Explorer │           │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
│        HTTP / WebSocket                                         │
└──────────────────────────┬───────────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────────┐
│  API Server (FastAPI + SQLAlchemy asyncpg)                       │
│  Routes: /generate, /export, /voice, /config, /admin,           │
│          /figures, /timeline, /memory, /conversation, /health    │
│  WebSocket relay for real-time streaming                         │
└──────────┬────────────────────────────┬──────────────────────────┘
           │                            │
           ▼                            ▼
┌──────────────────┐         ┌──────────────────────┐
│  PostgreSQL 16   │         │  Redis 7             │
│  (Cloud SQL)     │         │  (Memorystore)       │
│  - requests      │         │  - pub/sub streaming │
│  - images        │         │  - arq job queue     │
│  - audit_logs    │         │  - LangGraph ckpt    │
│  - figures       │         └──────────┬───────────┘
│  - research_cache│                    │
│    (pgvector)    │         ┌──────────▼───────────┐
└──────────────────┘         │  Worker (arq)        │
                             │  ┌─────────────────┐ │
                             │  │ Portrait Pipeline│ │
                             │  │ (10 nodes)       │ │
                             │  ├─────────────────┤ │
                             │  │ Story Pipeline   │ │
                             │  │ (13 nodes)       │ │
                             │  └────────┬────────┘ │
                             └───────────┼──────────┘
                                         │
                    ┌────────────────────┬┴──────────────────┐
                    ▼                    ▼                    ▼
             ┌────────────┐     ┌──────────────┐    ┌──────────────┐
             │ Gemini 2.5 │     │  Imagen 4    │    │ Gemini TTS   │
             │ Flash      │     │  (images)    │    │ (narration)  │
             │ (LLM)      │     └──────────────┘    └──────────────┘
             │ + Google    │
             │   Search    │
             └─────────────┘
```

### LangGraph Agent State Machine

Both pipelines are implemented as LangGraph `StateGraph` instances with typed state dicts (`AgentState` for portraits, `StoryState` for stories). Key patterns:

- **Conditional edges** — validation retry loops, image-to-story routing, coherence-triggered regeneration, TTS gating
- **Invariant checks** — portrait pipeline nodes are wrapped with `checked()` decorators that enforce pre/postcondition contracts
- **Checkpointing** — LangGraph persists state to PostgreSQL (via `AsyncPostgresSaver`) for pipeline recovery on restart; falls back to `MemorySaver` when psycopg is unavailable
- **RuntimeConfig threading** — per-request configuration overrides flow through state and are checked by each node

### LLM Router

The `LLMRouter` manages 4 pluggable providers (Gemini, Claude, OpenAI, Ollama) with:

- **Per-agent routing** — override provider per pipeline node via `LLM_AGENT_ROUTING` env var or `RuntimeConfig.agent_routing`
- **Deployment mode defaults** — GCP mode defaults to Gemini, local mode defaults to Ollama
- **Fallback chain** — if the preferred provider is unavailable, falls back to the next available provider
- **Strict Gemini mode** — `HACKATHON_STRICT_GEMINI=true` raises `GeminiUnavailableError` (503) instead of falling back, ensuring all LLM calls go through Gemini for hackathon scoring
- **Cost tracking** — every call records provider, model, tokens, cost, and latency
- **Rate limiting** — configurable RPM and concurrent call limits
- **Streaming** — `generate_stream()` delivers tokens to the frontend in real time via Redis pub/sub

---

## API Surface

### Generation

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/generate` | Create a generation request (portrait or story) |
| `POST` | `/api/generate/batch` | Create multiple generation requests |
| `GET` | `/api/generate` | List generations with pagination and status filter |
| `GET` | `/api/generate/{id}` | Get generation details |
| `GET` | `/api/generate/{id}/audit` | Full audit trail with LLM calls, costs, validation |
| `GET` | `/api/generate/{id}/images` | List generated images |
| `POST` | `/api/generate/{id}/retry` | Retry from a specific pipeline step |
| `POST` | `/api/generate/{id}/scenes/{idx}/edit` | Edit a specific scene with natural language |
| `POST` | `/api/generate/{id}/feedback` | Submit feedback on a generation step |
| `GET` | `/api/generate/{id}/feedback` | List feedback for a generation |
| `DELETE` | `/api/generate/{id}` | Delete a generation and its files |

### Export

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/export/{id}/download` | Download generated image (PNG) |
| `GET` | `/api/export/{id}/audio/{scene}` | Download scene narration audio (WAV) |
| `GET` | `/api/export/{id}/video` | Download assembled storyboard video (MP4) |
| `GET` | `/api/export/{id}/metadata` | Get export metadata (JSON) |
| `GET` | `/api/export/{id}/bundle` | Download zip bundle (citations + story + frames) |

### Voice

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/voice/transcribe` | Transcribe audio to text via Gemini multimodal |

### Configuration

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/config/validate` | Validate ConfigHUD payload against available services |
| `GET` | `/api/health` | Service health, deployment mode, hackathon mode, service availability map |

### Admin

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/admin/validation/rules` | Get validation rules and pass threshold |
| `PUT` | `/api/admin/validation/rules/{id}` | Update a validation rule weight/enabled |
| `POST` | `/api/admin/validation/rules` | Create a custom validation rule |
| `PUT` | `/api/admin/validation/threshold` | Update the pass/fail threshold |
| `GET` | `/api/admin/validation/queue` | Review queue for generations needing attention |
| `POST` | `/api/admin/validation/queue/{id}/review` | Submit human review decision |

### Other

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/figures` | List historical figures with search and era filter |
| `GET` | `/api/timeline/periods` | List timeline periods with figure counts |
| `GET` | `/api/memory/stats` | Research cache statistics (entries, hits, cost saved) |
| `GET` | `/api/memory/entries` | List cached research entries |
| `POST` | `/api/conversation/{id}/chat` | Conversational storyboard refinement |
| `POST` | `/api/faces/upload` | Upload a reference face image |
| `POST` | `/api/reference-images/upload` | Upload reference images for style matching |
| `WebSocket` | `/ws/generation/{id}` | Real-time pipeline progress and LLM token streams |

---

## Deployment

### Local (Docker Compose)

```bash
make quickstart    # Build, migrate, seed, health check
make smoke-test    # 8-check verification suite
```

Services: db (PostgreSQL), redis, api (FastAPI), worker (arq), frontend (Vite dev server).

Dev mode (`docker-compose.dev.yml`) adds bind mounts for hot reload and optional FaceFusion service.

### Cloud Run

Three Cloud Run services deployed via `deploy/cloudrun/deploy-all.sh`:

| Service | Spec | Role |
|---------|------|------|
| API | 2 vCPU, 4GB RAM | FastAPI backend + WebSocket |
| Worker | 2 vCPU, 4GB RAM | arq job processor |
| Frontend | 1 vCPU, 256MB RAM | nginx SPA |

Managed infrastructure:
- Cloud SQL (db-f1-micro) — PostgreSQL 16
- Memorystore (basic, 1GB) — Redis 7.0
- Secret Manager — API keys
- Artifact Registry — container images
- VPC connector — Cloud Run to Memorystore

Estimated cost: ~$144/month for demo/hackathon usage.

Deployment scripts in `deploy/cloudrun/scripts/`:
- `00-env.sh` — shared environment config
- `01-infra.sh` through `06-deploy.sh` — sequential setup steps
- `07-teardown.sh` — tear down all resources to stop billing

### GKE

Kubernetes deployment with in-cluster PostgreSQL, configurable via `deploy/gke/`. Supports configurable LLM and image providers.

---

## Metrics and Observability

### Per-Generation Audit

Every generation request accumulates:
- **`llm_calls`** — array of LLM call records, each containing: agent name, provider, model, input/output tokens, cost (USD), latency (ms), full prompt and response text, whether fallback was used
- **`agent_trace`** — array of trace entries per pipeline node with timestamps, node-specific metrics (scenes decomposed, panels reviewed, coherence scores, etc.)
- **`storyboard_data`** — full panel data including images, coherence scores, narration text, audio paths
- **`validation_results`** — per-category scores, pass/fail, reasoning

### Cost Tracking

The `CostTracker` in the LLM router records every call by provider, model, token count, cost, and task type. Per-model pricing is maintained in the provider implementations:

| Provider | Model | Input | Output |
|----------|-------|-------|--------|
| Gemini | gemini-2.5-flash | $0.15/M tokens | $0.60/M tokens |
| Gemini | gemini-2.0-flash | $0.10/M tokens | $0.40/M tokens |
| Imagen | imagen-4.0-fast | $0.02/image | — |

Costs are aggregated in the audit detail response as `total_cost` and `total_duration_ms`.

### Real-Time Streaming

Pipeline progress is published to Redis pub/sub channels (`generation:{request_id}`) and relayed to the frontend via WebSocket:
- `llm_token` — individual tokens during streaming generation
- `llm_stream_end` — stream completion marker
- `node_start` / `node_complete` — pipeline step transitions
- `scene_image` — scene image generated (with path and scene index)
- `artifact` — audio or video artifact available (with URL and mime type)

### Health Endpoint

`GET /api/health` returns:
- Overall status (`ok` or `degraded`)
- Deployment mode
- Hackathon mode flag
- Service availability map (LLM providers, image providers, search services, TTS, FaceFusion)
- Hackathon warnings if required services are misconfigured

### Research Cache Metrics

`GET /api/memory/stats` returns:
- Total cached entries
- Cache hit count
- Estimated cost saved (USD) from cache hits

### Pipeline Invariant Checks

Portrait pipeline nodes are wrapped with `checked()` decorators that validate pre/postconditions at runtime. Configurable via `INVARIANT_CHECKS_ENABLED` (default: true) and `INVARIANT_STRICT` (default: false — log warnings instead of raising).

---

## Security

- **SSRF prevention** — blocks outbound requests to private, loopback, link-local, and cloud-metadata IP ranges
- **Magic-byte validation** — uploaded and downloaded images validated against known file signatures
- **Download size cap** — 5MB limit on face images from web search
- **Security headers** — `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`
- **Input length limits** — bounded at the API layer
- **Content moderation** — keyword-based input filtering (default on)
- **Path confinement** — all file access uses `confine_path()` to prevent directory traversal
- **Deployment mode enforcement** — GCP deployments reject local-only providers; config validation prevents misconfiguration

No authentication layer is implemented. Designed for trusted deployment environments.
