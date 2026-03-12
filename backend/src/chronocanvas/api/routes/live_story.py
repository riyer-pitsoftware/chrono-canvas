"""Live Story — interleaved text+image generation via Gemini.

Uses per-scene chat-based generation so each scene sees prior images in context,
ensuring character consistency across the storyboard.
"""

import base64
import json
import logging
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from google import genai
from google.genai import types
from pydantic import BaseModel

from chronocanvas.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/live-story", tags=["live-story"])

# Models to try in order — best consistency first
_MODEL_CHAIN = [
    "gemini-3.1-flash-image-preview",  # Nano Banana 2: up to 5 character refs
    "gemini-2.5-flash-image",          # fallback
]

DASH_SYSTEM_INSTRUCTION = """\
You are Dash, a noir creative director and cinematographer.

CHARACTER CONSISTENCY (CRITICAL):
Before telling the story, mentally cast your characters. Lock in each character's \
exact physical appearance — face shape, skin tone, hair color/style, eye color, \
build, age, distinguishing marks, and wardrobe. Once set, NEVER deviate. Every \
image must depict the SAME person with IDENTICAL features. Think of this as a \
real film with real actors — they don't change faces between shots.

OUTPUT FORMAT — SCENE BY SCENE:
You will generate ONE scene at a time. For each scene:
1. Write 2-4 sentences of noir prose (present tense).
2. Generate ONE photorealistic image for that scene.
When generating images, ALWAYS re-state each visible character's key physical \
features (face shape, hair, skin tone, build, clothing) in your internal image \
description — do NOT rely on context alone.

STORY PACING: You decide how many scenes the story needs — as many as the \
narrative requires for a complete, satisfying arc. When the story reaches its \
natural conclusion, end your final scene text with the exact marker: [END] \
on its own line.

Voice: clipped, direct, occasionally lyrical. Every word earns its place."""

# Injected into every prompt to force photorealistic image output
_PHOTO_STYLE_PREFIX = """\
IMAGE STYLE REQUIREMENT: Generate all images as photorealistic photographs. \
Shot on 35mm film, Canon EOS R5, 50mm f/1.4 lens. Shallow depth of field, \
natural film grain, practical lighting only. Real people, real places, real textures. \
The images must look like still frames from a real movie — NOT illustrations, \
NOT drawings, NOT comics, NOT cartoons, NOT digital art, NOT paintings. \
Photorealistic only.

CHARACTER CONSISTENCY REQUIREMENT: Every character must look like the SAME person \
across ALL images. Maintain identical facial features, bone structure, skin tone, \
hair color and style, eye color, body type, and wardrobe throughout. Repeat the \
character's key physical descriptors in every image you generate.

"""


class HistoryPart(BaseModel):
    """A previously generated part — text or image reference."""

    type: str  # "text" or "image"
    content: str  # text content or base64 image data
    mime_type: str | None = None


class LiveStoryRequest(BaseModel):
    prompt: str
    style: str | None = None
    era: str | None = None
    num_scenes: int = 4
    history: list[HistoryPart] | None = None  # prior turns for continuation
    original_prompt: str | None = None  # original prompt (for continuation)


def _build_prompt(req: LiveStoryRequest) -> str:
    parts = [_PHOTO_STYLE_PREFIX]
    if req.style:
        parts.append(f"Art style: {req.style}.")
    if req.era:
        parts.append(f"Historical era: {req.era}.")
    parts.append(f"\nStory prompt: {req.prompt}")
    return "\n".join(parts)


def _gen_config() -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=DASH_SYSTEM_INSTRUCTION,
        response_modalities=["TEXT", "IMAGE"],
        temperature=1.0,
        max_output_tokens=8192,
    )


def _extract_parts(response) -> list[dict]:
    """Extract text and image parts from a Gemini response."""
    results = []
    if not response.candidates or not response.candidates[0].content.parts:
        return results
    for part in response.candidates[0].content.parts:
        if part.text is not None:
            results.append({"type": "text", "content": part.text})
        elif part.inline_data is not None:
            b64 = base64.b64encode(part.inline_data.data).decode("ascii")
            results.append({
                "type": "image",
                "content": b64,
                "mime_type": part.inline_data.mime_type or "image/png",
            })
    return results


