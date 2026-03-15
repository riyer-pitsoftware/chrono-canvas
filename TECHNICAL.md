# ChronoCanvas — Technical Reference

ChronoCanvas is a generative AI application that creates historically grounded portraits and cinematic visual storyboards. It uses **Google Gemini** as its primary AI backbone — for text generation, image generation (Imagen), multimodal vision analysis, text-to-speech narration, voice input transcription, and Google Search grounding — orchestrated through **LangGraph** state-machine pipelines.

---

## Architecture

| Component | Technology | Role |
|---|---|---|
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS | Web UI with real-time streaming, ConfigHUD, storyboard viewer |
| Backend | FastAPI + LangGraph + SQLAlchemy (asyncpg) | API server + agent pipeline orchestration |
| Worker | arq (async Redis queue) | Background job processing for portrait + story pipelines |
| Database | PostgreSQL 16 + pgvector | Persistent storage (requests, figures, images, audit log, research cache) |
| Cache | Redis 7 | LangGraph state checkpointing + pub/sub for real-time WebSocket streaming |
| Image Generation | Imagen 4 (primary) / ComfyUI / Stable Diffusion / Mock | Portrait and scene image generation |
| TTS | Gemini TTS (`gemini-2.5-flash-preview-tts`) | Per-scene narration audio synthesis |
| Video | ffmpeg | Storyboard-to-MP4 assembly with Ken Burns + crossfade |

All components run as Docker services. The frontend communicates with the backend over HTTP and WebSocket; the backend is the only service that touches the database and Redis directly.

### Google Cloud / GenAI SDK usage

ChronoCanvas uses the **`google-genai` Python SDK** (`google.genai.Client`) throughout — a single `GOOGLE_API_KEY` powers all Google AI features:

| Feature | SDK Method | Model |
|---|---|---|
| **LLM text generation** | `client.aio.models.generate_content()` | `gemini-2.5-flash` |
| **LLM streaming** | `client.aio.models.generate_content_stream()` | `gemini-2.5-flash` |
| **Google Search grounding** | `generate_content()` with `tools=[Tool(google_search=GoogleSearch())]` | `gemini-2.5-flash` |
| **Image generation** | `client.aio.models.generate_images()` | `imagen-4.0-fast-generate-001` |
| **Multimodal vision** (coherence, validation, image-to-story, reference analysis) | `generate_content()` with `Part.from_bytes()` image parts | `gemini-2.5-flash` |
| **Text-to-Speech** | `generate_content()` with `response_modalities=["AUDIO"]` | `gemini-2.5-flash-preview-tts` |
| **Voice input (speech-to-text)** | `generate_content()` with audio `Part.from_bytes()` | `gemini-2.5-flash` |

### GCP deployment services

| Service | Purpose |
|---|---|
| **Cloud Run** | Hosts API, worker, and frontend as serverless containers |
| **Cloud SQL (PostgreSQL)** | Managed database |
| **Memorystore (Redis)** | Managed Redis for checkpointing and pub/sub |
| **Artifact Registry** | Docker image storage |
| **Secret Manager** | API keys and credentials |
| **Cloud Build** | CI/CD pipeline |
| **GKE** (alternative) | Full Kubernetes deployment with HPA, Ingress, managed certs |

---

## Agent Pipelines

Both pipelines are **LangGraph `StateGraph`** state machines. Each node receives the full typed state dict, performs its work, and returns a partial state update. Conditional edges control branching (error handling, validation retries, coherence regeneration). All pipeline state is checkpointed to PostgreSQL via `langgraph-checkpoint-postgres` for durable recovery.

### Portrait Pipeline (10 nodes)

```
orchestrator → extraction → research → face_search → prompt_generation → image_generation
    ↓ error                                                                      ↓
   END                                                              validation ←→ prompt_generation (retry loop)
                                                                         ↓
                                                              multimodal_validation → facial_compositing → export → END
```

