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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/live-story", tags=["live-story"])

# Models to try in order — best consistency first
_MODEL_CHAIN = [
    "gemini-3.1-flash-image-preview",  # Nano Banana 2: up to 5 character refs
    "gemini-2.5-flash-image",          # fallback
]

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


def _gen_config() -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=DASH_SYSTEM_INSTRUCTION,
        response_modalities=["TEXT", "IMAGE"],
        temperature=1.0,
        max_output_tokens=8192,
        thinking_config=types.ThinkingConfig(thinking_level="MINIMAL"),
    )


def _scrub_thought_parts(chat) -> None:
    """Rebuild model responses in chat history with clean Part objects.

    Even with thinking_budget=0, the model can return thought parts that get
    auto-appended to _curated_history by the SDK.  Replaying these on the next
    turn triggers INVALID_ARGUMENT (thought_signature errors).

    Rather than patching existing Part objects (which can leave orphaned
    thought_signature fields), we rebuild each content entry with brand-new
    Part objects containing only text and inline_data — no thought metadata.
    """
    for content in chat._curated_history:
        if not content.parts:
            continue
        clean_parts = []
        for p in content.parts:
            # Skip thought parts entirely
            if isinstance(getattr(p, "thought", None), bool) and p.thought:
                continue
            # Rebuild text parts as fresh objects (drops thought_signature)
            if p.text is not None:
                clean_parts.append(types.Part.from_text(text=p.text))
            # Rebuild image parts as fresh objects
            elif p.inline_data is not None:
                clean_parts.append(types.Part.from_bytes(
                    data=p.inline_data.data,
                    mime_type=p.inline_data.mime_type or "image/png",
                ))
            # Keep other part types as-is (e.g. function calls)
            else:
                clean_parts.append(p)
        content.parts = clean_parts


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
    chat,
    prompt,
    *,
    timeout_s: float = _TURN_TIMEOUT_S,
    flush_timeout_s: float = _TEXT_FLUSH_TIMEOUT_S,
    keepalive_s: float = _KEEPALIVE_INTERVAL_S,
) -> AsyncGenerator[dict, None]:
    """Stream scene text+image from ``send_message_stream()``.

    Yields text as a single ``{"type": "text", ...}`` as soon as a gap of
    *flush_timeout_s* is detected between chunks (text finishes fast, image
    takes much longer).  Images are yielded as ``{"type": "image", ...}`` when
    they arrive.  Keepalive events are emitted while waiting for the image so
    the SSE connection stays alive.

    After the generator is exhausted the caller MUST run
    ``_scrub_thought_parts(chat)`` to clean the chat history.
    """
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout_s

    stream = chat.send_message_stream(prompt)
    stream_iter = stream.__aiter__()

    accumulated_text: list[str] = []
    text_yielded = False
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

        for part in chunk.candidates[0].content.parts:
            if getattr(part, "thought", False):
                continue
            if part.text is not None:
                accumulated_text.append(part.text)
                got_any_content = True
            elif part.inline_data is not None:
                got_any_content = True
                # Flush any pending text before the image
                if accumulated_text and not text_yielded:
                    full_text = "".join(accumulated_text)
                    clean = full_text.replace("[END]", "").rstrip()
                    if clean:
                        yield {"type": "text", "content": clean}
                    text_yielded = True
                b64 = base64.b64encode(part.inline_data.data).decode("ascii")
                yield {
                    "type": "image",
                    "content": b64,
                    "mime_type": part.inline_data.mime_type or "image/png",
                }

    # Flush any remaining text (e.g. text-only scene with no image)
    if accumulated_text and not text_yielded:
        full_text = "".join(accumulated_text)
        clean = full_text.replace("[END]", "").rstrip()
        if clean:
            yield {"type": "text", "content": clean}
        text_yielded = True

    # Determine whether the model signalled end-of-story
    raw_text = "".join(accumulated_text)
    is_final = "[END]" in raw_text

    # Yield metadata so the caller knows if the story ended and if content was empty
    yield {
        "type": "_meta",
        "is_final": is_final,
        "empty": not got_any_content,
    }


