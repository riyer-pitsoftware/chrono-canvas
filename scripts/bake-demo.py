#!/usr/bin/env python3
"""Bake a demo story + Veo film into demo/fallback/ for reliable presentations.

Usage:
    python scripts/bake-demo.py "A jazz singer discovers a coded message hidden in a vinyl record, 1940s Harlem"
    python scripts/bake-demo.py --prompt-file prompts/demo.txt
    python scripts/bake-demo.py --skip-video "A quick text prompt"   # only bake story, skip Veo

Requires the ChronoCanvas backend running locally (default: http://localhost:8000).
"""

import argparse
import base64
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

DEFAULT_API_BASE = "http://localhost:8000"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "demo" / "fallback"

# Timeout for SSE story generation (may take 2+ minutes)
STORY_TIMEOUT = 300.0
# Timeout for Veo film generation SSE (may take 5+ minutes for many scenes)
VIDEO_TIMEOUT = 600.0


def parse_sse_events(text: str) -> list[dict]:
    """Parse an SSE text stream into a list of JSON event dicts."""
    events = []
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    return events


def generate_story(api_base: str, prompt: str) -> list[dict]:
    """Call the live-story endpoint and return parsed SSE events."""
    print(f"  Generating story: {prompt[:80]}...")
    url = f"{api_base}/api/live-story/generate"
    body = {"prompt": prompt, "style": "noir"}

    with httpx.Client(timeout=STORY_TIMEOUT) as client:
        with client.stream("POST", url, json=body) as resp:
            resp.raise_for_status()
            raw = resp.read().decode("utf-8")

    events = parse_sse_events(raw)
    print(f"  Received {len(events)} SSE events from story generation")
    return events


def extract_scenes(events: list[dict]) -> list[dict]:
    """Pair text + image events into scenes."""
    scenes: list[dict] = []
    current_text = ""

    for evt in events:
        if evt.get("type") == "text":
            current_text = evt.get("content", "")
        elif evt.get("type") == "image":
            scenes.append({
                "text": current_text,
                "image_base64": evt.get("content", ""),
                "mime_type": evt.get("mime_type", "image/png"),
            })
            current_text = ""

    if not scenes:
        print("  WARNING: No scenes extracted from story events")
    else:
        print(f"  Extracted {len(scenes)} scenes")
    return scenes


def generate_videos(api_base: str, scenes: list[dict]) -> dict[int, str]:
    """Call Veo generate endpoint and return {scene_idx: video_base64}."""
    print(f"  Generating Veo video for {len(scenes)} scenes (this may take several minutes)...")
    url = f"{api_base}/api/live-video/generate"
    body = {
        "scenes": [
            {
                "text": s["text"],
                "image_base64": s["image_base64"],
                "mime_type": s.get("mime_type", "image/png"),
            }
            for s in scenes
        ]
    }

    videos: dict[int, str] = {}

    with httpx.Client(timeout=VIDEO_TIMEOUT) as client:
        with client.stream("POST", url, json=body) as resp:
            resp.raise_for_status()
            raw = resp.read().decode("utf-8")

    events = parse_sse_events(raw)
    for evt in events:
        if evt.get("type") == "scene_video":
            idx = evt["scene_idx"]
            videos[idx] = evt["video_base64"]
            print(f"    Scene {idx}: video generated ({evt.get('model', '?')}, {evt.get('elapsed_s', '?')}s)")
        elif evt.get("type") == "scene_video_error":
            print(f"    Scene {evt.get('scene_idx', '?')}: FAILED - {evt.get('error', 'unknown')}")

    print(f"  Got {len(videos)}/{len(scenes)} video clips")
    return videos


def assemble_film(api_base: str, videos: dict[int, str], scene_count: int) -> str | None:
    """Assemble clips into a single film. Returns base64 or None."""
    clips = [videos[i] for i in range(scene_count) if i in videos]
    if not clips:
        print("  No clips to assemble into film")
        return None

    print(f"  Assembling {len(clips)} clips into film...")
    url = f"{api_base}/api/live-video/assemble"
    body = {"video_base64_list": clips}

    with httpx.Client(timeout=120.0) as client:
        resp = client.post(url, json=body)
        if resp.status_code != 200:
            print(f"  Assembly failed: {resp.status_code} {resp.text[:200]}")
            return None
        data = resp.json()
        return data.get("video_base64")


def save_assets(
    output_dir: Path,
    prompt: str,
    scenes: list[dict],
    videos: dict[int, str],
    film_b64: str | None,
    model_info: str,
) -> None:
    """Write all assets to the output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save individual scenes
    for i, scene in enumerate(scenes):
        # Text
        (output_dir / f"scene_{i}.txt").write_text(scene["text"])

        # Image
        if scene.get("image_base64"):
            (output_dir / f"scene_{i}.png").write_bytes(
                base64.b64decode(scene["image_base64"])
            )

        # Video
        if i in videos:
            (output_dir / f"scene_{i}.mp4").write_bytes(
                base64.b64decode(videos[i])
            )

    # Assembled film
    if film_b64:
        (output_dir / "film.mp4").write_bytes(base64.b64decode(film_b64))
        print(f"  Saved assembled film")

    # Manifest
    manifest = {
        "prompt": prompt,
        "model": model_info,
        "scene_count": len(scenes),
        "video_count": len(videos),
        "has_film": film_b64 is not None,
        "baked_at": datetime.now(timezone.utc).isoformat(),
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"  Saved {len(scenes)} scenes to {output_dir}")


def main():
    parser = argparse.ArgumentParser(description="Bake demo story + Veo film for fallback")
    parser.add_argument("prompt", nargs="?", help="Story prompt text")
    parser.add_argument("--prompt-file", help="Read prompt from a file")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help="API base URL")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Output directory")
    parser.add_argument("--skip-video", action="store_true", help="Skip Veo video generation")
    args = parser.parse_args()

    # Get prompt
    if args.prompt_file:
        prompt = Path(args.prompt_file).read_text().strip()
    elif args.prompt:
        prompt = args.prompt
    else:
        parser.error("Provide a prompt or --prompt-file")
        return

    print(f"Baking demo fallback to {args.output_dir}")
    t0 = time.perf_counter()

    # Step 1: Generate story
    events = generate_story(args.api_base, prompt)
    scenes = extract_scenes(events)
    if not scenes:
        print("ERROR: No scenes generated. Is the backend running?")
        sys.exit(1)

    # Find model info from done event
    model_info = "unknown"
    for evt in events:
        if evt.get("type") == "done" and evt.get("model"):
            model_info = evt["model"]
            break

    # Step 2: Generate videos (unless skipped)
    videos: dict[int, str] = {}
    film_b64: str | None = None
    if not args.skip_video:
        videos = generate_videos(args.api_base, scenes)
        if videos:
            film_b64 = assemble_film(args.api_base, videos, len(scenes))
    else:
        print("  Skipping video generation (--skip-video)")

    # Step 3: Save everything
    save_assets(args.output_dir, prompt, scenes, videos, film_b64, model_info)

    elapsed = time.perf_counter() - t0
    print(f"\nDone in {elapsed:.1f}s. Fallback ready at {args.output_dir}")


if __name__ == "__main__":
    main()