| # | Node | LLM/Service | What it does |
|---|---|---|---|
| 1 | **orchestrator** | Gemini | Reads input, creates execution plan, validates request |
| 2 | **extraction** | Gemini | Parses free-text into structured figure JSON (name, era, region, role, birth/death years, notable features) |
| 3 | **research** | Gemini + **Google Search grounding** | Enriches figure with historical context, clothing, physical description, art style. Uses `generate_with_search()` for grounded citations. Results cached via pgvector semantic similarity. |
| 4 | **face_search** | SerpAPI | Searches for reference face image via web search; skippable via config |
| 5 | **prompt_generation** | Gemini | Constructs a period-informed image generation prompt from research data; streams tokens to UI |
| 6 | **image_generation** | Imagen 4 | Calls configured image provider to produce the portrait |
| 7 | **validation** | Gemini | Scores portrait 0-100 for historical plausibility; triggers retry if score < 70 (max 2 retries) |
| 8 | **multimodal_validation** | Gemini Vision | Sends generated image + research context to Gemini multimodal for visual accuracy scoring (clothing, facial features, environment, cultural markers, anachronism check) |
| 9 | **facial_compositing** | FaceFusion | Composites source face onto portrait; skipped if no face available |
| 10 | **export** | — | Packages final PNG + JSON metadata for download |

**State type**: `AgentState` (TypedDict with namespaced sub-dicts: `extraction`, `research`, `prompt`, `image`, `validation`, `face`, `compositing`, `export`)

### Story Director Pipeline (13 nodes)

```
story_orchestrator → [image_to_story] → [reference_image_analysis] → character_extraction
    ↓ error                                                                    ↓
   END                                                                 scene_decomposition
                                                                               ↓
                                                                  scene_prompt_generation
                                                                               ↓
                                                                     prompt_validation
                                                                               ↓
                                                                  scene_image_generation
                                                                               ↓
                                                              storyboard_coherence ←→ scene_prompt_generation (regen loop)
                                                                     ↓                          ↓
                                                              narration_script          storyboard_export → END
                                                                     ↓
                                                              narration_audio
                                                                     ↓
                                                              video_assembly
                                                                     ↓
                                                              storyboard_export → END
```

| # | Node | LLM/Service | What it does |
|---|---|---|---|
| 1 | **story_orchestrator** | Gemini | Validates story input, routes to image-to-story or standard flow |
| 2 | **image_to_story** | Gemini Vision | *Optional.* Extracts story concept (title, synopsis, characters, settings) from an uploaded image using multimodal analysis |
| 3 | **reference_image_analysis** | Gemini Vision | *Optional.* Analyzes style/location/character reference images for visual consistency guidance |
| 4 | **character_extraction** | Gemini | Extracts character descriptions, names, physical attributes from the story text |
| 5 | **scene_decomposition** | Gemini | Breaks story into 3-8 visual scenes with descriptions, mood, setting, and **continuity state** (expected_state / established_state per scene for cross-scene consistency) |
| 6 | **historical_research** | Gemini + Google Search | Researches historical context via `generate_with_search()` for grounded citations |
| 7 | **scene_prompt_generation** | Gemini | Generates image prompts per scene with character visual anchors and noir visual grammar; max_tokens=8192 |
| 8 | **prompt_validation** | Gemini | Scores prompts on 4 axes (identity clarity, era plausibility, composition completeness, contradiction-free); auto-repairs prompts scoring < 0.7; max_tokens=4096 |
| 9 | **scene_image_generation** | Imagen 4 | Parallel image generation via `asyncio.gather` with retry on 503/UNAVAILABLE |
| 10 | **storyboard_coherence** | Gemini Vision (multimodal) | Reviews ALL scene images together — character consistency, art style, color palette, narrative flow, **continuity tracking**. Flags low-scoring scenes for regeneration (max 1 regen cycle); max_output_tokens=8192. |
| 11 | **narration_script** | Gemini (dual mode) | Vision-enhanced (sends images to Gemini multimodal) or text-only fallback; max_output_tokens=4096 |
| 12 | **narration_audio** | Gemini TTS | Parallel TTS via `asyncio.gather` using `gemini-2.5-flash-preview-tts`; per-panel non-fatal |
| 13 | **video_assembly** | ffmpeg | Stitches scene images + audio into MP4 (854x480 @12fps, ultrafast preset, 120s timeout) |
| 14 | **storyboard_export** | — | Packages storyboard (images, audio, video, metadata JSON); GCS upload on Cloud Run |

**Key behaviors:**
- **Error-halting edges**: Every inter-node edge checks `state["error"]` — if any node fails, pipeline halts at END instead of feeding broken state downstream
- **Shared JSON repair**: All story nodes parse LLM JSON via `json_repair.extract_and_parse_json()` (8 recovery strategies + truncation repair). Root cause: Gemini 2.5 Flash thinking tokens consume `max_output_tokens` budget, truncating JSON.
- **Coherence-driven regen**: If `character_consistency_score < 0.6` or `continuity_score < 0.5`, worst-scoring scenes loop back through prompt gen + image gen (max 1 cycle)

