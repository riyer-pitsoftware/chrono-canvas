"""Live Story — interleaved text+image generation via Gemini.

Uses per-scene chat-based generation so each scene sees prior images in context,
ensuring character consistency across the storyboard.
"""

import asyncio
import base64
import json
import logging
import time
from collections.abc import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from google import genai
from google.genai import types
from pydantic import BaseModel

from chronocanvas.config import settings

try:
    from PIL import Image as _PILImage
except ImportError:
    _PILImage = None

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/live-story", tags=["live-story"])

# Models to try in order — best consistency first
_MODEL_CHAIN = [
    "gemini-3.1-flash-image-preview",  # Nano Banana 2: up to 5 character refs
    "gemini-2.5-flash-image",  # fallback
]

# Fast text-only model for parallel fallback (no image capability needed)
_TEXT_ONLY_MODEL = "gemini-2.5-flash"

# Timeout per Gemini chat turn (seconds) — casting and scenes
_TURN_TIMEOUT_S = 120

# Keepalive interval (seconds) — SSE comment sent while waiting for Gemini
_KEEPALIVE_INTERVAL_S = 15
_KEEPALIVE_EVENT = {"type": "keepalive"}

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


def _gen_config(*, thinking: bool = False) -> types.GenerateContentConfig:
    """Build generation config.

    When *thinking* is True, adds ``thinking_level=MINIMAL`` for Gemini 3.x
    models.  Thinking is only safe on fresh chats — multi-turn
    ``thought_signature`` corruption is handled by fallback logic in the
    scene loop.
    """
    cfg_kwargs: dict = dict(
        system_instruction=DASH_SYSTEM_INSTRUCTION,
        response_modalities=["TEXT", "IMAGE"],
        temperature=1.0,
        max_output_tokens=8192,
    )
    if thinking:
        cfg_kwargs["thinking_config"] = types.ThinkingConfig(thinking_level="MINIMAL")
    return types.GenerateContentConfig(**cfg_kwargs)


def _casting_config() -> types.GenerateContentConfig:
    """Config for one-shot casting call — no thinking, no chat needed."""
    return types.GenerateContentConfig(
        system_instruction=DASH_SYSTEM_INSTRUCTION,
        response_modalities=["TEXT", "IMAGE"],
        temperature=1.0,
        max_output_tokens=8192,
    )


def _is_thought_signature_error(exc: Exception) -> bool:
    """Return True if the exception is a Gemini thought_signature 400 error."""
    msg = str(exc).lower()
    return "thought_signature" in msg or ("400" in msg and ("invalid" in msg or "thought" in msg))


_RESULT = object()  # sentinel for _call_with_keepalives

# How long to wait between stream chunks before assuming text is "done" and
# yielding accumulated text early (while image is still generating).
_TEXT_FLUSH_TIMEOUT_S = 3.0


async def _call_with_keepalives(
    coro,
    timeout_s: float = _TURN_TIMEOUT_S,
    interval_s: float = _KEEPALIVE_INTERVAL_S,
) -> AsyncGenerator:
    """Async generator that yields keepalive events while awaiting a coroutine.

    Yields ``_KEEPALIVE_EVENT`` dicts every *interval_s* seconds while *coro*
    is running.  The final yield is the tuple ``(_RESULT, response)``.
    Raises ``asyncio.TimeoutError`` if the coroutine exceeds *timeout_s*.
    """
    task = asyncio.ensure_future(coro)
    deadline = asyncio.get_event_loop().time() + timeout_s
    try:
        while not task.done():
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                task.cancel()
                raise asyncio.TimeoutError()
            try:
                await asyncio.wait_for(
                    asyncio.shield(task),
                    timeout=min(interval_s, remaining),
                )
            except asyncio.TimeoutError:
                if task.done():
                    break
                yield _KEEPALIVE_EVENT
        # Propagate any exception from the task
        yield (_RESULT, task.result())
    except asyncio.CancelledError:
        task.cancel()
        raise


