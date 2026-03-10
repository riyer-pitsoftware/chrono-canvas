"""Scene editor — Gemini vision sees current image + edit instruction.

Revised prompt leads to Imagen regen.
"""

import json
import logging
import time
from pathlib import Path

from google import genai
from google.genai import types

from chronocanvas.config import settings
from chronocanvas.imaging.imagen_client import ImagenGenerator
from chronocanvas.llm.providers.gemini import GEMINI_PRICING, gemini_generate_with_timeout
from chronocanvas.services.progress import ProgressPublisher

logger = logging.getLogger(__name__)

SCENE_EDIT_PROMPT = """\
You are a visual storyboard editor. The user wants to modify a scene image.

Look at the CURRENT image and the user's EDIT INSTRUCTION, then generate a revised \
image generation prompt that incorporates the requested change while preserving \
everything else about the scene.

EDIT INSTRUCTION: {instruction}

ORIGINAL SCENE DESCRIPTION: {description}

Write a complete, detailed image prompt that an image generator can use. \
Keep all the good elements from the original, but apply the requested change.

Output ONLY valid JSON:
{{
  "revised_prompt": "the complete revised image generation prompt...",
  "negative_prompt": "low quality, blurry, deformed, cartoon",
  "change_summary": "brief description of what was changed"
}}"""


async def edit_scene(
    request_id: str,
    scene_index: int,
    instruction: str,
    current_image_path: str,
    current_description: str,
) -> dict:
    """Edit a single scene: Gemini vision + Imagen regeneration.

    Returns dict with revised image info and LLM call records.
    """
    publisher = ProgressPublisher()
    channel = f"generation:{request_id}"
    llm_calls = []

    # Step 1: Gemini multimodal — see current image + edit instruction → revised prompt
    client = genai.Client(api_key=settings.google_api_key)
    model = settings.gemini_model

    parts: list[types.Part] = [
        types.Part.from_text(
            text=SCENE_EDIT_PROMPT.format(
                instruction=instruction,
                description=current_description,
            )
        ),
    ]

    if current_image_path and Path(current_image_path).exists():
        image_bytes = Path(current_image_path).read_bytes()
        parts.append(types.Part.from_bytes(data=image_bytes, mime_type="image/png"))

    start = time.perf_counter()
    response = await gemini_generate_with_timeout(
        client,
        model=model,
        contents=types.Content(role="user", parts=parts),
        config=types.GenerateContentConfig(
            temperature=0.5,
            max_output_tokens=1500,
            response_mime_type="application/json",
        ),
    )
    elapsed_ms = (time.perf_counter() - start) * 1000

    input_tokens = response.usage_metadata.prompt_token_count or 0
    output_tokens = response.usage_metadata.candidates_token_count or 0
    pricing = GEMINI_PRICING.get(model, {"input": 0, "output": 0})
    cost = input_tokens * pricing["input"] + output_tokens * pricing["output"]

    raw_text = response.text or "{}"
    json_start = raw_text.find("{")
    json_end = raw_text.rfind("}") + 1
    parsed = json.loads(raw_text[json_start:json_end]) if json_start >= 0 else {}

    revised_prompt = parsed.get("revised_prompt", "")
    change_summary = parsed.get("change_summary", "")

    llm_calls.append(
        {
            "agent": "scene_editor",
            "timestamp": time.time(),
            "provider": "gemini",
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost,
            "duration_ms": elapsed_ms,
        }
    )

    if not revised_prompt:
        raise ValueError("Gemini returned no revised prompt")

    # Step 2: Imagen regeneration
    imagen = ImagenGenerator()
    scene_dir = Path(settings.output_dir) / request_id / f"scene_{scene_index}"
    scene_dir.mkdir(parents=True, exist_ok=True)

    img_start = time.perf_counter()
    img_result = await imagen.generate(
        prompt=revised_prompt,
        output_dir=scene_dir,
        width=768,
        height=768,
    )
    img_elapsed = (time.perf_counter() - img_start) * 1000

    # Rename to edited_ prefix for clarity
    original_path = Path(img_result.file_path)
    edited_filename = f"edited_{int(time.time())}.png"
    edited_path = scene_dir / edited_filename
    original_path.rename(edited_path)

    # Publish artifact
    image_url = f"/output/{request_id}/scene_{scene_index}/{edited_filename}"
    await publisher.publish_artifact(
        channel,
        artifact_type="scene_edit",
        scene_index=scene_index,
        total=1,
        completed=1,
        url=image_url,
        mime_type="image/png",
    )

    logger.info(
        "Scene edit complete: scene %d, '%s' [request_id=%s]",
        scene_index,
        change_summary,
        request_id,
    )

    return {
        "scene_index": scene_index,
        "edited_image_path": str(edited_path),
        "edited_image_url": image_url,
        "revised_prompt": revised_prompt,
        "change_summary": change_summary,
        "llm_calls": llm_calls,
        "image_generation_ms": img_elapsed,
    }