**State type**: `StoryState` (TypedDict with panels as `list[StoryPanel]`, each containing description, image_prompt, image_path, coherence_score, narration_text, narration_audio_path, continuity state)

### Grounding and Research Cache

The **research** node uses `generate_with_search()` which enables **Gemini Google Search grounding** — the model retrieves real-time web information and returns structured citations with URLs, titles, and confidence scores. Grounding citations from the search tool are merged with LLM-generated citations in the response.

Research results are cached using **pgvector** semantic similarity search (cosine similarity threshold: 0.85, model: `all-MiniLM-L6-v2`). Cache hits skip the LLM call entirely, saving cost and latency. Cache lookups and cost savings are tracked in the audit trail.

### Runtime Invariant Checks

Every portrait pipeline node is wrapped with `checked()` decorators that run pre/postcondition validation on the state before and after each node executes. Violations can be strict (raise) or soft (log warning), controlled by `INVARIANT_CHECKS_ENABLED` and `INVARIANT_STRICT`.

---

## Live API Features

Real-time, streaming experiences built on Gemini's native multimodal capabilities.

### Live Story (`POST /api/live-story/generate` — SSE)

Full-screen flip-o-rama storyboard generator using Gemini's native image generation.

| Component | Detail |
|---|---|
| **Image model** | `gemini-3.1-flash-image-preview` (fallback: `gemini-2.5-flash-image`) |
| **Text model** | `gemini-2.5-flash` (parallel fallback for fast text) |
| **Architecture** | ONE-SHOT casting photo → PARALLEL per-scene (fast text + dedicated image call) |
| **Streaming** | SSE with `: keepalive` every 15s; stage events for progress tracking |
| **Image compression** | JPEG q85, max 1280px (~60-70% payload reduction) |
| **Thinking** | `thinking_level="MINIMAL"` for gemini-3.1+ only |
| **SDK pin** | `google-genai<1.67` (1.67 drops `thought_signature` from chat history) |

### Live Session (`GET /api/live-session/ws` — WebSocket)

Bidirectional voice storytelling via Gemini Live API.

| Component | Detail |
|---|---|
| **Audio model** | `gemini-2.5-flash-native-audio-latest` (Charon voice) |
| **Image model** | `gemini-3.1-flash-image-preview` (via function calling) |
| **Protocol** | Browser ↔ WebSocket ↔ Backend ↔ Gemini Live API (bidirectional) |
| **Function calling** | `generate_scene_image()`, `search_historical_context()` mid-narration |
| **Turn states** | listening (green), narrating (dimmed), generating (amber) |
| **VAD** | RMS threshold (~0.01) skips silence; mute during playback |

### Live Video (`POST /api/live-video/generate` — SSE)

Veo scene-to-video generation with camera motion directives.

| Component | Detail |
|---|---|
| **Model** | `veo-3.1-generate-preview` (fallback: `veo-3.0-fast-generate-001`) |
| **Cost** | $0.15/sec (fast) x 6s = $0.90/scene |
| **Camera directives** | 7 categories: intimate, chase, establishing, revelation, dialogue, tracking, contemplative |
| **Assembly** | `POST /api/live-video/assemble` — ffmpeg concat with optional narration |
| **Demo fallback** | `GET /api/live-video/demo-fallback` — pre-baked assets |

### Live Voice

| Endpoint | Description |
|---|---|
| `POST /api/live-voice/narrate` | Text → WAV via Gemini TTS (Charon voice) |
| `POST /api/live-voice/narrate-stream` | Streaming PCM16 narration via `generate_content_stream` |
| `POST /api/live-voice/prompt` | Audio → transcript + creative response |

---

## LLM Provider Routing

ChronoCanvas supports four LLM providers via a pluggable `LLMRouter`:

| Provider | SDK | Model default | Capabilities |
|---|---|---|---|
| **Gemini** | `google.genai.Client` | `gemini-2.5-flash` | Text, streaming, JSON mode, **Google Search grounding**, multimodal vision, TTS |
| **Claude** | `anthropic` | `claude-sonnet-4-5-20250929` | Text, streaming, JSON mode |
| **OpenAI** | `openai` | `gpt-4o` | Text, streaming, JSON mode |
| **Ollama** | HTTP API | `llama3.1:8b` | Text, streaming (local only) |