async def _stream_scene_parts(
    client,
    model: str,
    config,
    contents,
    *,
    timeout_s: float = _TURN_TIMEOUT_S,
    flush_timeout_s: float = _TEXT_FLUSH_TIMEOUT_S,
    keepalive_s: float = _KEEPALIVE_INTERVAL_S,
) -> AsyncGenerator[dict, None]:
    """Stream scene text+image from one-shot ``generate_content_stream()``.

    Uses one-shot calls instead of chat.send_message_stream() because
    Gemini 3.x image models only reliably generate images in one-shot mode,
    not in multi-turn chat mode.

    *contents* is the full conversation history (list of Content objects).
    """
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout_s

    stream = await asyncio.wait_for(
        client.aio.models.generate_content_stream(
            model=model,
            contents=contents,
            config=config,
        ),
        timeout=min(30, timeout_s),
    )
    stream_iter = stream.__aiter__()

    accumulated_text: list[str] = []
    text_yielded = False
    text_early = False  # True if text was flushed before first image arrived
    got_any_content = False

    while True:
        remaining = deadline - loop.time()
        if remaining <= 0:
            raise asyncio.TimeoutError()

        # Choose how long to wait for the next chunk:
        # - If we have un-yielded text, use a short timeout so we flush quickly.
        # - Otherwise, use the keepalive interval.
        wait = flush_timeout_s if (accumulated_text and not text_yielded) else keepalive_s
        wait = min(wait, remaining)

        try:
            chunk = await asyncio.wait_for(stream_iter.__anext__(), timeout=wait)
        except StopAsyncIteration:
            break
        except asyncio.TimeoutError:
            # Timed out waiting for next chunk.
            if loop.time() >= deadline:
                raise asyncio.TimeoutError()
            # Flush accumulated text if we've been waiting long enough.
            if accumulated_text and not text_yielded:
                full_text = "".join(accumulated_text)
                clean = full_text.replace("[END]", "").rstrip()
                if clean:
                    yield {"type": "text", "content": clean}
                text_yielded = True
                text_early = True  # text flushed before image — streaming works
            else:
                yield _KEEPALIVE_EVENT
            continue

        # Process chunk parts
        if (
            not chunk.candidates
            or not chunk.candidates[0].content
            or not chunk.candidates[0].content.parts
        ):
            continue

        # Log finish reason for diagnostics
        if chunk.candidates and chunk.candidates[0].finish_reason:
            logger.info(
                "Scene chunk finish_reason=%s",
                chunk.candidates[0].finish_reason,
            )

        for part in chunk.candidates[0].content.parts:
            part_type = (
                "thought"
                if getattr(part, "thought", False)
                else "text"
                if part.text is not None
                else "image"
                if part.inline_data is not None
                else "other"
            )
            logger.debug(
                "Scene part: type=%s len=%s",
                part_type,
                len(part.text)
                if part.text
                else (
                    len(part.inline_data.data)
                    if part.inline_data and part.inline_data.data
                    else "?"
                ),
            )
            if getattr(part, "thought", False):
                continue
            if part.text is not None:
                accumulated_text.append(part.text)
                got_any_content = True
            elif part.inline_data is not None:
                got_any_content = True
                logger.info(
                    "Scene image received: %d bytes, mime=%s",
                    len(part.inline_data.data) if part.inline_data.data else 0,
                    part.inline_data.mime_type,
                )
                # Flush any pending text before the image
                if accumulated_text and not text_yielded:
                    full_text = "".join(accumulated_text)
                    clean = full_text.replace("[END]", "").rstrip()
                    if clean:
                        yield {"type": "text", "content": clean}
                    text_yielded = True
                compressed, mime = _compress_image(
                    part.inline_data.data,
                    part.inline_data.mime_type or "image/png",
                )
                b64 = base64.b64encode(compressed).decode("ascii")
                yield {
                    "type": "image",
                    "content": b64,
                    "mime_type": mime,
                }

    # Flush any remaining text (e.g. text-only scene with no image)
    if accumulated_text and not text_yielded:
        full_text = "".join(accumulated_text)
        clean = full_text.replace("[END]", "").rstrip()
        if clean:
            yield {"type": "text", "content": clean}
            logger.warning("Scene had text but NO image (text-only fallback)")
        text_yielded = True

    # Determine whether the model signalled end-of-story
    raw_text = "".join(accumulated_text)
    is_final = "[END]" in raw_text

    # Yield metadata so the caller knows if the story ended and if content was empty
    yield {
        "type": "_meta",
        "is_final": is_final,
        "empty": not got_any_content,
        "text_early": text_early,
    }


