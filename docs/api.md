# ChronoCanvas — API Reference

The backend exposes a REST API at `http://localhost:8000`. Interactive documentation (Swagger UI) is available at `http://localhost:8000/docs`.

---

## Generation

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/generate` | Submit a new generation request |
| `GET` | `/api/generate` | List generation requests (supports `?status=`, `?offset=`, `?limit=`) |
| `GET` | `/api/generate/{id}` | Get status and metadata for a generation |
| `GET` | `/api/generate/{id}/audit` | Full audit detail: LLM calls, validation, state snapshots |
| `GET` | `/api/generate/{id}/images` | List generated images for a request |
| `POST` | `/api/generate/{id}/retry` | Retry a failed or completed generation from a specific step |
| `DELETE` | `/api/generate/{id}` | Delete a generation and its output files |

### POST `/api/generate`

```json
{
  "input_text": "Aryabhata, Indian mathematician, 5th century CE",
  "figure_id": "optional-uuid",
  "face_id": "optional-face-uuid"
}
```

Returns a `GenerationResponse` with `id` and `status: "pending"`.

### POST `/api/generate/{id}/retry`

Query parameter: `?from_step=<step_name>`

Valid steps: `extraction`, `research`, `prompt_generation`, `image_generation`, `validation`, `export`.

Only allowed when `status` is `"failed"` or `"completed"`.

---

## Figures

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/figures` | List figures (supports `?search=`, `?offset=`, `?limit=`) |
| `GET` | `/api/figures/{id}` | Get a figure by ID |
| `POST` | `/api/figures` | Create a figure |
| `PUT` | `/api/figures/{id}` | Update a figure |
| `DELETE` | `/api/figures/{id}` | Delete a figure |

---

## Timeline

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/timeline/figures` | List figures filtered by birth year range |

Query parameters: `?year_min=` (default `-500`), `?year_max=` (default `1700`), `?limit=` (default `300`).

Birth years use signed integers: negative = BCE, positive = CE.

---

## Faces

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/faces/upload` | Upload a reference face image (JPEG, PNG, WebP; max 10 MB) |

Returns `{"face_id": "...", "file_path": "..."}`. Pass `face_id` to `POST /api/generate` to use the uploaded face.

---

## Export

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/export/{id}` | Download a ZIP archive containing the portrait and JSON metadata |

---

## Agents

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/agents/status` | Health status of all agent nodes and LLM providers |
| `GET` | `/api/agents/metrics` | Aggregated LLM usage and cost metrics |
| `GET` | `/api/agents/costs` | Per-provider cost breakdown |

---

## WebSocket

### `WS /ws/generation/{request_id}`

Connect to receive real-time events for a generation. The server publishes events as JSON messages.

| `type` | Fields | Description |
|---|---|---|
| `llm_token` | `agent`, `token` | A single token streamed from an LLM response |
| `llm_stream_end` | `agent` | The LLM stream for this agent step has completed |
| `image_progress` | `step`, `total` | Diffusion sampling step progress |
| `agent_complete` | `agent`, `status` | An agent node has finished |
| `completed` | `status`, `result` | Generation finished successfully |
| `failed` | `status`, `error` | Generation failed |

Reconnect on disconnect — the backend will replay the current state on reconnect.

---

## Static files

Generated images are served from `/output/{request_id}/`. Uploaded face images are served from `/uploads/faces/`. Both paths are read-only static mounts.