@router.post("")
async def live_story(req: LiveStoryRequest):
    """Stream interleaved text+image story as SSE events.

    Uses per-scene chat-based generation: each scene is a separate chat turn,
    so the model sees its own prior images and maintains character consistency.
    """
    if not settings.google_api_key:
        raise HTTPException(status_code=503, detail="GOOGLE_API_KEY not configured")

    client = genai.Client(api_key=settings.google_api_key)
    is_continuation = req.history is not None and len(req.history) > 0

    async def event_stream():
        start_time = time.perf_counter()
        model_used = None
        text_count = 0
        image_count = 0

        # Status: starting
        status_msg = (
            "Dash picks up the thread..."
            if is_continuation
            else "Dash is casting the characters..."
        )
        yield _sse({"type": "status", "content": status_msg})

        # Find a working model
        chat = None
        last_error = None
        for model in _MODEL_CHAIN:
            try:
                chat = client.aio.chats.create(
                    model=model, config=_gen_config()
                )
                model_used = model
                break
            except Exception as e:
                last_error = e
                logger.warning("Model %s failed to create chat: %s", model, e)
                continue

        if chat is None:
            yield _sse({"type": "error", "content": f"All models failed: {last_error}"})
            return

        if is_continuation:
            # Continuation: replay history into chat, then continue
            for part_data in await _continuation_flow(
                chat, req, model_used
            ):
                if part_data["type"] == "text":
                    text_count += 1
                elif part_data["type"] == "image":
                    image_count += 1
                yield _sse(part_data)
        else:
            # Fresh generation: per-scene chat loop
            for part_data in await _scene_by_scene_flow(
                chat, req, model_used
            ):
                if part_data["type"] == "text":
                    text_count += 1
                elif part_data["type"] == "image":
                    image_count += 1
                elif part_data["type"] in ("status", "error"):
                    pass  # don't count status/error as content
                yield _sse(part_data)

        elapsed = time.perf_counter() - start_time
        yield _sse({
            "type": "done",
            "model": model_used,
            "elapsed_s": round(elapsed, 1),
            "text_parts": text_count,
            "image_parts": image_count,
        })

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _scene_by_scene_flow(
    chat, req: LiveStoryRequest, model: str
) -> list[dict]:
    """Generate story scene-by-scene via chat turns.

    Turn 0 (hidden): Casting photo — character portraits for visual anchoring
    Turns 1..N: Model generates scenes until it signals [END]
    """
    all_parts = []
    base_prompt = _build_prompt(req)

    # Scene 0: Casting photo (hidden from viewer)
    # Generate character portraits to anchor visual consistency in chat history
    casting_prompt = (
        f"{base_prompt}\n\n"
        f"CASTING CALL: Before we begin filming, generate a casting photo. "
        f"Describe each main character's exact appearance in detail "
        f"(face shape, skin tone, hair color/style, eye color, build, age, "
        f"distinguishing marks, wardrobe). Then generate ONE image: a portrait "
        f"lineup of the main characters standing side by side, well-lit, "
        f"facing the camera. This is the reference photo for the entire film."
    )
    try:
        response = await chat.send_message(casting_prompt)
        casting_parts = _extract_parts(response)
        # Send casting text as a "casting" type so frontend can show it differently
        for cp in casting_parts:
            if cp["type"] == "text":
                all_parts.append({
                    "type": "casting",
                    "content": cp["content"],
                })
            elif cp["type"] == "image":
                all_parts.append({
                    "type": "casting_image",
                    "content": cp["content"],
                    "mime_type": cp.get("mime_type", "image/png"),
                })
        all_parts.append({
            "type": "status",
            "content": "Characters cast. Rolling camera...",
        })
    except Exception as e:
        logger.warning("Casting photo failed (continuing without): %s", e)
        all_parts.append({
            "type": "status",
            "content": "Dash is setting the scene...",
        })

    # Scenes — model decides how many; stops on [END] marker
    max_scenes = 20  # safety cap
    scene_idx = 0
    while scene_idx < max_scenes:
        if scene_idx == 0:
            prompt = (
                "Now begin the story. Write Scene 1 with text and one image. "
                "The characters must look EXACTLY like the casting photo above. "
                "Tell as many scenes as the story needs. When done, end with [END]."
            )
        else:
            prompt = (
                f"Continue with Scene {scene_idx + 1}. "
                f"Write the next scene with text and one image. "
                f"Same characters — same faces, same hair, same build as the casting photo. "
                f"If this is the final scene, end with a line that lingers and [END]."
            )

        try:
            response = await chat.send_message(prompt)
            parts = _extract_parts(response)
            if not parts:
                all_parts.append({
                    "type": "error",
                    "content": f"Scene {scene_idx + 1}: empty response",
                })
                break
            all_parts.extend(parts)
            all_parts.append({
                "type": "status",
                "content": f"Scene {scene_idx + 1} complete...",
            })

            # Check if model signaled story end
            text_content = " ".join(
                p["content"] for p in parts if p["type"] == "text"
            )
            if "[END]" in text_content:
                # Strip the marker from the last text part
                for p in reversed(all_parts):
                    if p.get("type") == "text" and "[END]" in p["content"]:
                        p["content"] = p["content"].replace("[END]", "").rstrip()
                        break
                break

        except Exception as e:
            logger.error("Scene %d generation failed: %s", scene_idx + 1, e)
            all_parts.append({
                "type": "error",
                "content": f"Scene {scene_idx + 1} failed: {e}",
            })
            break

        scene_idx += 1

    return all_parts