async def _parallel_scene_parts(
    chat,
    prompt: str,
    client,
    *,
    timeout_s: float = _TURN_TIMEOUT_S,
    keepalive_s: float = _KEEPALIVE_INTERVAL_S,
) -> AsyncGenerator[dict, None]:
    """Generate text and image in parallel for faster perceived response.

    When streaming doesn't separate text from image (both arrive together after
    ~2min), this fallback runs two concurrent tasks:
      - Text task: fast text-only model (~3s) for immediate narration
      - Image task: main chat (for character consistency) for the scene image

    Text is yielded first so the frontend can start typewriter + narration
    while the image is still generating.
    """
    # Text-only prompt — strip image generation instructions
    text_prompt = (
        f"Write ONLY the prose text for this scene. No image. "
        f"2-4 sentences of noir prose, present tense.\n\n{prompt}"
    )

    text_config = types.GenerateContentConfig(
        system_instruction=DASH_SYSTEM_INSTRUCTION,
        response_modalities=["TEXT"],
        temperature=1.0,
        max_output_tokens=2048,
    )

    async def _get_text():
        text_chat = client.aio.chats.create(model=_TEXT_ONLY_MODEL, config=text_config)
        return await asyncio.wait_for(
            text_chat.send_message(text_prompt),
            timeout=30,  # text should be fast
        )

    async def _get_image():
        return await asyncio.wait_for(
            chat.send_message(prompt),
            timeout=timeout_s,
        )

    text_task = asyncio.create_task(_get_text())
    image_task = asyncio.create_task(_get_image())

    # Wait for text first (should be ~3s)
    text_succeeded = False
    try:
        text_response = await text_task
        text_parts = _extract_parts(text_response)
        text_content = " ".join(p["content"] for p in text_parts if p["type"] == "text")
        if text_content:
            clean = text_content.replace("[END]", "").rstrip()
            if clean:
                yield {"type": "text", "content": clean}
                text_succeeded = True
    except Exception as e:
        logger.warning("Parallel text generation failed: %s", e)
        # Fall through — image task response will have text too

    # Wait for image (longer), with keepalives
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout_s
    while not image_task.done():
        remaining = deadline - loop.time()
        if remaining <= 0:
            image_task.cancel()
            raise asyncio.TimeoutError()
        try:
            await asyncio.wait_for(
                asyncio.shield(image_task),
                timeout=min(keepalive_s, remaining),
            )
        except asyncio.TimeoutError:
            if not image_task.done():
                yield _KEEPALIVE_EVENT

    image_response = image_task.result()

    parts = _extract_parts(image_response)

    # Yield image; if parallel text failed, also yield text from image model
    text_from_image = []
    for p in parts:
        if p["type"] == "image":
            yield p
        elif p["type"] == "text":
            text_from_image.append(p["content"])

    # If text task failed, fall back to text from image model
    if not text_succeeded and text_from_image:
        full_text = " ".join(text_from_image)
        clean = full_text.replace("[END]", "").rstrip()
        if clean:
            yield {"type": "text", "content": clean}

    # Check [END] from the authoritative image model response
    full_text = " ".join(text_from_image)
    is_final = "[END]" in full_text

    yield {
        "type": "_meta",
        "is_final": is_final,
        "empty": not parts,
        "text_early": True,  # parallel mode always delivers text early
    }


