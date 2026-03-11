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

LIVE_MODEL_PRIMARY = "gemini-2.5-flash-preview-native-audio-dialog"
LIVE_MODEL_FALLBACK = "gemini-2.0-flash-live-001"

IMAGE_MODEL = "gemini-2.5-flash-image"

SYSTEM_INSTRUCTION = """\
You are Dash, a noir creative director with a deep, gravelly voice. \
You tell stories in shadow and light. You are in a live session with the audience.

RULES:
1. When the user gives you a story premise, narrate it scene by scene in noir prose.
2. After narrating each scene, call generate_scene_image() with a detailed visual description. \
   The description MUST specify: photorealistic photograph, 35mm film, Canon EOS R5, 50mm f/1.4, \
   shallow depth of field, practical lighting. NEVER describe illustrations or drawings.
3. If the user asks about history, call search_historical_context() to ground the story.
4. If the user interrupts or redirects, adapt immediately. You are co-directing with them.
5. Keep narration to 2-3 sentences per scene, then generate the image, then continue.
6. Your voice: clipped, direct, noir. Every word earns its place.

You speak. You don't type. This is a conversation in a dark room."""

LIVE_TOOLS = [
    types.Tool(function_declarations=[
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
    ]),
    types.Tool(google_search=types.GoogleSearch()),
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


async def _generate_image(client: genai.Client, description: str) -> str | None:
    """Generate an image via Gemini and return base64 PNG, or None on failure."""
    try:
        response = await client.aio.models.generate_content(
            model=IMAGE_MODEL,
            contents=description,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
            ),
        )
        if (
            response.candidates
            and response.candidates[0].content.parts
        ):
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.data:
                    return base64.b64encode(part.inline_data.data).decode("ascii")
    except Exception as e:
        logger.error("Image generation failed: %s", e)
    return None


async def _handle_function_call(
    client: genai.Client,
    session,
    ws: WebSocket,
    tool_call: types.FunctionCall,
) -> None:
    """Process a Gemini function call, send results to browser and back to Gemini."""
    fn_name = tool_call.name
    fn_args = dict(tool_call.args) if tool_call.args else {}

    if fn_name == "generate_scene_image":
        description = fn_args.get("description", "")
        mood = fn_args.get("mood", "")
        logger.info("Generating scene image: %s (mood: %s)", description[:80], mood)

        await _send_json(ws, {"type": "status", "content": "generating_image"})

        b64_img = await _generate_image(client, description)

        if b64_img:
            await _send_json(ws, {
                "type": "image",
                "data": b64_img,
                "description": description,
            })
            result = {"success": True, "message": "Image generated and displayed to user."}
        else:
            result = {"success": False, "message": "Image generation failed."}

        # Send function response back to Gemini so it can continue
        await session.send(
            input=types.LiveClientToolResponse(
                function_responses=[
                    types.FunctionResponse(
                        name=fn_name,
                        response=result,
                    )
                ]
            ),
        )

    elif fn_name == "search_historical_context":
        query = fn_args.get("query", "")
        logger.info("Historical search requested: %s", query)

        # Google Search tool handles this automatically via grounding.
        # Send a minimal response back so Gemini continues.
        await session.send(
            input=types.LiveClientToolResponse(
                function_responses=[
                    types.FunctionResponse(
                        name=fn_name,
                        response={
                            "success": True,
                            "message": f"Search completed for: {query}",
                        },
                    )
                ]
            ),
        )

    else:
        logger.warning("Unknown function call: %s", fn_name)
        await session.send(
            input=types.LiveClientToolResponse(
                function_responses=[
                    types.FunctionResponse(
                        name=fn_name,
                        response={"error": f"Unknown function: {fn_name}"},
                    )
                ]
            ),
        )


async def _receive_from_browser(ws: WebSocket, session, stop_event: asyncio.Event) -> None:
    """Loop: read messages from browser WebSocket and forward audio to Gemini."""
    try:
        while not stop_event.is_set():
            raw = await ws.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type")

            if msg_type == "audio":
                audio_b64 = msg.get("data", "")
                if audio_b64:
                    audio_bytes = base64.b64decode(audio_b64)
                    await session.send_realtime_input(
                        audio=types.Blob(data=audio_bytes, mime_type="audio/pcm;rate=16000"),
                    )

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
) -> None:
    """Loop: read responses from Gemini session and forward to browser."""
    try:
        while not stop_event.is_set():
            async for response in session.receive():
                if stop_event.is_set():
                    break

                # Handle audio from model
                if response.server_content and response.server_content.model_turn:
                    for part in response.server_content.model_turn.parts:
                        if part.inline_data and part.inline_data.data:
                            audio_b64 = base64.b64encode(
                                part.inline_data.data
                            ).decode("ascii")
                            ok = await _send_json(ws, {
                                "type": "audio",
                                "data": audio_b64,
                            })
                            if not ok:
                                stop_event.set()
                                return
                        if part.text:
                            await _send_json(ws, {
                                "type": "transcript",
                                "content": part.text,
                            })

                # Handle turn complete
                if response.server_content and response.server_content.turn_complete:
                    await _send_json(ws, {"type": "status", "content": "listening"})

                # Handle tool calls
                if response.tool_call:
                    for fc in response.tool_call.function_calls:
                        await _send_json(ws, {"type": "status", "content": "narrating"})
                        await _handle_function_call(client, session, ws, fc)

            # If receive() generator exits, session may be done
            break

    except Exception as e:
        if not stop_event.is_set():
            logger.error("Error receiving from Gemini: %s", e)
            await _send_json(ws, {"type": "error", "content": str(e)})
        stop_event.set()


@router.websocket("/ws")
async def live_session_ws(ws: WebSocket):
    """WebSocket endpoint bridging browser audio to Gemini Live API."""
    await ws.accept()

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
    model_used = None
    for model in [LIVE_MODEL_PRIMARY, LIVE_MODEL_FALLBACK]:
        try:
            logger.info("Connecting to Gemini Live API with model %s", model)
            session_ctx = client.aio.live.connect(model=model, config=config)
            session = await session_ctx.__aenter__()
            model_used = model
            break
        except Exception as e:
            logger.warning("Model %s failed to connect: %s", model, e)
            continue

    if session is None:
        await _send_json(ws, {
            "type": "error",
            "content": "Failed to connect to Gemini Live API",
        })
        await ws.close()
        return

    logger.info("Gemini Live session established with %s", model_used)
    await _send_json(ws, {"type": "status", "content": "listening"})

    stop_event = asyncio.Event()

    # Run browser→Gemini and Gemini→browser loops concurrently
    browser_task = asyncio.create_task(
        _receive_from_browser(ws, session, stop_event)
    )
    gemini_task = asyncio.create_task(
        _receive_from_gemini(client, session, ws, stop_event)
    )

    try:
        await asyncio.gather(browser_task, gemini_task, return_exceptions=True)
    finally:
        # Clean up
        stop_event.set()
        browser_task.cancel()
        gemini_task.cancel()

        try:
            await session_ctx.__aexit__(None, None, None)
        except Exception:
            pass

        try:
            await ws.close()
        except Exception:
            pass

        logger.info("Live session closed (model: %s)", model_used)
