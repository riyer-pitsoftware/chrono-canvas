#!/usr/bin/env python3
"""Minimal FaceFusion REST API wrapper for ChronoCanvas.

Exposes:
  GET  /api/health
  POST /api/process  {"source_image": "<path>", "target_image": "<path>"}
  → Returns raw PNG image bytes.

FaceFusion uses global shared state, so requests are serialised behind a
single asyncio lock. This is fine for a local dev environment.
"""

import asyncio
import logging
import os
import sys
import time
import uuid
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel

# ── Path setup ─────────────────────────────────────────────────────────────────
sys.path.insert(0, "/facefusion")
os.chdir("/facefusion")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


# ── Initialise FaceFusion state once at startup ────────────────────────────────

def _bootstrap_state() -> None:
    from facefusion import state_manager
    from facefusion.choices import face_mask_areas, face_mask_regions

    defaults: dict = {
        # paths
        "temp_path": "/tmp/ff_temp",
        "jobs_path": "/tmp/ff_jobs",
        "source_paths": None,
        "target_path": None,
        "output_path": None,
        # processors
        "processors": ["face_swapper"],
        # face detector
        "face_detector_model": "yolo_face",
        "face_detector_size": "640x640",
        "face_detector_margin": [0, 0, 0, 0],
        "face_detector_angles": [0],
        "face_detector_score": 0.5,
        # face landmarker
        "face_landmarker_model": "2dfan4",
        "face_landmarker_score": 0.5,
        # face selector
        "face_selector_mode": "many",
        "face_selector_order": "large-small",
        "face_selector_age_start": None,
        "face_selector_age_end": None,
        "face_selector_gender": None,
        "face_selector_race": None,
        "reference_face_position": 0,
        "reference_face_distance": 0.3,
        "reference_frame_number": 0,
        # face masker
        "face_occluder_model": "xseg_1",
        "face_parser_model": "bisenet_resnet_34",
        "face_mask_types": ["box"],
        "face_mask_areas": list(face_mask_areas),
        "face_mask_regions": list(face_mask_regions),
        "face_mask_blur": 0.3,
        "face_mask_padding": [0, 0, 0, 0],
        # face swapper
        "face_swapper_model": "inswapper_128",
        "face_swapper_pixel_boost": "512x512",
        "face_swapper_weight": 1.0,
        # output creation
        "output_image_quality": 80,
        "output_image_scale": 1.0,
        "output_audio_encoder": "aac",
        "output_audio_quality": 80,
        "output_audio_volume": 100,
        "output_video_encoder": "libx264",
        "output_video_preset": "veryfast",
        # frame extraction
        "temp_frame_format": "png",
        "keep_temp": False,
        "trim_frame_start": None,
        "trim_frame_end": None,
        # execution
        "execution_providers": ["cpu"],
        "execution_thread_count": 4,
        "execution_queue_count": 1,
        "video_memory_strategy": "tolerant",
        "system_memory_limit": 0,
        # misc
        "log_level": "info",
        "command": None,
        "config_path": "facefusion.ini",
        "download_scope": "lite",
        "skip_download": False,
    }

    for key, value in defaults.items():
        state_manager.init_item(key, value)

    logger.info("FaceFusion state bootstrapped")


_bootstrap_state()

# ── FastAPI app ────────────────────────────────────────────────────────────────

app = FastAPI(title="FaceFusion API", version="1.0.0")

# Serialise requests — FaceFusion uses module-level global state
_lock = asyncio.Lock()


class ProcessRequest(BaseModel):
    source_image: str
    target_image: str


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "facefusion"}


@app.post("/api/process")
async def process_images(req: ProcessRequest):
    src = Path(req.source_image)
    tgt = Path(req.target_image)

    if not src.exists():
        raise HTTPException(status_code=400, detail=f"Source image not found: {req.source_image}")
    if not tgt.exists():
        raise HTTPException(status_code=400, detail=f"Target image not found: {req.target_image}")

    output_path = f"/tmp/ff_output_{uuid.uuid4().hex}.png"

    async with _lock:
        try:
            loop = asyncio.get_event_loop()
            error_code = await loop.run_in_executor(
                None, _do_swap, req.source_image, req.target_image, output_path
            )
        except Exception as exc:
            logger.exception("FaceFusion swap error")
            raise HTTPException(status_code=500, detail=str(exc))

    if error_code != 0:
        raise HTTPException(status_code=500, detail=f"FaceFusion returned error code {error_code}")

    out_file = Path(output_path)
    if not out_file.exists():
        raise HTTPException(status_code=500, detail="Output file was not created")

    data = out_file.read_bytes()
    out_file.unlink(missing_ok=True)
    return Response(content=data, media_type="image/png")


def _do_swap(source_image: str, target_image: str, output_path: str) -> int:
    """Run FaceFusion image-to-image workflow synchronously."""
    from facefusion import state_manager
    from facefusion.workflows import image_to_image

    state_manager.init_item("source_paths", [source_image])
    state_manager.init_item("target_path", target_image)
    state_manager.init_item("output_path", output_path)

    return image_to_image.process(time.time())


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7861, log_level="info")