### Routing priority (highest to lowest)

1. **Per-agent RuntimeConfig override** — from ConfigHUD UI, per-request: `{"llm": {"agent_routing": {"research": "claude"}}}`
2. **Per-agent env var override** — `LLM_AGENT_ROUTING='{"prompt_generation": "claude"}'`
3. **Global RuntimeConfig provider** — from ConfigHUD: `{"llm": {"provider": "gemini"}}`
4. **Deployment mode default** — `DEPLOYMENT_MODE=gcp` → Gemini, `local` → Ollama, `hybrid` → Gemini

### Fallback chain

If the preferred provider is unavailable, the router tries other available providers. In **strict Gemini mode** (`HACKATHON_STRICT_GEMINI=true`), if Gemini is unavailable the router raises `GeminiUnavailableError` (503) instead of falling back — ensuring hackathon demos run exclusively on Google AI.

### Cost tracking

Every LLM call records provider, model, input/output tokens, cost, and duration. The `CostTracker` aggregates costs per provider/model/task. All calls are stored in the pipeline state's `llm_calls` list and persisted to the audit trail in PostgreSQL.

---

## Image Generation

| Provider | SDK/Protocol | Model | Cost | Notes |
|---|---|---|---|---|
| **Imagen 4** (default) | `google.genai` `generate_images()` | `imagen-4.0-fast-generate-001` | $0.02/image | Aspect ratio auto-mapped from requested dimensions. Retry with exponential backoff for rate limits/503s. |
| **ComfyUI** | HTTP + WebSocket | SDXL or FLUX | — | External process; workflow submitted via `/prompt` endpoint |
| **Stable Diffusion** | HTTP API | Configurable | — | Via A1111/Forge API |
| **Mock** | — | — | Free | Returns placeholder images for testing |

Set via `IMAGE_PROVIDER` env var. The ConfigHUD UI can override per-request via `RuntimeConfig`.

---

## Configuration Reference

All configuration is via environment variables. Copy `.env.example` to `.env` to get started.

> **Source of truth**: `backend/src/chronocanvas/config.py` (`Settings` class)

### LLM providers

| Variable | Description | Default |
|---|---|---|
| `DEPLOYMENT_MODE` | Provider routing mode: `gcp` (cloud-only), `local` (local-only), `hybrid` (both) | `hybrid` |
| `GOOGLE_API_KEY` | Google API key (Gemini LLM, Imagen, TTS, multimodal, voice) | — |
| `GEMINI_MODEL` | Gemini model ID | `gemini-2.5-flash` |
| `ANTHROPIC_API_KEY` | Anthropic API key | — |
| `CLAUDE_MODEL` | Claude model ID | `claude-sonnet-4-5-20250929` |
| `OPENAI_API_KEY` | OpenAI API key | — |
| `OPENAI_MODEL` | OpenAI model | `gpt-4o` |
| `OLLAMA_BASE_URL` | Ollama endpoint | `http://localhost:11434` |
| `OLLAMA_MODEL` | Ollama model | `llama3.1:8b` |
| `LLM_AGENT_ROUTING` | Per-agent provider JSON, e.g. `{"research": "claude"}` | `{}` |

### Image generation

| Variable | Description | Default |
|---|---|---|
| `IMAGE_PROVIDER` | `imagen`, `comfyui`, `stable_diffusion`, or `mock` | `imagen` |
| `IMAGEN_MODEL` | Imagen model ID | `imagen-4.0-fast-generate-001` |
| `SD_API_URL` | Stable Diffusion API endpoint | `http://localhost:7860` |
| `COMFYUI_API_URL` | ComfyUI API endpoint | `http://localhost:8188` |
| `COMFYUI_MODEL` | `sdxl` or `flux` | `sdxl` |
| `COMFYUI_SDXL_CHECKPOINT` | SDXL checkpoint filename | `juggernautXL_v9.safetensors` |
| `PORTRAIT_WIDTH` | Portrait width in pixels | `1024` |
| `PORTRAIT_HEIGHT` | Portrait height in pixels | `1024` |
| `FACEFUSION_ENABLED` | Enable FaceFusion for facial compositing | `false` |
| `FACEFUSION_API_URL` | FaceFusion API endpoint | `http://localhost:7861` |