def _compress_image(
    raw_bytes: bytes,
    mime_type: str = "image/png",
    *,
    max_width: int = 1280,
    jpeg_quality: int = 85,
) -> tuple[bytes, str]:
    """Compress an image to JPEG, capping width at *max_width* px.

    Returns ``(compressed_bytes, mime_type)``.  Falls back to the original
    bytes if Pillow is unavailable or an error occurs.
    """
    if _PILImage is None:
        return raw_bytes, mime_type
    try:
        import io

        img = _PILImage.open(io.BytesIO(raw_bytes))

        # Cap width while preserving aspect ratio
        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), _PILImage.LANCZOS)

        # JPEG doesn't support alpha
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=jpeg_quality, optimize=True)
        compressed = buf.getvalue()

        logger.debug(
            "Image compressed: %d -> %d bytes (%.0f%% reduction)",
            len(raw_bytes),
            len(compressed),
            (1 - len(compressed) / len(raw_bytes)) * 100,
        )
        return compressed, "image/jpeg"
    except Exception:
        logger.warning("Image compression failed, sending original", exc_info=True)
        return raw_bytes, mime_type


def _extract_parts(response) -> list[dict]:
    """Extract text and image parts from a Gemini response."""
    results = []
    if (
        not response.candidates
        or not response.candidates[0].content
        or not response.candidates[0].content.parts
    ):
        return results
    for part in response.candidates[0].content.parts:
        if getattr(part, "thought", False):
            continue
        if part.text is not None:
            results.append({"type": "text", "content": part.text})
        elif part.inline_data is not None:
            compressed, mime = _compress_image(
                part.inline_data.data, part.inline_data.mime_type or "image/png"
            )
            b64 = base64.b64encode(compressed).decode("ascii")
            results.append(
                {
                    "type": "image",
                    "content": b64,
                    "mime_type": mime,
                }
            )
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

        # Stage: init
        yield _sse(_stage_event("init", "start"))
        init_t0 = time.perf_counter()

        # Find a working model — probe with a chat create to validate access
        chat = None
        last_error = None
        for model in _MODEL_CHAIN:
            try:
                chat = client.aio.chats.create(model=model, config=_gen_config())
                model_used = model
                break
            except Exception as e:
                last_error = e
                logger.warning("Model %s failed to create chat: %s", model, e)
                continue

        if chat is None:
            yield _sse(
                _stage_event(
                    "init",
                    "error",
                    elapsed_s=time.perf_counter() - init_t0,
                    detail=f"All models failed: {last_error}",
                )
            )
            yield _sse({"type": "error", "content": f"All models failed: {last_error}"})
            return

        yield _sse(
            _stage_event(
                "init",
                "complete",
                elapsed_s=time.perf_counter() - init_t0,
                detail=model_used,
            )
        )

        if is_continuation:
            flow = _continuation_flow(chat, req, model_used)
        else:
            # cn-krhe: scene flow creates its own fresh chat internally
            flow = _scene_by_scene_flow(chat, req, model_used, client=client)

        async for part_data in flow:
            if part_data.get("type") == "keepalive":
                yield ": keepalive\n\n"
                continue
            if part_data["type"] == "text":
                text_count += 1
            elif part_data["type"] == "image":
                image_count += 1
            yield _sse(part_data)

        elapsed = time.perf_counter() - start_time
        yield _sse(
            {
                "type": "done",
                "model": model_used,
                "elapsed_s": round(elapsed, 1),
                "text_parts": text_count,
                "image_parts": image_count,
            }
        )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _scene_by_scene_flow(
    chat, req: LiveStoryRequest, model: str, *, client=None
) -> AsyncGenerator[dict, None]:
    """Generate story scene-by-scene, yielding each part immediately.

    Architecture (cn-krhe fix):
      1. Casting: ONE-SHOT ``generate_content`` — no chat, no thinking.
         Portraits don't need reasoning and this avoids thought_signature
         corruption entirely.
      2. Scene chat: FRESH chat with ``thinking_level=MINIMAL``.  The
         casting image is injected as user context in the first turn so
         the model sees it without inheriting a polluted history.
      3. Fallback: if any scene turn hits a thought_signature 400 error,
         recreate the chat WITHOUT thinking and retry the failed turn.
    """
    if client is None:
        client = genai.Client(api_key=settings.google_api_key)

    base_prompt = _build_prompt(req)

    # ── Casting (Scene 0) — one-shot, no chat, no thinking ─────
    yield _stage_event("casting", "start")

    casting_prompt = (
        f"{base_prompt}\n\n"
        f"CASTING CALL ONLY — DO NOT START THE STORY.\n"
        f"Describe each main character's exact appearance in detail "
        f"(face shape, skin tone, hair color/style, eye color, build, age, "
        f"distinguishing marks, wardrobe). Then generate ONE image: a portrait "
        f"lineup of the main characters standing side by side, well-lit, "
        f"facing the camera. This is the reference photo for the entire film.\n\n"
        f"STOP after the casting photo. Do NOT write any story scenes or narration. "
        f"Do NOT include [END]. Just the character descriptions and one portrait image."
    )
    casting_parts = []
    casting_image_bytes: bytes | None = None  # raw bytes for chat injection
    casting_image_mime: str = "image/png"
    casting_text: str = ""  # character descriptions for scene chat context
    casting_t0 = time.perf_counter()
    try:
        # Stream casting — stop after first image to prevent the model
        # from generating the entire story during what should be a
        # portrait-only call.  Text chunks are accumulated; the first
        # image terminates consumption.
        accumulated_text: list[str] = []
        stream = await asyncio.wait_for(
            client.aio.models.generate_content_stream(
                model=model,
                contents=casting_prompt,
                config=_casting_config(),
            ),
            timeout=30,
        )
        loop = asyncio.get_event_loop()
        deadline = loop.time() + _TURN_TIMEOUT_S
        last_keepalive = loop.time()
        got_image = False
        image_seen_time: float | None = None
        # After image arrives, keep reading text for up to 5s
        _post_image_text_window_s = 5.0

        async for chunk in stream:
            # Keepalive while waiting
            now = loop.time()
            if now >= deadline:
                raise asyncio.TimeoutError()
            if now - last_keepalive >= _KEEPALIVE_INTERVAL_S:
                yield _KEEPALIVE_EVENT
                last_keepalive = now

            if (
                not chunk.candidates
                or not chunk.candidates[0].content
                or not chunk.candidates[0].content.parts
            ):
                continue

            for part in chunk.candidates[0].content.parts:
                if getattr(part, "thought", False):
                    continue
                if part.text is not None:
                    accumulated_text.append(part.text)
                elif part.inline_data is not None and not got_image:
                    # First image = casting portrait — stash raw bytes
                    casting_image_bytes = part.inline_data.data
                    casting_image_mime = part.inline_data.mime_type or "image/png"
                    compressed, mime = _compress_image(
                        casting_image_bytes,
                        casting_image_mime,
                    )
                    b64 = base64.b64encode(compressed).decode("ascii")
                    casting_parts.append(
                        {
                            "type": "image",
                            "content": b64,
                            "mime_type": mime,
                        }
                    )
                    got_image = True
                    image_seen_time = loop.time()

            # After image, keep collecting text briefly then stop —
            # don't let the model generate full story scenes.
            if got_image and (loop.time() - image_seen_time) >= _post_image_text_window_s:
                break

        # Assemble text part
        if accumulated_text:
            full_text = "".join(accumulated_text)
            clean = full_text.replace("[END]", "").rstrip()
            if clean:
                casting_parts.insert(0, {"type": "text", "content": clean})
                casting_text = clean  # stash for scene chat context
    except asyncio.TimeoutError:
        elapsed = time.perf_counter() - casting_t0
        logger.warning("Casting photo timed out after %.1fs", elapsed)
        yield _stage_event(
            "casting",
            "timeout",
            elapsed_s=elapsed,
            detail=f"Timed out after {_TURN_TIMEOUT_S}s",
        )
    except Exception as e:
        elapsed = time.perf_counter() - casting_t0
        logger.warning("Casting photo failed (continuing without): %s", e)
        yield _stage_event(
            "casting",
            "error",
            elapsed_s=elapsed,
            detail=str(e),
        )

    # ── Check if casting accidentally generated the full story ──
    casting_has_end = any("[END]" in cp["content"] for cp in casting_parts if cp["type"] == "text")

    if casting_has_end:
        logger.info(
            "Model generated complete story during casting (%d parts, "
            "[END] detected) — emitting first part as casting, rest as scenes",
            len(casting_parts),
        )
        # Emit first text + first image as casting data so the
        # CastingInterstitial has something to display.
        first_text_emitted = False
        first_image_emitted = False
        scene_parts = []
        for cp in casting_parts:
            if cp["type"] == "text" and not first_text_emitted:
                # First text block = character descriptions (casting)
                clean = cp["content"].replace("[END]", "").rstrip()
                if clean:
                    yield {"type": "casting", "content": clean}
                first_text_emitted = True
            elif cp["type"] == "image" and not first_image_emitted:
                yield {
                    "type": "casting_image",
                    "content": cp["content"],
                    "mime_type": cp.get("mime_type", "image/png"),
                }
                first_image_emitted = True
            else:
                scene_parts.append(cp)

        yield _stage_event(
            "casting",
            "complete",
            elapsed_s=time.perf_counter() - casting_t0,
        )

        # Remaining parts are story scenes
        scene_num = 0
        for cp in scene_parts:
            if cp["type"] == "text":
                scene_num += 1
                clean = cp["content"].replace("[END]", "").rstrip()
                if clean:
                    yield _stage_event("scene", "start", scene_idx=scene_num)
                    yield {"type": "text", "content": clean}
                    yield _stage_event(
                        "scene",
                        "complete",
                        scene_idx=scene_num,
                        elapsed_s=0.0,
                    )
            elif cp["type"] == "image":
                yield {
                    "type": "image",
                    "content": cp["content"],
                    "mime_type": cp.get("mime_type", "image/png"),
                }
        return

    # Normal path — emit as casting data for the interstitial title card
    for cp in casting_parts:
        if cp["type"] == "text":
            yield {"type": "casting", "content": cp["content"]}
        elif cp["type"] == "image":
            yield {
                "type": "casting_image",
                "content": cp["content"],
                "mime_type": cp.get("mime_type", "image/png"),
            }
    yield _stage_event(
        "casting",
        "complete",
        elapsed_s=time.perf_counter() - casting_t0,
    )

    # ── Parallel scene generation — text + image in parallel ────
    # Gemini 3.x image models intermittently skip images when asked
    # for both text+image.  Fix: dedicated text call (fast model) +
    # dedicated image call (image model, image-only prompt).
    logger.info(
        "Scene generation: text_model=%s image_model=%s mode=parallel",
        _TEXT_ONLY_MODEL,
        model,
    )

    # Conversation history for text continuity (text-only model)
    text_history: list[types.Content] = []
    _image_timeout_s = 90  # image generation can be slow

    # ── Scenes ────────────────────────────────────────────────────
    max_scenes = 4  # cap for demo pacing
    scene_idx = 0
    while scene_idx < max_scenes:
        yield _stage_event("scene", "start", scene_idx=scene_idx + 1)
        scene_t0 = time.perf_counter()

        # ── Build text prompt ─────────────────────────────────────
        if scene_idx == 0:
            casting_context = ""
            if casting_text:
                casting_context = f"CHARACTER REFERENCE:\n{casting_text}\n\n"
            text_prompt = (
                f"{casting_context}{base_prompt}\n\n"
                f"Write ONLY Scene 1 — 2-4 sentences of noir prose, present tense. "
                f"Do NOT write multiple scenes."
            )
        else:
            is_last = scene_idx == max_scenes - 1
            text_prompt = (
                f"Continue with ONLY Scene {scene_idx + 1} — 2-4 sentences of noir "
                f"prose, present tense. Do NOT write multiple scenes."
            )
            if is_last:
                text_prompt += " This is the FINAL scene — wrap up the story and end with [END]."
            else:
                text_prompt += " If the story reaches a natural conclusion, end with [END]."

        logger.info(
            "Scene %d: %d text history turns, is_last=%s",
            scene_idx + 1,
            len(text_history),
            scene_idx == max_scenes - 1,
        )

        # ── Text generation (fast, ~2-3s) ─────────────────────────
        text_config = types.GenerateContentConfig(
            system_instruction=DASH_SYSTEM_INSTRUCTION,
            response_modalities=["TEXT"],
            temperature=1.0,
            max_output_tokens=2048,
        )
        user_turn = types.Content(
            role="user",
            parts=[types.Part.from_text(text=text_prompt)],
        )
        text_contents = text_history + [user_turn]

        try:
            text_response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=_TEXT_ONLY_MODEL,
                    contents=text_contents,
                    config=text_config,
                ),
                timeout=30,
            )
            scene_text = (text_response.text or "").replace("[END]", "").rstrip()
            is_final = "[END]" in (text_response.text or "")

            if not scene_text:
                yield _stage_event(
                    "scene",
                    "error",
                    scene_idx=scene_idx + 1,
                    elapsed_s=time.perf_counter() - scene_t0,
                    detail="Empty text from model",
                )
                yield {"type": "error", "content": f"Scene {scene_idx + 1}: empty text"}
                break

            # Yield text immediately
            yield {"type": "text", "content": scene_text}

            # Update text history
            text_history.append(user_turn)
            text_history.append(
                types.Content(
                    role="model",
                    parts=[types.Part.from_text(text=scene_text)],
                )
            )

        except Exception as e:
            elapsed = time.perf_counter() - scene_t0
            logger.error("Scene %d text failed: %s", scene_idx + 1, e)
            yield _stage_event(
                "scene",
                "error",
                scene_idx=scene_idx + 1,
                elapsed_s=elapsed,
                detail=str(e),
            )
            yield {"type": "error", "content": f"Scene {scene_idx + 1} text failed: {e}"}
            break

        # ── Image generation (parallel, ~10-30s) ─────────────────
        # Fire-and-forget style: yield keepalives while waiting.
        image_prompt = (
            f"Generate ONE photorealistic cinematic image for this noir scene:\n\n{scene_text}\n\n"
        )
        if casting_text:
            image_prompt += f"Character appearances:\n{casting_text}\n\n"
        image_prompt += (
            "Dramatic lighting, cinematic composition, film noir aesthetic. "
            "Photorealistic. No text overlays."
        )

        image_config = types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            temperature=1.0,
            max_output_tokens=8192,
        )

        loop = asyncio.get_event_loop()

        async def _gen_image():
            return await client.aio.models.generate_content(
                model=model,
                contents=image_prompt,
                config=image_config,
            )

        image_task = asyncio.create_task(_gen_image())
        img_deadline = loop.time() + _image_timeout_s
        last_keepalive = loop.time()

        while not image_task.done():
            now = loop.time()
            if now >= img_deadline:
                image_task.cancel()
                logger.warning("Scene %d image timed out", scene_idx + 1)
                break
            if now - last_keepalive >= _KEEPALIVE_INTERVAL_S:
                yield _KEEPALIVE_EVENT
                last_keepalive = now
            try:
                await asyncio.wait_for(
                    asyncio.shield(image_task),
                    timeout=min(_KEEPALIVE_INTERVAL_S, img_deadline - now),
                )
            except asyncio.TimeoutError:
                pass

        if image_task.done() and not image_task.cancelled():
            try:
                img_response = image_task.result()
                img_parts = _extract_parts(img_response)
                for p in img_parts:
                    if p["type"] == "image":
                        yield p
                        logger.info(
                            "Scene %d image generated in %.1fs",
                            scene_idx + 1,
                            time.perf_counter() - scene_t0,
                        )
                        break
                else:
                    logger.warning("Scene %d: image model returned no image", scene_idx + 1)
            except Exception as e:
                logger.warning("Scene %d image failed: %s", scene_idx + 1, e)
        else:
            logger.warning("Scene %d: image generation skipped (timeout/cancel)", scene_idx + 1)

        yield _stage_event(
            "scene",
            "complete",
            scene_idx=scene_idx + 1,
            elapsed_s=time.perf_counter() - scene_t0,
        )
        if is_final:
            break
        scene_idx += 1