def _extract_parts(response) -> list[dict]:
    """Extract text and image parts from a Gemini response."""
    results = []
    if not response.candidates or not response.candidates[0].content or not response.candidates[0].content.parts:
        return results
    for part in response.candidates[0].content.parts:
        if getattr(part, "thought", False):
            continue
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

        # Stage: init
        yield _sse(_stage_event("init", "start"))
        init_t0 = time.perf_counter()

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
            yield _sse(_stage_event(
                "init", "error",
                elapsed_s=time.perf_counter() - init_t0,
                detail=f"All models failed: {last_error}",
            ))
            yield _sse({"type": "error", "content": f"All models failed: {last_error}"})
            return

        yield _sse(_stage_event(
            "init", "complete",
            elapsed_s=time.perf_counter() - init_t0,
            detail=model_used,
        ))

        if is_continuation:
            flow = _continuation_flow(chat, req, model_used)
        else:
            flow = _scene_by_scene_flow(chat, req, model_used)

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
) -> AsyncGenerator[dict, None]:
    """Generate story scene-by-scene via chat turns, yielding each part immediately.

    Turn 0 (hidden): Casting photo — character portraits for visual anchoring
    Turns 1..N: Model generates scenes until it signals [END]
    """
    base_prompt = _build_prompt(req)

    # ── Casting (Scene 0) ───────────────────────────────────────
    yield _stage_event("casting", "start")

    casting_prompt = (
        f"{base_prompt}\n\n"
        f"CASTING CALL: Before we begin filming, generate a casting photo. "
        f"Describe each main character's exact appearance in detail "
        f"(face shape, skin tone, hair color/style, eye color, build, age, "
        f"distinguishing marks, wardrobe). Then generate ONE image: a portrait "
        f"lineup of the main characters standing side by side, well-lit, "
        f"facing the camera. This is the reference photo for the entire film."
    )
    casting_t0 = time.perf_counter()
    try:
        response = None
        async for item in _call_with_keepalives(chat.send_message(casting_prompt)):
            if isinstance(item, tuple) and item[0] is _RESULT:
                response = item[1]
            else:
                yield item
        _scrub_thought_parts(chat)
        casting_parts = _extract_parts(response)
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
            "casting", "complete",
            elapsed_s=time.perf_counter() - casting_t0,
        )
    except asyncio.TimeoutError:
        elapsed = time.perf_counter() - casting_t0
        logger.warning("Casting photo timed out after %.1fs", elapsed)
        yield _stage_event(
            "casting", "timeout",
            elapsed_s=elapsed,
            detail=f"Timed out after {_TURN_TIMEOUT_S}s",
        )
    except Exception as e:
        elapsed = time.perf_counter() - casting_t0
        logger.warning("Casting photo failed (continuing without): %s", e)
        yield _stage_event(
            "casting", "error",
            elapsed_s=elapsed,
            detail=str(e),
        )

    # ── Scenes — model decides how many; stops on [END] marker ──
    max_scenes = 20  # safety cap
    scene_idx = 0
    while scene_idx < max_scenes:
        yield _stage_event("scene", "start", scene_idx=scene_idx + 1)
        scene_t0 = time.perf_counter()

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
            is_final = False
            async for item in _stream_scene_parts(chat, prompt):
                if item.get("type") == "_meta":
                    is_final = item["is_final"]
                    if item["empty"]:
                        yield _stage_event(
                            "scene", "error",
                            scene_idx=scene_idx + 1,
                            elapsed_s=time.perf_counter() - scene_t0,
                            detail="Empty response from model",
                        )
                        yield {"type": "error", "content": f"Scene {scene_idx + 1}: empty response"}
                        break
                elif item.get("type") == "keepalive":
                    yield item
                else:
                    yield item
            else:
                # Loop completed without break — stream finished normally
                _scrub_thought_parts(chat)
                yield _stage_event(
                    "scene", "complete",
                    scene_idx=scene_idx + 1,
                    elapsed_s=time.perf_counter() - scene_t0,
                )
                if is_final:
                    break
                scene_idx += 1
                continue

            # If we broke out of the for-loop (empty response), stop
            _scrub_thought_parts(chat)
            break

        except asyncio.TimeoutError:
            elapsed = time.perf_counter() - scene_t0
            logger.error("Scene %d timed out after %.1fs", scene_idx + 1, elapsed)
            yield _stage_event(
                "scene", "timeout",
                scene_idx=scene_idx + 1,
                elapsed_s=elapsed,
                detail=f"Timed out after {_TURN_TIMEOUT_S}s",
            )
            yield {"type": "error", "content": f"Scene {scene_idx + 1} timed out after {_TURN_TIMEOUT_S}s"}
            break

        except Exception as e:
            elapsed = time.perf_counter() - scene_t0
            logger.error("Scene %d generation failed: %s", scene_idx + 1, e)
            yield _stage_event(
                "scene", "error",
                scene_idx=scene_idx + 1,
                elapsed_s=elapsed,
                detail=str(e),
            )
            yield {"type": "error", "content": f"Scene {scene_idx + 1} failed: {e}"}
            break


async def _continuation_flow(
    chat, req: LiveStoryRequest, model: str
) -> AsyncGenerator[dict, None]:
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
        _scrub_thought_parts(chat)
        yield _stage_event(
            "replay", "complete",
            elapsed_s=time.perf_counter() - replay_t0,
        )
    except asyncio.TimeoutError:
        elapsed = time.perf_counter() - replay_t0
        logger.error("Replay timed out after %.1fs", elapsed)
        yield _stage_event(
            "replay", "timeout",
            elapsed_s=elapsed,
            detail=f"Timed out after {_TURN_TIMEOUT_S}s",
        )
        yield {"type": "error", "content": f"Replay timed out after {_TURN_TIMEOUT_S}s"}
        return
    except Exception as e:
        elapsed = time.perf_counter() - replay_t0
        logger.error("Failed to replay original prompt: %s", e)
        yield _stage_event(
            "replay", "error",
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
        async for item in _stream_scene_parts(chat, continuation_parts):
            if item.get("type") == "_meta":
                if item["empty"]:
                    yield _stage_event(
                        "scene", "error",
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
        _scrub_thought_parts(chat)
        yield _stage_event(
            "scene", "complete",
            scene_idx=1,
            elapsed_s=time.perf_counter() - cont_t0,
        )
    except asyncio.TimeoutError:
        elapsed = time.perf_counter() - cont_t0
        logger.error("Continuation timed out after %.1fs", elapsed)
        yield _stage_event(
            "scene", "timeout",
            scene_idx=1,
            elapsed_s=elapsed,
            detail=f"Timed out after {_TURN_TIMEOUT_S}s",
        )
        yield {"type": "error", "content": f"Continuation timed out after {_TURN_TIMEOUT_S}s"}
    except Exception as e:
        elapsed = time.perf_counter() - cont_t0
        logger.error("Continuation generation failed: %s", e)
        yield _stage_event(
            "scene", "error",
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