### Search and reference

| Variable | Description | Default |
|---|---|---|
| `SERPAPI_KEY` | SerpAPI key for face image web search | — |
| `PEXELS_API_KEY` | Pexels stock image API key | — |
| `UNSPLASH_ACCESS_KEY` | Unsplash stock image API key | — |

### Voice and TTS

| Variable | Description | Default |
|---|---|---|
| `TTS_ENABLED` | Enable narration audio synthesis | `true` |
| `TTS_MODEL` | Gemini TTS model | `gemini-2.5-flash-preview-tts` |
| `TTS_VOICE` | TTS voice name | `Kore` |
| `VOICE_INPUT_ENABLED` | Enable speech-to-text voice input | `true` |

### Multimodal and interactivity

| Variable | Description | Default |
|---|---|---|
| `IMAGE_TO_STORY_ENABLED` | Enable image-to-story (upload image, get storyboard) | `true` |
| `VISION_NARRATION_ENABLED` | Enable vision-based narration | `true` |
| `VIDEO_ASSEMBLY_ENABLED` | Enable MP4 video assembly from storyboard | `true` |
| `SCENE_EDITING_ENABLED` | Enable per-scene edit instructions | `true` |
| `CONVERSATION_MODE_ENABLED` | Enable conversational storyboard refinement | `false` |

### Pipeline toggles

| Variable | Description | Default |
|---|---|---|
| `VALIDATION_RETRY_ENABLED` | When `false`, validation scores but never triggers regeneration | `true` |
| `FACE_SEARCH_ENABLED` | When `false`, face_search node is skipped entirely | `true` |

### Research cache

| Variable | Description | Default |
|---|---|---|
| `RESEARCH_CACHE_ENABLED` | Enable pgvector semantic research cache | `true` |
| `RESEARCH_CACHE_THRESHOLD` | Cosine similarity threshold for cache hit | `0.85` |
| `RESEARCH_CACHE_MODEL` | Sentence-transformer model for embeddings | `all-MiniLM-L6-v2` |

### Invariant checks

| Variable | Description | Default |
|---|---|---|
| `INVARIANT_CHECKS_ENABLED` | Run pre/postcondition checks on pipeline nodes | `true` |
| `INVARIANT_STRICT` | Raise on violation (`true`) vs log warning (`false`) | `false` |

### Hackathon mode

| Variable | Description | Default |
|---|---|---|
| `DEPLOYMENT_MODE` | `gcp` auto-enables hackathon mode + strict Gemini via validator in config.py | `hybrid` |
| `HACKATHON_STRICT_GEMINI` | LLM router fails fast (503) instead of falling back away from Gemini | `false` (auto-set by `gcp` mode) |

Setting `DEPLOYMENT_MODE=gcp` automatically sets `hackathon_mode=True` and `hackathon_strict_gemini=True` via the `_unify_gcp_and_hackathon()` validator. No separate `HACKATHON_MODE` env var is needed. The `/api/health` endpoint exposes `hackathon_mode`, `deployment_mode`, and a `services` availability map.

### Auth gate

| Variable | Description | Default |
|---|---|---|
| `APP_PASSWORD` | When set, requires HMAC-signed session cookie (7-day TTL) on all API/WS routes | — (open access) |

WebSocket upgrade requests bypass the auth middleware (BaseHTTPMiddleware + WS incompatible). Login/check/logout via `/api/auth/*`.

### Database and cache

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string (asyncpg format) | `postgresql+asyncpg://chronocanvas:chronocanvas@localhost:5432/chronocanvas` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |

### Application

| Variable | Description | Default |
|---|---|---|
| `API_HOST` | API bind address | `0.0.0.0` |
| `API_PORT` | API bind port | `8000` |
| `CORS_ORIGINS` | JSON array of allowed origins | `["http://localhost:3000"]` |
| `SECRET_KEY` | Secret for signing tokens — **change in production** | (required) |
| `CONTENT_MODERATION_ENABLED` | Enable keyword input validation | `true` |
| `OUTPUT_DIR` | Directory for generated images | `./output` |
| `UPLOAD_DIR` | Directory for uploaded images | `./uploads` |
| `RATE_LIMIT_RPM` | API rate limit (requests per minute) | `60` |
| `LLM_MAX_CONCURRENT` | Max concurrent LLM calls | `5` |
| `LOG_LEVEL` | Logging level | `INFO` |

