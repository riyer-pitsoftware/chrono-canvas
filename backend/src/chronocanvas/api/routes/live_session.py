"""Live Session — WebSocket bridge between browser and Gemini Live API.

Real-time bidirectional audio streaming for noir storytelling with Dash.
Browser sends mic audio, Gemini responds with narration audio, and tool calls
trigger image generation and historical search mid-session.
"""

import asyncio
import base64
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types

from chronocanvas.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/live-session", tags=["live-session"])

LIVE_MODEL_PRIMARY = "gemini-2.5-flash-native-audio-latest"
LIVE_MODEL_FALLBACK = "gemini-2.5-flash-native-audio-preview-12-2025"

# Image generation models — speed first for live sessions
_IMAGE_MODEL_CHAIN = [
    "imagen-4.0-fast-generate-001",  # Fastest: ~2-3s, purpose-built
    "gemini-2.5-flash-image",  # Fallback: slower, supports reference images
]

SYSTEM_INSTRUCTION = """\
You are Dash, a noir creative director with a deep, gravelly voice. \
You tell stories in shadow and light. You are in a live session with the audience.

CHARACTER CONSISTENCY (CRITICAL):
Before starting, mentally cast your characters. Lock in each character's exact \
physical appearance — face shape, skin tone, hair color/style, eye color, build, \
age, distinguishing marks, and wardrobe. Once set, NEVER deviate.

WORKFLOW (YOU MUST FOLLOW THIS EXACTLY):
1. Narrate ONE scene in 2-3 sentences of noir prose.
2. STOP talking.
3. Call generate_scene_image() with a detailed visual description of that scene.
4. WAIT for the image result before continuing.
5. Then narrate the NEXT scene and repeat.

YOU MUST call generate_scene_image() after EVERY scene. This is not optional. \
If you narrate without calling generate_scene_image(), the audience sees nothing. \
NEVER narrate more than one scene without calling the function.

IMAGE DESCRIPTION RULES for generate_scene_image():
- MUST specify: photorealistic photograph, 35mm film, Canon EOS R5, 50mm f/1.4, \
  shallow depth of field, practical lighting.
- NEVER describe illustrations or drawings.
- ALWAYS re-state each visible character's key physical features (face, hair, skin tone, \
  build, clothing) in EVERY image description — do NOT rely on context alone.

OTHER RULES:
- If the user asks about history, call search_historical_context() to ground the story.
- If the user interrupts or redirects, adapt immediately. You are co-directing with them.
- Your voice: clipped, direct, noir. Every word earns its place.

You speak. You don't type. This is a conversation in a dark room."""

LIVE_TOOLS = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="generate_scene_image",
                description="Generate a photorealistic noir scene image based on the current narration",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "description": types.Schema(
                            type="STRING",
                            description="Detailed visual description of the scene to photograph",
                        ),
                        "mood": types.Schema(
                            type="STRING",
                            description="Emotional mood: tense, melancholy, mysterious, dangerous",
                        ),
                    },
                    required=["description"],
                ),
            ),
            types.FunctionDeclaration(
                name="search_historical_context",
                description="Search for historical facts to ground the story in reality",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(
                            type="STRING",
                            description="Historical search query",
                        ),
                    },
                    required=["query"],
                ),
            ),
        ]
    ),
    # NOTE: google_search tool removed — mixing it with function_declarations
    # in Live API causes Gemini 1011 internal errors mid-stream.
    # search_historical_context uses the function call path instead.
]


def _build_live_config(voice_name: str = "Charon") -> types.LiveConnectConfig:
    return types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=SYSTEM_INSTRUCTION,
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name)
            )
        ),
        tools=LIVE_TOOLS,
    )


async def _send_json(ws: WebSocket, data: dict) -> bool:
    """Send JSON to browser. Returns False if connection is closed."""
    try:
        await ws.send_text(json.dumps(data))
        return True
    except Exception:
        return False


_IMAGE_STYLE_PREFIX = (
    "Photorealistic photograph. Shot on 35mm film, Canon EOS R5, 50mm f/1.4 lens. "
    "Shallow depth of field, natural film grain, practical lighting only. "
    "Real people, real places, real textures. NOT illustration, NOT drawing, "
    "NOT cartoon, NOT digital art. Photorealistic only. "
)