async def _continuation_flow(chat, req: LiveStoryRequest, model: str) -> AsyncGenerator[dict, None]:
    """Continue an existing story by replaying history through chat, yielding parts immediately.

    Reconstructs the conversation: original prompt → history → continuation.
    Images from history are included so the model sees prior characters.
    """
    # ── Replay original prompt ──────────────────────────────────
    yield _stage_event("replay", "start")
    replay_t0 = time.perf_counter()

    orig = LiveStoryRequest(
        prompt=req.original_prompt or req.prompt,
        style=req.style,
        era=req.era,
        num_scenes=req.num_scenes,
    )
    initial_prompt = _build_prompt(orig)

    try:
        async for item in _call_with_keepalives(chat.send_message(initial_prompt)):
            if isinstance(item, tuple) and item[0] is _RESULT:
                pass  # replay result discarded
            else:
                yield item

        yield _stage_event(
            "replay",
            "complete",
            elapsed_s=time.perf_counter() - replay_t0,
        )
    except asyncio.TimeoutError:
        elapsed = time.perf_counter() - replay_t0
        logger.error("Replay timed out after %.1fs", elapsed)
        yield _stage_event(
            "replay",
            "timeout",
            elapsed_s=elapsed,
            detail=f"Timed out after {_TURN_TIMEOUT_S}s",
        )
        yield {"type": "error", "content": f"Replay timed out after {_TURN_TIMEOUT_S}s"}
        return
    except Exception as e:
        elapsed = time.perf_counter() - replay_t0
        logger.error("Failed to replay original prompt: %s", e)
        yield _stage_event(
            "replay",
            "error",
            elapsed_s=elapsed,
            detail=str(e),
        )
        yield {"type": "error", "content": f"Replay failed: {e}"}
        return

    # ── Continuation ────────────────────────────────────────────
    yield _stage_event("scene", "start", scene_idx=1)
    cont_t0 = time.perf_counter()

    history_text_parts = []
    history_image_parts = []
    for hp in req.history or []:
        if hp.type == "text":
            history_text_parts.append(hp.content)
        elif hp.type == "image" and hp.content:
            history_image_parts.append(hp)

    continuation_parts = []
    for img_hp in history_image_parts[-2:]:
        image_bytes = base64.b64decode(img_hp.content)
        continuation_parts.append(
            types.Part.from_bytes(data=image_bytes, mime_type=img_hp.mime_type or "image/png")
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
        async for item in _stream_scene_parts(chat, continuation_parts):
            if item.get("type") == "_meta":
                if item["empty"]:
                    yield _stage_event(
                        "scene",
                        "error",
                        scene_idx=1,
                        elapsed_s=time.perf_counter() - cont_t0,
                        detail="Empty response from model",
                    )
                    yield {"type": "error", "content": "Continuation: empty response"}
                # _meta is internal — don't forward to client
                continue
            if item.get("type") == "keepalive":
                yield item
                continue
            yield item

        yield _stage_event(
            "scene",
            "complete",
            scene_idx=1,
            elapsed_s=time.perf_counter() - cont_t0,
        )
    except asyncio.TimeoutError:
        elapsed = time.perf_counter() - cont_t0
        logger.error("Continuation timed out after %.1fs", elapsed)
        yield _stage_event(
            "scene",
            "timeout",
            scene_idx=1,
            elapsed_s=elapsed,
            detail=f"Timed out after {_TURN_TIMEOUT_S}s",
        )
        yield {"type": "error", "content": f"Continuation timed out after {_TURN_TIMEOUT_S}s"}
    except Exception as e:
        elapsed = time.perf_counter() - cont_t0
        logger.error("Continuation generation failed: %s", e)
        yield _stage_event(
            "scene",
            "error",
            scene_idx=1,
            elapsed_s=elapsed,
            detail=str(e),
        )
        yield {"type": "error", "content": f"Continuation failed: {e}"}


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _stage_event(
    stage: str,
    status: str,
    *,
    elapsed_s: float | None = None,
    scene_idx: int | None = None,
    detail: str | None = None,
) -> dict:
    """Build a structured stage event for pipeline progress tracking.

    stage: "init", "casting", "scene"
    status: "start", "complete", "error", "timeout"
    """
    evt: dict = {"type": "stage", "stage": stage, "status": status}
    if elapsed_s is not None:
        evt["elapsed_s"] = round(elapsed_s, 1)
    if scene_idx is not None:
        evt["scene_idx"] = scene_idx
    if detail:
        evt["detail"] = detail
    return evt