### Production feature flags

| Variable | Description | Default |
|---|---|---|
| `ENABLE_ADMIN_API` | Enable admin API endpoints | `true` |
| `ENABLE_AUDIT_UI` | Enable audit detail endpoint | `true` |
| `ENABLE_FACE_UPLOAD` | Enable face upload endpoint | `true` |

### Per-request configuration (ConfigHUD)

Generation requests can include a `config` payload that overrides global settings for that run. This is parsed into a `RuntimeConfig` dataclass (`backend/src/chronocanvas/runtime_config.py`) which provides per-channel overrides for LLM provider, image provider, per-agent routing, search toggles, TTS, vision features, and compositing.

```json
{
  "mode": "gcp",
  "llm": {"provider": "gemini", "model": "gemini-2.5-flash", "agent_routing": {"research": "gemini"}},
  "image": {"provider": "imagen"},
  "voice": {"tts_enabled": true, "tts_voice": "Kore"},
  "vision": {"image_to_story": true},
  "post": {"video_assembly": true}
}
```

When an override is not set, the global `.env` setting is used.

### Service availability

The `/api/health` endpoint returns a `services` object showing which providers are available (keys configured and reachable). This powers the ConfigHUD.

```json
{
  "status": "ok",
  "deployment_mode": "hybrid",
  "hackathon_mode": false,
  "services": {
    "llm": {"gemini": true, "claude": false, "openai": false, "ollama": true},
    "image": {"imagen": true, "comfyui": false, "stable_diffusion": false},
    "search": {"serpapi": true, "pexels": false, "unsplash": false},
    "tts": true,
    "facefusion": false
  }
}
```

In hackathon mode, the health endpoint also runs `validate_hackathon_requirements()` which checks that `GOOGLE_API_KEY` is set, `IMAGE_PROVIDER` is not `mock`, and returns warnings if any critical services are missing.

---

## API Endpoints

### Core

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Health check with service availability map, deployment mode, hackathon status |
| `POST` | `/api/generate` | Create generation request (portrait or story pipeline) |
| `POST` | `/api/generate/batch` | Batch generation (portrait pipeline) |
| `GET` | `/api/generate` | List generation requests (paginated, filterable by status) |
| `GET` | `/api/generate/{id}` | Get generation request details |
| `DELETE` | `/api/generate/{id}` | Delete generation request + cleanup files |
| `GET` | `/api/generate/{id}/images` | Get generated images for a request |
| `GET` | `/api/generate/{id}/audit` | Full audit trail (agent trace, LLM calls, costs) |
| `POST` | `/api/generate/{id}/retry` | Retry from a specific pipeline step |
| `POST` | `/api/generate/{id}/scenes/{idx}/edit` | Edit a specific scene with natural language instruction |
| `POST` | `/api/generate/{id}/feedback` | Submit feedback on a generation |
| `GET` | `/api/generate/{id}/feedback` | List feedback for a generation |
| `WS` | `/ws/{request_id}` | Real-time streaming (LLM tokens, progress, artifacts) |

### Reference and input

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/reference-images/upload` | Upload reference images for style/location guidance |
| `POST` | `/api/voice/transcribe` | Speech-to-text via Gemini multimodal |
| `POST` | `/api/conversation/{id}/chat` | Conversational storyboard refinement |
| `POST` | `/api/faces/upload` | Upload face image for compositing |

### Live features

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/live-story/generate` | SSE — generate Live Story (text + images streamed per scene) |
| `GET` | `/api/live-session/ws` | WebSocket — bidirectional voice storytelling session |
| `POST` | `/api/live-video/generate` | SSE — generate Veo video clips per scene |
| `POST` | `/api/live-video/assemble` | Assemble scene videos into single MP4 |
| `GET` | `/api/live-video/demo-fallback` | Pre-baked demo assets |
| `POST` | `/api/live-voice/narrate` | Text-to-speech narration (WAV) |
| `POST` | `/api/live-voice/narrate-stream` | Streaming PCM16 narration |
| `POST` | `/api/live-voice/prompt` | Audio prompt → transcript + creative response |