async def _generate_image(
    client: genai.Client, description: str, last_image_b64: str | None = None
) -> str | None:
    """Generate an image and return base64, or None on failure.

    Tries Imagen Fast first (fastest, ~2-3s, no reference image support).
    Falls back to Gemini image gen which supports reference images for
    character consistency across scenes.
    """
    styled_description = f"{_IMAGE_STYLE_PREFIX}{description}"

    for img_model in _IMAGE_MODEL_CHAIN:
        try:
            if img_model.startswith("imagen"):
                # Imagen API — fastest, but no reference image support
                response = await client.aio.models.generate_images(
                    model=img_model,
                    prompt=styled_description,
                    config=types.GenerateImagesConfig(
                        number_of_images=1,
                        aspect_ratio="16:9",
                        person_generation="ALLOW_ADULT",
                    ),
                )
                if response.generated_images:
                    img = response.generated_images[0]
                    return base64.b64encode(img.image.image_bytes).decode("ascii")
            else:
                # Gemini image gen — supports reference image for consistency
                contents: list = []
                if last_image_b64:
                    image_bytes = base64.b64decode(last_image_b64)
                    contents.append(
                        types.Part.from_bytes(data=image_bytes, mime_type="image/png")
                    )
                    contents.append(
                        types.Part.from_text(
                            text=f"Maintain the same characters with identical "
                            f"faces and features as shown in the reference "
                            f"image above. {styled_description}"
                        )
                    )
                else:
                    contents.append(types.Part.from_text(text=styled_description))

                gen_config = types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                )
                response = await client.aio.models.generate_content(
                    model=img_model,
                    contents=contents,
                    config=gen_config,
                )
                if response.candidates and response.candidates[0].content.parts:
                    for part in response.candidates[0].content.parts:
                        if part.inline_data and part.inline_data.data:
                            return base64.b64encode(
                                part.inline_data.data
                            ).decode("ascii")
        except Exception as e:
            logger.warning("Image model %s failed: %s", img_model, e)
            continue

    logger.error("All image models failed for: %s", description[:80])
    return None


async def _generate_image_background(
    client: genai.Client,
    ws: WebSocket,
    description: str,
    session_state: dict,
) -> None:
    """Generate image in background and send to browser when ready.

    Runs as a fire-and-forget task so the receive loop stays unblocked,
    keeping the Gemini WebSocket alive (pings/pongs flow).
    """
    try:
        last_img = session_state.get("last_image_b64")
        b64_img = await _generate_image(client, description, last_image_b64=last_img)

        if b64_img:
            session_state["last_image_b64"] = b64_img
            await _send_json(
                ws,
                {
                    "type": "image",
                    "data": b64_img,
                    "description": description,
                },
            )
            logger.info("Background image delivered to browser")
        else:
            logger.warning("Background image generation failed")
    except Exception as e:
        logger.error("Background image generation error: %s", e)


async def _handle_function_call(
    client: genai.Client,
    session,
    ws: WebSocket,
    tool_call: types.FunctionCall,
    session_state: dict,
) -> None:
    """Process a Gemini function call, send results to browser and back to Gemini.

    Image generation is fire-and-forget in the background so we don't block
    the receive loop (which would starve WebSocket pings and kill the session).
    We send an immediate FunctionResponse to Gemini so it continues narrating.
    """
    fn_name = tool_call.name
    fn_args = dict(tool_call.args) if tool_call.args else {}

    if fn_name == "generate_scene_image":
        description = fn_args.get("description", "")
        mood = fn_args.get("mood", "")
        logger.info("Generating scene image: %s (mood: %s)", description[:80], mood)

        await _send_json(ws, {"type": "status", "content": "generating_image"})

        # Fire off image generation in background — don't block receive loop
        asyncio.create_task(_generate_image_background(client, ws, description, session_state))

        # Send immediate response — tell Gemini to PAUSE and wait for user
        await session.send_tool_response(
            function_responses=[
                types.FunctionResponse(
                    id=tool_call.id,
                    name=fn_name,
                    response={
                        "success": True,
                        "message": "Image is being generated and will appear for the audience. "
                        "STOP talking now. Wait silently for the audience to respond "
                        "before narrating the next scene.",
                    },
                )
            ],
        )

    elif fn_name == "search_historical_context":
        query = fn_args.get("query", "")
        logger.info("Historical search requested: %s", query)

        await session.send_tool_response(
            function_responses=[
                types.FunctionResponse(
                    id=tool_call.id,
                    name=fn_name,
                    response={
                        "success": True,
                        "message": f"Search completed for: {query}",
                    },
                )
            ],
        )

    else:
        logger.warning("Unknown function call: %s", fn_name)
        await session.send_tool_response(
            function_responses=[
                types.FunctionResponse(
                    id=tool_call.id,
                    name=fn_name,
                    response={"error": f"Unknown function: {fn_name}"},
                )
            ],
        )


