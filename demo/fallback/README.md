# Demo Fallback Assets

Pre-baked Veo film clips for reliable hackathon demo presentations.
When live Veo generation fails, the frontend falls back to these cached assets.

## How to bake demo content

Run the bake script from the backend root (with the API server running locally):

```bash
python scripts/bake-demo.py "A jazz singer discovers a coded message hidden in a vinyl record, 1940s Harlem"
```

This will:
1. Call the local `/api/live-story/generate` endpoint with the prompt
2. Parse the SSE stream to collect scene text + images
3. Call `/api/live-video/generate` to produce Veo video clips for each scene
4. Save everything to `demo/fallback/`

## Directory structure after baking

```
demo/fallback/
  manifest.json       # Metadata: prompt, model, timestamp, scene_count
  scene_0.txt         # Scene 0 narration text
  scene_0.png         # Scene 0 image
  scene_0.mp4         # Scene 0 Veo video clip
  scene_1.txt
  scene_1.png
  scene_1.mp4
  ...
  film.mp4            # Assembled full film (all clips concatenated)
```

## How fallback works

1. Frontend calls `POST /api/live-video/generate` for Veo clips
2. If ALL scenes fail, frontend calls `GET /api/live-video/demo-fallback`
3. If pre-baked assets exist (manifest.json present), the endpoint serves them
4. Frontend displays the pre-baked clips with a "Demo Reel" badge