### Auth

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/auth/login` | Authenticate with APP_PASSWORD |
| `GET` | `/api/auth/check` | Check session validity |
| `POST` | `/api/auth/logout` | Clear session cookie |
| `GET` | `/api/config/` | Get deployment config (hackathon_mode, features) |

### Configuration and management

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/config/validate` | Validate ConfigHUD payload against available services and deployment mode |
| `GET` | `/api/figures` | List historical figures from the seed library |
| `GET` | `/api/timeline` | Timeline visualization data |
| `GET` | `/api/agents` | Agent status and configuration |
| `GET` | `/api/memory` | Research cache statistics |
| `GET` | `/api/eval` | Evaluation viewer data |
| `GET/POST` | `/api/admin/*` | Admin endpoints (conditionally enabled) |
| `GET` | `/api/export/*` | Export endpoints |
| `GET` | `/api/validation/*` | Validation management endpoints |

---

## Frontend Architecture

React 18 SPA with client-side routing (no React Router — uses a Zustand `navigation` store).

### Pages

| Page | Path | Description |
|---|---|---|
| **ModeSelector** | `/` | Choose between Historical Lens (portrait) and Story Director (storyboard). In hackathon mode, auto-redirects to Story Director. |
| **Generate** | `/generate` | Main generation UI — ConfigHUD, text/voice input, image upload, real-time pipeline progress, storyboard viewer |
| **Dashboard** | `/dashboard` | Generation overview and statistics |
| **FigureLibrary** | `/figures` | Browse seed historical figures |
| **Timeline** | `/timeline` | Timeline visualization |
| **Validate** | `/validate` | Validation review |
| **AuditList** | `/audit` | List of audit trails |
| **AuditDetail** | `/audit/{id}` | Full audit detail — agent trace, LLM calls, cost timeline |
| **Review** | `/review/{id}` | Generation review with feedback |
| **Memory** | `/memory` | Research cache statistics |
| **EvalViewer** | `/eval` | Evaluation results viewer |
| **Admin** | `/admin` | Admin panel |
| **Export** | `/export` | Export management |
| **LiveStory** | `/live-story` | Full-screen flip-o-rama storyboard with narration |
| **LiveSession** | `/live-session` | Bidirectional voice storytelling with Dash |
| **Login** | `/login` | Password gate (when APP_PASSWORD set) |
| **Guide** | `/guide` | User guide |

### Key components

- **ConfigHUD** (`components/config/ConfigHUD.tsx`) — Pre-generation mixing board. Reads available services from `/api/health`, lets user select LLM provider, image provider, TTS, voice, vision features per-request. Validates selections via `/api/config/validate` before submission.
- **StoryboardView** (`components/generation/StoryboardView.tsx`) — Renders storyboard panels with images, narration text, coherence scores, and audio playback.
- **StreamingText** — Displays LLM tokens in real time via WebSocket.
- **DAGVisualizer** — Interactive pipeline graph showing node execution status.
- **PipelineStepper** — Step-by-step progress indicator for pipeline nodes.
- **CostTimeline** — Visualizes LLM call costs over time.
- **TrustCard** — Shows research citations and grounding sources.
- **VoiceInputButton** — Record and transcribe voice input via Gemini.
- **StoryConversationPanel** — Chat interface for conversational storyboard refinement.
- **PatienceMeter** — Estimated wait time indicator during generation.

### State management

- **Zustand** for navigation state and config store
- **React hooks** for API communication (`useGeneration`, `useGenerationWS`, `useConfig`, `useFigures`, `useAgents`, `useTimeline`, `useMemory`, `useEval`, `useValidationAdmin`)
- **WebSocket** for real-time streaming (LLM tokens, progress events, artifact delivery)

---

## Two-Mode Operation

| Setting | Normal mode (`hybrid`/`local`) | Hackathon mode (`DEPLOYMENT_MODE=gcp`) |
|---|---|---|
| Landing page | Mode selector (portrait or story) | Auto-redirect to Story Director |
| Sidebar | All nav items | Story Director + Live Story + Live Session (dev tools collapsed) |
| ConfigHUD | Visible | Hidden |
| Degradation | Graceful (fallback to other providers) | Fail-loud (strict Gemini, 503 on fallback) |
| Providers | Multi-provider (Gemini, Claude, OpenAI, Ollama) | Gemini-only |
| Live features | Available | Primary navigation items |

Nothing is deleted between modes — all features exist behind flags, fully reversible.

---

## Error Handling

