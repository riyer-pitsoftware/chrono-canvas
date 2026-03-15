# ChronoCanvas — API Reference

The backend exposes a REST API at `http://localhost:8000`. Interactive documentation (Swagger UI) is available at `http://localhost:8000/docs`.

All REST endpoints are prefixed with `/api`.

---

## Health

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Service health check with provider availability |

### GET `/api/health`

Returns service status, deployment mode, hackathon mode flag, and availability of all configured providers (LLM, image, search, TTS, FaceFusion). In hackathon mode, includes `hackathon_warnings` if critical services are misconfigured, and status becomes `"degraded"`.

Response:

```json
{
  "status": "ok",
  "service": "chronocanvas",
  "deployment_mode": "local",
  "hackathon_mode": false,
  "services": {
    "llm": { "gemini": true, "claude": false, "openai": false, "ollama": false },
    "image": { "imagen": true, "comfyui": false, "stable_diffusion": false },
    "search": { "serpapi": false, "pexels": false, "unsplash": false },
    "tts": true,
    "facefusion": false
  }
}
```

---

## Generation

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/generate` | Submit a new generation request (portrait or story) |
| `POST` | `/api/generate/batch` | Submit multiple generation requests at once |
| `GET` | `/api/generate` | List generation requests (supports `?status=`, `?offset=`, `?limit=`) |
| `GET` | `/api/generate/{id}` | Get status and metadata for a generation |
| `GET` | `/api/generate/{id}/audit` | Full audit detail: LLM calls, validation, state snapshots |
| `GET` | `/api/generate/{id}/images` | List generated images for a request |
| `POST` | `/api/generate/{id}/retry` | Retry a failed or completed generation from a specific step |
| `POST` | `/api/generate/{id}/scenes/{scene_index}/edit` | Edit a specific scene in a story storyboard |
| `POST` | `/api/generate/{id}/feedback` | Submit feedback on a generation step |
| `GET` | `/api/generate/{id}/feedback` | List feedback for a generation |
| `DELETE` | `/api/generate/{id}` | Delete a generation and its output files |

### POST `/api/generate`

```json
{
  "input_text": "Aryabhata, Indian mathematician, 5th century CE",
  "figure_id": "optional-uuid",
  "face_id": "optional-32-char-hex",
  "run_type": "portrait",
  "ref_image_id": "optional-32-char-hex",
  "ref_image_ids": ["optional-32-char-hex"],
  "provider_override": "optional-provider-name",
  "config": {}
}
```

- `run_type`: `"portrait"` (default) or `"creative_story"`.
- `face_id`: 32-char hex from the face upload endpoint. Used for portrait mode face swapping.
- `ref_image_id`: 32-char hex from the reference image upload endpoint. Used for image-to-story.
- `ref_image_ids`: Up to 5 reference image IDs for style/location/character references (story mode).
- `config`: Per-request config overrides from ConfigHUD (passed through to RuntimeConfig).

Returns `201` with a `GenerationResponse`:

```json
{
  "id": "uuid",
  "figure_id": "uuid | null",
  "input_text": "...",
  "run_type": "portrait",
  "status": "pending",
  "current_agent": null,
  "extracted_data": null,
  "research_data": null,
  "generated_prompt": null,
  "error_message": null,
  "agent_trace": null,
  "llm_calls": null,
  "llm_costs": null,
  "storyboard_data": null,
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### POST `/api/generate/batch`

```json
{
  "items": [
    { "input_text": "...", "figure_id": "optional-uuid" },
    { "input_text": "..." }
  ]
}
```

Returns `201` with:

```json
{
  "request_ids": ["uuid", "uuid"],
  "total": 2
}
```

### GET `/api/generate`

Query parameters: `?status=`, `?offset=` (default 0), `?limit=` (default 20).

Returns:

```json
{
  "items": [ GenerationResponse, ... ],
  "total": 42
}
```

### GET `/api/generate/{id}/audit`

Returns `AuditDetailResponse` with full pipeline trace. Requires `ENABLE_AUDIT_UI=true` (returns 404 otherwise).

```json
{
  "id": "uuid",
  "input_text": "...",
  "status": "completed",
  "current_agent": null,
  "figure_name": "...",
  "created_at": "datetime",
  "updated_at": "datetime",
  "extracted_data": {},
  "research_data": {},
  "generated_prompt": "...",
  "error_message": null,
  "total_cost": 0.04,
  "total_duration_ms": 12345.0,
  "llm_calls": [
    {
      "agent": "extraction",
      "timestamp": 1234567890.0,
      "provider": "gemini",
      "model": "gemini-2.0-flash",
      "input_tokens": 100,
      "output_tokens": 200,
      "cost": 0.01,
      "duration_ms": 500.0,
      "fallback": false
    }
  ],
  "validation_score": 85.0,
  "validation_passed": true,
  "validation_categories": [
    { "category": "historical_accuracy", "rule_name": "...", "passed": true, "score": 0.9 }
  ],
  "images": [ ImageResponse, ... ],
  "state_snapshots": [ { "agent": "...", "snapshot": {} } ],
  "agent_trace": [],
  "storyboard_data": {},
  "narration_audio_urls": [],
  "run_type": "portrait"
}
```

### GET `/api/generate/{id}/images`

Returns a list of `ImageResponse`:

```json
[
  {
    "id": "uuid",
    "request_id": "uuid",
    "figure_id": "uuid | null",
    "file_path": "/output/.../image.png",
    "thumbnail_path": "... | null",
    "prompt_used": "...",
    "provider": "imagen",
    "width": 1024,
    "height": 1024,
    "validation_score": 85.0,
    "created_at": "datetime"
  }
]
```

### POST `/api/generate/{id}/retry`

Query parameter: `?from_step=<step_name>`

Valid steps: see `VALID_RETRY_STEPS` in `services/generation.py` (e.g. `extraction`, `research`, `prompt_generation`, `image_generation`, `validation`, `export`).

Cannot retry when status is `"pending"`. Story pipelines are re-run from scratch.

Returns `202` with a `GenerationResponse`.

### POST `/api/generate/{id}/scenes/{scene_index}/edit`

Query parameter: `?instruction=<edit_instruction>`

Requires `SCENE_EDITING_ENABLED=true` (returns 503 otherwise). Only available for `creative_story` run type. Enqueues a background scene edit task.

Returns `202`:

```json
{ "status": "editing", "scene_index": 0 }
```

### POST `/api/generate/{id}/feedback`

```json
{
  "step_name": "extraction",
  "comment": "The date is wrong",
  "author": "reviewer1"
}
```

Returns `201` with a `FeedbackResponse`:

```json
{
  "id": "uuid",
  "request_id": "uuid",
  "step_name": "extraction",
  "comment": "The date is wrong",
  "author": "reviewer1",
  "created_at": "datetime"
}
```

### GET `/api/generate/{id}/feedback`

Returns:

```json
{
  "items": [ FeedbackResponse, ... ]
}
```

### DELETE `/api/generate/{id}`

Deletes the generation record and cleans up output files on disk. Returns `204`.

---

## Live Story

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/live-story/generate` | Generate a live story via SSE (Server-Sent Events) |

### POST `/api/live-story/generate`

Streams a multi-scene visual story in real-time using Gemini native image generation.

```json
{
  "prompt": "A detective follows a cold trail through rain-soaked streets",
  "num_scenes": 4,
  "style": "noir"
}
```

SSE event types:

| `type` | Fields | Description |
|---|---|---|
| `stage` | `stage`, `status`, `elapsed_s`, `scene_idx` | Pipeline stage progress (init/casting/scene/replay) |
| `scene` | `scene_idx`, `text`, `image` | Scene content (text and/or base64 JPEG image) |
| `error` | `message`, `scene_idx` | Error for a specific scene or overall |
| `done` | — | Stream complete |

Architecture: ONE-SHOT casting photo (scene 0, hidden) → PARALLEL per-scene text (gemini-2.5-flash, ~3s) + image (gemini-3.1-flash-image-preview, ~2min). SSE keepalives every 15s.

---

## Live Session

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/live-session/ws` | WebSocket — bidirectional voice storytelling |

### WS `/api/live-session/ws`

Persistent bidirectional WebSocket proxying to Gemini Live API. User speaks, Dash narrates back, images materialize via function calls.

Client → Server messages:

| `type` | Fields | Description |
|---|---|---|
| `start` | — | Begin session |
| `audio` | `data` (base64 PCM16) | Audio chunk from microphone |
| `stop` | — | End session |

Server → Client messages:

| `type` | Fields | Description |
|---|---|---|
| `audio` | `data` (base64 PCM16) | Narration audio chunk |
| `image` | `data` (base64 JPEG), `prompt` | Generated scene image |
| `status` | `status` | Turn state: `listening`, `narrating`, `generating` |
| `transcript` | `text` | Speech-to-text transcript |
| `ping` | — | Keepalive (every 20s) |
| `error` | `message` | Error message |

Models: `gemini-2.5-flash-native-audio-latest` (audio, Charon voice), `gemini-3.1-flash-image-preview` (images via function calling).

---

## Live Video

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/live-video/generate` | Generate Veo video clips per scene (SSE) |
| `POST` | `/api/live-video/assemble` | Assemble scene videos into single MP4 |
| `GET` | `/api/live-video/demo-fallback` | Pre-baked demo video assets |

### POST `/api/live-video/generate`

Generates Veo video clips from scene images. Streams progress via SSE.

```json
{
  "scenes": [
    { "image": "base64...", "text": "Scene description", "index": 0 }
  ]
}
```

SSE event types: `scene_video` (with base64 MP4), `scene_video_error`, `film_complete`, `stage`.

Models: `veo-3.1-generate-preview` (fallback: `veo-3.0-fast-generate-001`). Cost: $0.90/scene (6s clips).

### POST `/api/live-video/assemble`

Concatenates individual Veo clips into single MP4 via ffmpeg.

```json
{
  "videos": ["base64-mp4-1", "base64-mp4-2"],
  "narration_audio": "optional-base64-wav"
}
```

Returns assembled video as base64.

### GET `/api/live-video/demo-fallback`

Returns pre-baked demo assets from `demo/fallback/` directory (manifest.json + scene files).

---

## Live Voice

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/live-voice/narrate` | Text → WAV narration (Charon voice) |
| `POST` | `/api/live-voice/narrate-stream` | Text → streaming PCM16 narration |
| `POST` | `/api/live-voice/prompt` | Audio → transcript + creative response |

### POST `/api/live-voice/narrate`

```json
{ "text": "The rain fell like a confession nobody asked for." }
```

Returns WAV audio (24kHz PCM16 mono) via Gemini TTS with Charon voice.

### POST `/api/live-voice/narrate-stream`

Same input as `/narrate` but streams PCM16 audio chunks via SSE for lower latency.

### POST `/api/live-voice/prompt`

Upload audio file (multipart). Returns:

```json
{
  "transcript": "transcribed text",
  "response": "Dash's creative response"
}
```

---

## Auth

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/login` | Authenticate with APP_PASSWORD |
| `GET` | `/api/auth/check` | Check session validity |
| `POST` | `/api/auth/logout` | Clear session cookie |
| `GET` | `/api/config/` | Get deployment configuration |

### POST `/api/auth/login`

```json
{ "password": "your-password" }
```

Returns `200` with Set-Cookie (HMAC-signed, 7-day TTL) on success, `401` on failure.

### GET `/api/auth/check`

Returns `200` if session is valid, `401` otherwise.

### GET `/api/config/`

Returns deployment configuration flags consumed by the frontend:

```json
{
  "hackathon_mode": true,
  "deployment_mode": "gcp",
  "features": { ... }
}
```

---

## Figures

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/figures` | List figures (supports `?search=`, `?offset=`, `?limit=`) |
| `GET` | `/api/figures/{id}` | Get a figure by ID |
| `POST` | `/api/figures` | Create a figure |
| `PUT` | `/api/figures/{id}` | Update a figure |
| `DELETE` | `/api/figures/{id}` | Delete a figure |

### POST `/api/figures`

```json
{
  "name": "Hatshepsut",
  "birth_year": -1507,
  "death_year": -1458,
  "nationality": "Egyptian",
  "occupation": "Pharaoh",
  "description": "...",
  "physical_description": "...",
  "clothing_notes": "...",
  "period_id": "optional-uuid",
  "metadata_json": {}
}
```

All fields except `name` are optional.

### PUT `/api/figures/{id}`

Same shape as `POST`, but all fields are optional (partial update).

### FigureResponse

```json
{
  "id": "uuid",
  "name": "Hatshepsut",
  "birth_year": -1507,
  "death_year": -1458,
  "period_id": "uuid | null",
  "nationality": "Egyptian",
  "occupation": "Pharaoh",
  "description": "...",
  "physical_description": "...",
  "clothing_notes": "...",
  "metadata_json": {},
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### GET `/api/figures`

Query parameters: `?search=` (max 200 chars), `?offset=` (default 0), `?limit=` (default 50).

Returns:

```json
{
  "items": [ FigureResponse, ... ],
  "total": 120,
  "offset": 0,
  "limit": 50
}
```

---

## Timeline

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/timeline/figures` | List figures filtered by birth year range |

Query parameters: `?year_min=` (default `-500`), `?year_max=` (default `1700`), `?limit=` (default `300`).

Birth years use signed integers: negative = BCE, positive = CE.

Returns:

```json
{
  "items": [ FigureResponse, ... ],
  "total": 42,
  "year_min": -500,
  "year_max": 1700
}
```

---

## Faces

Requires `ENABLE_FACE_UPLOAD=true` in config. Disabled by default; the router is conditionally mounted.

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/faces/upload` | Upload a reference face image (JPEG, PNG, WebP; max 10 MB) |

Returns:

```json
{ "face_id": "32-char-hex", "file_path": "/uploads/faces/..." }
```

Pass `face_id` to `POST /api/generate` to use the uploaded face for portrait mode.

---

## Reference Images

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/reference-images/upload` | Upload a reference image for stories (JPEG, PNG, WebP; max 10 MB) |

Query parameters: `?ref_type=` (default `"story_source"`; allowed: `story_source`, `location`, `character`, `artifact`, `style_reference`), `?description=` (optional).

Returns:

```json
{
  "ref_id": "32-char-hex",
  "file_path": "/uploads/references/...",
  "mime_type": "image/jpeg",
  "ref_type": "story_source",
  "description": ""
}
```

Pass `ref_id` as `ref_image_id` or in `ref_image_ids` to `POST /api/generate` for story mode.

---

## Export

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/export/{id}/download` | Download the first generated image for a request |
| `GET` | `/api/export/{id}/audio/{scene_index}` | Download narration audio for a specific scene (WAV) |
| `GET` | `/api/export/{id}/video` | Download the storyboard video (MP4) |
| `GET` | `/api/export/{id}/metadata` | Get export metadata JSON |
| `GET` | `/api/export/{id}/bundle` | Download a ZIP bundle (citations.json, story.md, scene frames) |

### GET `/api/export/{id}/download`

Returns the image file as `image/png` with `Content-Disposition` header.

### GET `/api/export/{id}/audio/{scene_index}`

Returns the audio file as `audio/wav`. Scene index is zero-based.

### GET `/api/export/{id}/video`

Returns the video file as `video/mp4`.

### GET `/api/export/{id}/metadata`

Returns the JSON content of `export/metadata.json` from the request's output directory.

### GET `/api/export/{id}/bundle`

Returns a ZIP archive (`application/zip`) containing:
- `citations.json` — aggregated citations from research and storyboard
- `story.md` — formatted storyboard as Markdown
- `frames/` — scene images

---

## Validation

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/validation/{id}` | Get validation results for a generation request |

Returns a `ValidationSummary`:

```json
{
  "request_id": "uuid",
  "overall_score": 85.0,
  "passed": true,
  "results": [
    {
      "id": "uuid",
      "request_id": "uuid",
      "category": "historical_accuracy",
      "rule_name": "...",
      "passed": true,
      "score": 0.9,
      "details": "...",
      "suggestions": [],
      "created_at": "datetime"
    }
  ]
}
```

---

## Agents

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/agents` | List all agent nodes and their descriptions |
| `GET` | `/api/agents/llm-status` | LLM provider availability (per-provider boolean) |
| `GET` | `/api/agents/costs` | Aggregated LLM cost summary |

### GET `/api/agents`

Returns:

```json
{
  "agents": [
    { "name": "orchestrator", "description": "...", "status": "available" },
    { "name": "extraction", "description": "...", "status": "available" }
  ]
}
```

### GET `/api/agents/llm-status`

Returns:

```json
{
  "providers": { "gemini": true, "claude": false, "openai": false, "ollama": false }
}
```

### GET `/api/agents/costs`

Returns:

```json
{
  "total_cost": 0.12,
  "total_tokens": 15000,
  "by_provider": { "gemini": 0.10, "claude": 0.02 },
  "num_calls": 8
}
```

---

## Config

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/config/validate` | Validate a ConfigHUD payload before orchestration |

### POST `/api/config/validate`

Accepts any JSON object representing a ConfigHUD configuration. Validates provider availability and deployment mode constraints (GCP vs local).

```json
{
  "llm_provider": "gemini",
  "image_provider": "imagen",
  "tts_enabled": true,
  "facefusion_enabled": false,
  "mode": "gcp",
  "agent_routing": { "extraction": "gemini", "research": "gemini" }
}
```

Returns:

```json
{
  "valid": true,
  "errors": []
}
```

On validation failure:

```json
{
  "valid": false,
  "errors": [
    {
      "channel": "llm",
      "provider": "ollama",
      "error": "Provider 'ollama' is not available in GCP mode"
    }
  ]
}
```

---

## Voice

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/voice/transcribe` | Transcribe audio to text using Gemini multimodal |

Requires `VOICE_INPUT_ENABLED=true` (returns 503 otherwise).

Upload an audio file (form field `file`). Allowed types: `audio/webm`, `audio/wav`, `audio/wave`, `audio/x-wav`, `audio/ogg`, `audio/mpeg`, `audio/mp4`. Max 25 MB.

Returns:

```json
{
  "transcript": "transcribed text here",
  "duration_ms": 1234.5,
  "cost": 0.001
}
```

---

## Conversation

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/conversation/{id}/chat` | Chat with Gemini about a storyboard for refinement |
| `DELETE` | `/api/conversation/{id}` | End a conversation session |

### POST `/api/conversation/{id}/chat`

Requires `CONVERSATION_MODE_ENABLED=true` (returns 503 otherwise). The generation must have `storyboard_data` (returns 422 otherwise).

```json
{
  "message": "Make the second scene more dramatic"
}
```

Returns the Gemini response (shape varies by conversation service).

### DELETE `/api/conversation/{id}`

Clears the in-memory conversation session.

Returns:

```json
{ "status": "ended" }
```

---

## Memory (Research Cache)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/memory/stats` | Cache statistics: entries, hits, cost saved |
| `GET` | `/api/memory/entries` | List all cached research entries with stats |
| `DELETE` | `/api/memory/entries` | Clear all cached research entries |

### GET `/api/memory/stats`

Returns:

```json
{
  "total_entries": 12,
  "total_hits": 45,
  "estimated_cost_saved_usd": 1.23
}
```

### GET `/api/memory/entries`

Returns:

```json
{
  "entries": [
    {
      "id": "uuid",
      "figure_name": "Hatshepsut",
      "time_period": "New Kingdom",
      "region": "Egypt",
      "hit_count": 3,
      "cost_saved_usd": 0.15,
      "original_cost_usd": 0.05
    }
  ],
  "stats": { "total_entries": 12, "total_hits": 45, "estimated_cost_saved_usd": 1.23 }
}
```

### DELETE `/api/memory/entries`

Returns:

```json
{ "deleted_count": 12 }
```

---

## Eval Viewer

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/eval/runs` | List eval runs (supports `?condition=`, `?case_id=`, `?include_rejected=`) |
| `GET` | `/api/eval/runs/{run_id}` | Get detailed info for a single eval run |
| `POST` | `/api/eval/runs/{run_id}/reject` | Soft-reject an eval run |
| `POST` | `/api/eval/runs/{run_id}/unreject` | Remove soft-reject from an eval run |
| `GET` | `/api/eval/cases` | List all eval cases with their run summaries |
| `GET` | `/api/eval/cases/{case_id}` | Get a single eval case with all its runs |
| `GET` | `/api/eval/dashboard` | Get aggregated dashboard data across all conditions |

### GET `/api/eval/runs`

Query parameters: `?condition=` (optional), `?case_id=` (optional), `?include_rejected=` (default `false`).

Returns a list of `EvalRunSummary`:

```json
[
  {
    "run_id": "run_001",
    "case_id": "case_001",
    "condition": "baseline",
    "success": true,
    "image_url": "/eval-assets/...",
    "title": "...",
    "has_rating": true,
    "rejected": false
  }
]
```

### GET `/api/eval/runs/{run_id}`

Returns `EvalRunDetail` (extends `EvalRunSummary`):

```json
{
  "run_id": "...",
  "case_id": "...",
  "condition": "...",
  "success": true,
  "image_url": "...",
  "title": "...",
  "has_rating": true,
  "rejected": false,
  "manifest": {},
  "rating": {},
  "output_text": "..."
}
```

### POST `/api/eval/runs/{run_id}/reject`

Optional body:

```json
{ "reason": "bad output quality" }
```

Returns:

```json
{ "status": "rejected", "run_id": "..." }
```

### POST `/api/eval/runs/{run_id}/unreject`

Returns:

```json
{ "status": "unrejected", "run_id": "..." }
```

### GET `/api/eval/dashboard`

Returns:

```json
{
  "conditions": [ { ... } ],
  "dimension_scores": [
    { "condition": "baseline", "dimension": "accuracy", "mean": 0.85, "median": 0.87, "n": 10 }
  ],
  "failure_tags": [ { ... } ],
  "total_runs": 50,
  "total_rated": 40
}
```

---

## Admin

Requires `ENABLE_ADMIN_API=true` in config. Disabled by default; the router is conditionally mounted.

### Validation Rules

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/admin/validation/rules` | List all validation rules with pass threshold |
| `POST` | `/api/admin/validation/rules` | Create a new validation rule |
| `PUT` | `/api/admin/validation/rules/{rule_id}` | Update a validation rule's weight and enabled status |
| `DELETE` | `/api/admin/validation/rules/{rule_id}` | Delete a validation rule |
| `PUT` | `/api/admin/validation/threshold` | Update the global pass threshold |

#### GET `/api/admin/validation/rules`

Returns:

```json
{
  "rules": [
    {
      "id": "uuid",
      "category": "historical_accuracy",
      "display_name": "Historical Accuracy",
      "weight": 0.25,
      "description": "...",
      "enabled": true,
      "created_at": "datetime",
      "updated_at": "datetime"
    }
  ],
  "pass_threshold": 70.0
}
```

#### POST `/api/admin/validation/rules`

```json
{
  "category": "art_style",
  "display_name": "Art Style Consistency",
  "weight": 0.25,
  "description": "...",
  "enabled": true
}
```

`category` must match `^[a-z][a-z0-9_]*$`. Returns `201`. Returns `409` if category already exists.

#### PUT `/api/admin/validation/rules/{rule_id}`

```json
{
  "weight": 0.3,
  "enabled": true
}
```

`weight` is required (0.0 to 1.0). `enabled` is optional.

#### PUT `/api/admin/validation/threshold`

```json
{
  "pass_threshold": 75.0
}
```

`pass_threshold` must be between 0.0 and 100.0. Returns:

```json
{ "pass_threshold": 75.0 }
```

### Review Queue

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/admin/validation/queue` | List completed generations pending human review |
| `GET` | `/api/admin/validation/{id}` | Get validation detail for a specific request |
| `POST` | `/api/admin/validation/{id}/accept` | Accept a generation in review |
| `POST` | `/api/admin/validation/{id}/reject` | Reject a generation in review |
| `POST` | `/api/admin/validation/{id}/flag` | Flag a generation for further review |

#### GET `/api/admin/validation/queue`

Query parameters: `?skip=` (default 0), `?limit=` (default 50).

Returns completed generations that have not yet been reviewed:

```json
{
  "items": [
    {
      "request_id": "uuid",
      "input_text": "...",
      "figure_name": "...",
      "overall_score": 85.0,
      "categories": [
        { "category": "...", "rule_name": "...", "score": 0.9, "passed": true }
      ],
      "image_url": "/output/.../image.png",
      "human_review_status": null,
      "created_at": "datetime"
    }
  ],
  "total": 5
}
```

#### POST `/api/admin/validation/{id}/accept`, `/reject`, `/flag`

```json
{ "notes": "optional reviewer notes" }
```

Returns:

```json
{
  "request_id": "uuid",
  "status": "accepted",
  "notes": "..."
}
```

### Archive

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/admin/archive` | Archive old generation images and data |

Query parameters: `?older_than_days=` (default 2), `?dry_run=` (default `false`).

Returns a summary of archived (or would-be-archived) items.

---

## WebSocket

### `WS /ws/generation/{request_id}`

Connect to receive real-time events for a generation. The server relays messages from Redis pub/sub.

| `type` | Fields | Description |
|---|---|---|
| `llm_token` | `agent`, `token` | A single token streamed from an LLM response |
| `llm_stream_end` | `agent` | The LLM stream for this agent step has completed |
| `image_progress` | `step`, `total` | Diffusion sampling step progress |
| `agent_complete` | `agent`, `status` | An agent node has finished |
| `completed` | `status`, `result` | Generation finished successfully |
| `failed` | `status`, `error` | Generation failed |
| `ping` | | Server heartbeat (every 20s) |

Connection lifecycle:
- Auto-closes when generation reports `completed` or `failed`
- Idle timeout: 300 seconds with no progress events
- Slow-client protection: sends that take >5s trigger disconnect
- Reconnect on disconnect — the backend will replay the current state on reconnect

---

## Static Files

| Mount path | Description |
|---|---|
| `/output/{request_id}/` | Generated images and export artifacts |
| `/uploads/faces/` | Uploaded face images |
| `/uploads/references/` | Uploaded reference images |
| `/eval-assets/` | Eval run assets (mounted only if `eval/runs/` directory exists) |

All static paths are read-only mounts.