_PING_INTERVAL_S = 20.0


async def _keepalive_ping(ws: WebSocket, stop_event: asyncio.Event) -> None:
    """Send periodic pings to keep proxies and browsers from closing idle connections."""
    while not stop_event.is_set():
        await asyncio.sleep(_PING_INTERVAL_S)
        if stop_event.is_set():
            break
        ok = await _send_json(ws, {"type": "ping"})
        if not ok:
            stop_event.set()
            return


async def _receive_from_browser(ws: WebSocket, session, stop_event: asyncio.Event) -> None:
    """Loop: read messages from browser WebSocket and forward audio to Gemini."""
    audio_chunks_received = 0
    try:
        while not stop_event.is_set():
            raw = await ws.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type")

            if msg_type == "audio":
                audio_b64 = msg.get("data", "")
                if audio_b64:
                    audio_bytes = base64.b64decode(audio_b64)
                    audio_chunks_received += 1
                    if audio_chunks_received == 1:
                        logger.info(
                            "First audio chunk from browser: %d bytes",
                            len(audio_bytes),
                        )
                    elif audio_chunks_received % 50 == 0:
                        logger.info("Audio chunks from browser: %d", audio_chunks_received)
                    try:
                        await session.send_realtime_input(
                            audio=types.Blob(
                                data=audio_bytes,
                                mime_type="audio/pcm;rate=16000",
                            ),
                        )
                    except Exception as e:
                        logger.error(
                            "Failed to send audio to Gemini (chunk %d): %s",
                            audio_chunks_received,
                            e,
                        )
                        await _send_json(
                            ws,
                            {
                                "type": "error",
                                "content": "Lost connection to Gemini. Please restart the session.",
                            },
                        )
                        stop_event.set()
                        break

            elif msg_type == "end_turn":
                # User tapped Send — send a burst of silence so auto-VAD
                # detects end-of-speech and triggers Gemini's response.
                # We use silence instead of audio_stream_end (which permanently
                # kills the audio stream) or send_client_content (which is
                # invalid when mixed with send_realtime_input).
                logger.info("User ended turn manually (Send button)")
                try:
                    silence = b"\x00" * 32000  # 1s at 16kHz mono 16-bit
                    await session.send_realtime_input(
                        audio=types.Blob(
                            data=silence, mime_type="audio/pcm;rate=16000",
                        ),
                    )
                    logger.info("Sent 1s silence to trigger VAD")
                except Exception as e:
                    logger.error("Failed to send silence: %s", e)

            elif msg_type == "stop":
                logger.info("Client requested session stop")
                stop_event.set()
                break

    except WebSocketDisconnect:
        logger.info("Browser disconnected")
        stop_event.set()
    except Exception as e:
        logger.error("Error receiving from browser: %s", e)
        stop_event.set()


async def _receive_from_gemini(
    client: genai.Client,
    session,
    ws: WebSocket,
    stop_event: asyncio.Event,
    session_state: dict | None = None,
) -> None:
    """Loop: read responses from Gemini session and forward to browser."""
    _receive_timeout_s = 120  # Max seconds to wait for a single Gemini response
    gemini_response_count = 0
    try:
        while not stop_event.is_set():
            aiter = session.receive().__aiter__()
            while not stop_event.is_set():
                try:
                    response = await asyncio.wait_for(
                        aiter.__anext__(),
                        timeout=_receive_timeout_s,
                    )
                except StopAsyncIteration:
                    break
                except asyncio.TimeoutError:
                    logger.warning(
                        "Gemini receive timed out after %ds",
                        _receive_timeout_s,
                    )
                    stop_event.set()
                    return

                gemini_response_count += 1
                # Log what's in this response for debugging
                has_audio = bool(
                    response.server_content
                    and response.server_content.model_turn
                    and response.server_content.model_turn.parts
                )
                has_tool_call = bool(response.tool_call)
                turn_complete = bool(
                    response.server_content and response.server_content.turn_complete
                )

                if gemini_response_count == 1:
                    logger.info(
                        "First Gemini response: audio=%s tool_call=%s turn_complete=%s",
                        has_audio,
                        has_tool_call,
                        turn_complete,
                    )
                elif gemini_response_count % 20 == 0:
                    logger.info("Gemini responses received: %d", gemini_response_count)

                # Handle audio from model
                if response.server_content and response.server_content.model_turn:
                    for part in response.server_content.model_turn.parts:
                        if part.inline_data and part.inline_data.data:
                            audio_b64 = base64.b64encode(part.inline_data.data).decode("ascii")
                            ok = await _send_json(
                                ws,
                                {
                                    "type": "audio",
                                    "data": audio_b64,
                                },
                            )
                            if not ok:
                                stop_event.set()
                                return
                        if part.text:
                            await _send_json(
                                ws,
                                {
                                    "type": "transcript",
                                    "content": part.text,
                                },
                            )

                # Handle turn complete
                if response.server_content and response.server_content.turn_complete:
                    await _send_json(ws, {"type": "status", "content": "listening"})

                # Handle tool calls
                if response.tool_call:
                    for fc in response.tool_call.function_calls:
                        await _send_json(ws, {"type": "status", "content": "narrating"})
                        await _handle_function_call(client, session, ws, fc, session_state)

            # receive() generator exhausted for this turn — loop back
            # to call receive() again for the next turn
            logger.info("Gemini receive() cycle complete, awaiting next turn")

    except Exception as e:
        if not stop_event.is_set():
            logger.error(
                "Error receiving from Gemini: %s: %s", type(e).__name__, e
            )
            # Surface the actual error type so we can diagnose
            err_msg = f"Gemini error: {type(e).__name__}: {e}"
            await _send_json(ws, {"type": "error", "content": err_msg})
        stop_event.set()