- **LLM fallback chain**: If primary provider is unavailable, router tries others (unless strict Gemini mode)
- **Imagen retry**: Exponential backoff (2s, 4s, 8s) for rate limits, 503s, and timeouts
- **Non-fatal nodes**: Multimodal validation, storyboard coherence, narration audio, and image-to-story are non-fatal — failures log warnings and pipeline continues
- **Hackathon mode escalation**: In `HACKATHON_MODE=true`, non-fatal nodes become fatal (raise instead of skip) to surface issues during demo rather than silently degrading
- **Pipeline checkpointing**: LangGraph state checkpointed to PostgreSQL via `langgraph-checkpoint-postgres`. Pipeline can resume from last checkpoint after process restart.
- **Content moderation**: Keyword-based input validation at the API layer (configurable)
- **Config validation**: `/api/config/validate` endpoint checks provider availability and deployment mode constraints before generation starts
- **SSRF prevention**: `security.py:is_safe_url()` blocks outbound requests to private/loopback/link-local/cloud-metadata IPs
- **Rate limiting**: API-level rate limit (`RATE_LIMIT_RPM`) and LLM concurrency limit (`LLM_MAX_CONCURRENT`)

---

## Deployment

### Local Docker (development)

```bash
docker compose -f docker-compose.dev.yml up
```

Services: db, redis, api, worker, frontend. Bind mounts for hot reload.

### Local Docker (production)

```bash
docker compose up
```

Services: db, redis, api, worker, frontend. Named volumes.

### Cloud Run

Deployment scripts in `deploy/cloudrun/`:

| Script | Purpose |
|---|---|
| `scripts/00-env.sh` | Environment configuration |
| `scripts/01-enable-apis.sh` | Enable required GCP APIs |
| `scripts/02-create-infra.sh` | Provision Cloud SQL, Memorystore Redis, VPC connector |
| `scripts/03-setup-secrets.sh` | Store secrets in Secret Manager |
| `scripts/04-build-push.sh` | Build and push Docker images to Artifact Registry |
| `scripts/05-deploy-services.sh` | Deploy API, worker, frontend to Cloud Run |
| `scripts/06-verify.sh` | Verify deployment health |
| `deploy-all.sh` | Run all scripts in sequence |

Dockerfiles: `Dockerfile.api` (API + worker), `Dockerfile.frontend` (nginx).

### GKE (Kubernetes)

Full manifests in `deploy/gke/`: namespace, service account, PostgreSQL StatefulSet, Redis deployment, API deployment + HPA, worker deployment + HPA, frontend deployment, Ingress with managed TLS certificate, ConfigMap, Secrets, migration Job.

---

## Security

- **SSRF prevention** — blocks outbound requests to private, loopback, link-local, and cloud-metadata IP ranges
- **Magic-byte validation** — uploaded and downloaded images validated against known file signatures (JPEG, PNG, WebP)
- **Download size cap** — face images from web search capped at 5 MB
- **Security headers** — `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`
- **Input length limits** — search queries and text inputs bounded at the API layer
- **Path confinement** — `confine_path()` prevents directory traversal in file operations
- **Secret key validation** — app refuses to start with the insecure default `SECRET_KEY` when using PostgreSQL
- **Deployment mode enforcement** — GCP deployments (`DEPLOYMENT_MODE=gcp`) reject local-only providers (Ollama, ComfyUI, FaceFusion) at config validation time

**Authentication**: Optional password gate via `APP_PASSWORD` env var. When set, `AuthGateMiddleware` requires HMAC-signed session cookie on all API routes. WebSocket upgrades bypass middleware. See Auth gate section above.

---

## Service Dependencies

### PostgreSQL

SQLAlchemy with asyncpg. Migrations managed with Alembic. pgvector extension for research cache semantic similarity.

### Redis

1. **LangGraph state checkpointing** — persists pipeline state between steps via `langgraph-checkpoint-postgres` (Redis used for pub/sub, Postgres for durable checkpoints)
2. **Pub/sub streaming** — backend publishes LLM tokens and progress events to per-request Redis channels; WebSocket relay subscribes and forwards to the browser

### Worker (arq)

Background job queue processing portrait and story pipelines. Without the worker running, generation requests stay `pending`. Configured via `arq chronocanvas.worker.WorkerSettings`.

---

## Development

See [docs/development.md](docs/development.md).

## API Reference

See [docs/api.md](docs/api.md).