async def _continuation_flow(
    chat, req: LiveStoryRequest, model: str
) -> list[dict]:
    """Continue an existing story by replaying history through chat.

    Reconstructs the conversation: original prompt → history → continuation.
    Images from history are included so the model sees prior characters.
    """
    all_parts = []

    # Turn 1: replay the original prompt
    orig = LiveStoryRequest(
        prompt=req.original_prompt or req.prompt,
        style=req.style,
        era=req.era,
        num_scenes=req.num_scenes,
    )
    initial_prompt = _build_prompt(orig)

    try:
        # Send original prompt (we discard this response since we have history)
        await chat.send_message(initial_prompt)
    except Exception as e:
        logger.error("Failed to replay original prompt: %s", e)
        all_parts.append({"type": "error", "content": f"Replay failed: {e}"})
        return all_parts

    # Turn 2: feed history as "model" response then ask continuation
    # Since chat API doesn't let us inject model turns, we send the history
    # as a user message with context, then ask for continuation
    history_text_parts = []
    history_image_parts = []
    for hp in req.history or []:
        if hp.type == "text":
            history_text_parts.append(hp.content)
        elif hp.type == "image" and hp.content:
            history_image_parts.append(hp)

    # Build continuation message with reference images from history
    continuation_parts = []

    # Include the last 2 images as visual reference (cap to avoid context overflow)
    for img_hp in history_image_parts[-2:]:
        image_bytes = base64.b64decode(img_hp.content)
        continuation_parts.append(
            types.Part.from_bytes(
                data=image_bytes, mime_type=img_hp.mime_type or "image/png"
            )
        )

    continuation_text = (
        f"Here is the story so far:\n\n"
        f"{''.join(history_text_parts[-3:])}\n\n"
        f"The audience says: {req.prompt}\n"
        f"Continue with 2-3 more scenes. Same characters — same faces, "
        f"same hair, same build, same clothing. Generate text and images."
    )
    continuation_parts.append(types.Part.from_text(text=continuation_text))

    try:
        response = await chat.send_message(continuation_parts)
        parts = _extract_parts(response)
        all_parts.extend(parts)
    except Exception as e:
        logger.error("Continuation generation failed: %s", e)
        all_parts.append({"type": "error", "content": f"Continuation failed: {e}"})

    return all_parts


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"