@router.websocket("/ws")
async def live_session_ws(ws: WebSocket):
    """WebSocket endpoint bridging browser audio to Gemini Live API."""
    await ws.accept()

    session_ctx = None
    model_used = None

    try:
        if not settings.google_api_key:
            await _send_json(ws, {"type": "error", "content": "GOOGLE_API_KEY not configured"})
            await ws.close()
            return

        # Wait for start message
        try:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            if msg.get("type") != "start":
                await _send_json(ws, {"type": "error", "content": "Expected start message"})
                await ws.close()
                return
        except (WebSocketDisconnect, Exception) as e:
            logger.warning("Connection closed before start: %s", e)
            return

        client = genai.Client(api_key=settings.google_api_key)
        config = _build_live_config()

        # Try primary model, fall back if needed
        session = None
        for model in [LIVE_MODEL_PRIMARY, LIVE_MODEL_FALLBACK]:
            try:
                logger.info("Connecting to Gemini Live API with model %s", model)
                session_ctx = client.aio.live.connect(model=model, config=config)
                session = await session_ctx.__aenter__()
                model_used = model
                break
            except Exception as e:
                logger.warning("Model %s failed to connect: %s", model, e)
                # Clean up partially-entered context manager
                if session_ctx is not None:
                    try:
                        await session_ctx.__aexit__(None, None, None)
                    except Exception:
                        pass
                    session_ctx = None
                continue

        if session is None:
            await _send_json(
                ws,
                {
                    "type": "error",
                    "content": "Failed to connect to Gemini Live API",
                },
            )
            await ws.close()
            return

        logger.info("Gemini Live session established with %s", model_used)
        await _send_json(ws, {"type": "status", "content": "listening"})

        stop_event = asyncio.Event()
        # Track state across the session (e.g., last image for consistency)
        session_state: dict = {}

        # Run browser→Gemini, Gemini→browser, and keepalive loops concurrently
        browser_task = asyncio.create_task(_receive_from_browser(ws, session, stop_event))
        gemini_task = asyncio.create_task(
            _receive_from_gemini(client, session, ws, stop_event, session_state)
        )
        ping_task = asyncio.create_task(_keepalive_ping(ws, stop_event))

        try:
            results = await asyncio.gather(
                browser_task,
                gemini_task,
                ping_task,
                return_exceptions=True,
            )
            # Log any exceptions that were swallowed by return_exceptions
            for i, result in enumerate(results):
                if isinstance(result, BaseException):
                    task_name = ["browser", "gemini", "ping"][i]
                    logger.error("Task %s exited with error: %s", task_name, result)
        finally:
            # Clean up tasks
            stop_event.set()
            browser_task.cancel()
            gemini_task.cancel()
            ping_task.cancel()

    except Exception as e:
        # Top-level catch — prevents 1011 from leaking to browser
        logger.error("Live session crashed: %s: %s", type(e).__name__, e)
        await _send_json(
            ws,
            {"type": "error", "content": f"Session error: {e}"},
        )
    finally:
        # Clean up Gemini session
        if session_ctx is not None:
            try:
                await session_ctx.__aexit__(None, None, None)
            except Exception:
                pass

        try:
            await ws.close(code=1000, reason="session ended")
        except Exception:
            pass

        logger.info("Live session closed (model: %s)", model_used)
