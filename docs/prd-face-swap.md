# PRD: Face Swap with FaceFusion

## Problem

The app generates historically informed portraits of figures like Abraham Lincoln — period clothing, lighting, and setting are plausible with SDXL + Juggernaut XL. But the faces are generic. A teacher can't say "here's what Lincoln would look like if he were played by Daniel Day-Lewis." The educational value comes from bridging the gap between historical context and recognizable contemporary faces.

## Vision

Teachers upload a reference photo (an actor, a student, themselves) and pick a historical figure. The system generates a period-plausible portrait and swaps in the reference face. The result: a photorealistic image of a familiar face in historically informed clothing, setting, and context.

**Example use cases:**
- "Show me Keanu Reeves as Genghis Khan" — period Mongol armor, yurt backdrop, Keanu's face
- "What would I look like as Cleopatra?" — student uploads selfie, gets back Egyptian royal portrait with their face
- Teacher generates a set of "celebrity historical figures" for a lesson on the Renaissance

## Architecture

### Current Pipeline

```
input_text → extraction → research → prompt_generation → image_generation → validation → export
```

### Proposed Pipeline

```
input_text → extraction → research → prompt_generation → image_generation → validation → face_swap → export
                                                                                           ↑
                                                                                    source_face_path
                                                                                   (uploaded by user)
```

Face swap is a **new node** inserted between validation and export. It only runs when a source face image is provided. When no source face is uploaded, the pipeline behaves exactly as it does today.

### New Node: `face_swap`

**Input from state:**
- `image_path` — the SDXL-generated historical portrait (target)
- `source_face_path` — user-uploaded reference photo (source face to swap in)

**Output to state:**
- `swapped_image_path` — the final face-swapped image
- `original_image_path` — preserved reference to the pre-swap portrait

**Behavior:**
1. If `source_face_path` is not set, pass through (no-op)
2. Call FaceFusion API with source face + target portrait
3. Save result to `{output_dir}/{request_id}/`
4. Update state with both original and swapped paths

### FaceFusion API Contract

FaceFusion exposes a REST API (already stubbed in `facefusion_client.py`):

```
POST /api/process
Content-Type: multipart/form-data

source_image: <file>   # reference face photo
target_image: <file>   # SDXL-generated portrait
```

Response: the swapped image bytes.

FaceFusion must run as a separate service. It requires its own GPU/MPS access for the face detection + swap models (inswapper_128, etc.).

### FaceFusion Service

Add to `docker-compose.dev.yml` or run standalone on the host (MPS). FaceFusion is Python-based and can run as:

```bash
facefusion run --execution-providers coreml  # macOS MPS
# or expose via API mode
facefusion api-run --host 0.0.0.0 --port 7861
```

For Docker, a custom image is needed since FaceFusion doesn't ship an official one. Start with host-based execution for dev.

## Data Model Changes

### `GenerationRequest`

No schema change. The `agent_trace` JSONB array already supports arbitrary agent entries. Face swap results append to the existing trace.

### `GeneratedImage`

Add a new record for the swapped image. The `provider` field already supports `"facefusion"`. Both the original SDXL image and the swapped image are stored as separate `GeneratedImage` rows linked to the same request.

### New: `source_face` storage

User-uploaded face images are stored at `{upload_dir}/faces/{uuid}.{ext}`. The upload endpoint returns a `face_id` that's passed with the generation request.

## API Changes

### Upload Face

```
POST /api/faces/upload
Content-Type: multipart/form-data
Body: file=<image>

Response 201:
{
  "face_id": "uuid",
  "file_path": "/uploads/faces/uuid.png",
  "created_at": "..."
}
```

Basic validation: image format (JPEG/PNG), max size (10MB), face detection check (at least one face found).

### Modified Generation Request

```
POST /api/generate
{
  "input_text": "Julius Caesar during the Roman Republic",
  "face_id": "uuid"          // optional — triggers face swap
}
```

When `face_id` is provided:
1. Look up the uploaded face image path
2. Pass `source_face_path` into the agent state
3. Pipeline runs face_swap node after validation

### Generation Response

Existing response schema works. Add to the response:

```json
{
  "images": [
    { "provider": "comfyui", "file_path": "...", "label": "original" },
    { "provider": "facefusion", "file_path": "...", "label": "face_swap" }
  ],
  "source_face_id": "uuid"
}
```

## Frontend Changes

### Generate Page

1. **Face upload area** — drag-and-drop or file picker above the text input
   - Shows thumbnail preview of uploaded face
   - "Remove" button to clear
   - Optional: face library showing previously uploaded faces
2. **Text input** — unchanged ("Describe a historical figure...")
3. **Generate button** — unchanged, now sends `face_id` with request
4. **Progress view** — add "Swapping face..." step after "Validating..."
5. **Result view** — show both images side-by-side:
   - Left: original SDXL portrait (historical figure with generic face)
   - Right: face-swapped version (historical figure with uploaded face)

### Audit Detail Page

- Show source face thumbnail
- Show original vs swapped images
- Face swap duration in agent trace

### Export Page

- Download options: "Original Portrait" / "Face-Swapped Portrait" / "Both"

## Agent State Changes

Add to `AgentState` TypedDict:

```python
# Face swap
source_face_path: str      # path to uploaded reference face
swapped_image_path: str     # path to face-swapped result
original_image_path: str    # preserved pre-swap portrait path
face_swap_params: dict      # FaceFusion parameters used
```

## Graph Changes

```python
# In graph.py — add face_swap node and conditional edge
graph.add_node("face_swap", face_swap_node)

# Replace: validation → export
# With: validation → face_swap → export
# face_swap is a no-op when source_face_path is not set
```

## FaceFusion Configuration

Add to `config.py` / `.env`:

```
FACEFUSION_API_URL=http://localhost:7861     # already exists
FACEFUSION_FACE_ENHANCER=gfpgan_1.4         # post-swap face enhancement
FACEFUSION_FACE_SWAPPER=inswapper_128       # swap model
```

## Quality Considerations

### Face Enhancement

After swap, faces can look slightly blurry or misaligned. FaceFusion supports post-processing with GFPGAN or CodeFormer to enhance the swapped face. This should be enabled by default.

### Face Detection Failures

If FaceFusion can't detect a face in either the source or target image:
- Log the failure in agent_trace
- Return the original SDXL portrait (graceful degradation)
- Mark in response: `face_swap_status: "failed"` with reason

### Multiple Faces

If the SDXL portrait contains multiple faces (unlikely for portraits but possible), FaceFusion should only swap the primary/largest face. Source images with multiple faces should use the largest detected face.

## Scope

### Phase 1 (MVP)
- Face upload endpoint with basic validation
- `face_swap` agent node calling FaceFusion API
- Pipeline integration (conditional node after validation)
- Frontend: face upload on Generate page, side-by-side results
- Store both original and swapped images

### Phase 2 (Follow-up)
- Face library — browse/reuse previously uploaded faces
- Batch swap — one face across multiple historical figures
- Face enhancement tuning (GFPGAN vs CodeFormer, strength slider)
- Comparison slider UI (drag to reveal original vs swapped)

## Dependencies

- **FaceFusion** running as API service (port 7861)
- **inswapper_128** model downloaded (~500MB)
- **GFPGAN 1.4** model for face enhancement (~350MB)
- MPS/CUDA for acceptable performance (~5-10s per swap on MPS)

## Non-Goals

- Real-time video face swap
- Training custom face models
- Age progression/regression
- Multiple face swaps in single image
