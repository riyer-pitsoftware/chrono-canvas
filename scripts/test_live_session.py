#!/usr/bin/env python3
"""Live Session test suite — exercises WebSocket + Gemini Live API.

Tests run against localhost. Requires services to be running (make restart).

Usage:
    python scripts/test_live_session.py              # all tests
    python scripts/test_live_session.py --quick       # connectivity only
    python scripts/test_live_session.py --image-only  # image gen only
"""

import argparse
import asyncio
import base64
import json
import struct
import sys
import time

import websockets

WS_URL = "ws://localhost:3000/api/live-session/ws"
HEALTH_URL = "http://localhost:3000/api/health"
AUTH_CHECK_URL = "http://localhost:3000/api/auth/check"
AUTH_LOGIN_URL = "http://localhost:3000/api/auth/login"

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
WARN = "\033[93m⚠\033[0m"
INFO = "\033[94m→\033[0m"

results: list[tuple[str, bool, str]] = []


def report(name: str, ok: bool, detail: str = ""):
    results.append((name, ok, detail))
    mark = PASS if ok else FAIL
    suffix = f" — {detail}" if detail else ""
    print(f"  {mark} {name}{suffix}")


async def get_auth_cookie() -> dict:
    """Get session cookie if auth is enabled."""
    import aiohttp
    async with aiohttp.ClientSession() as s:
        async with s.get(AUTH_CHECK_URL) as resp:
            data = await resp.json()
            if data.get("authenticated"):
                return {}
        # Need to log in — try common dev password
        import os
        password = os.environ.get("APP_PASSWORD", "")
        if not password:
            print(f"  {WARN} APP_PASSWORD env var needed for auth. Set it and retry.")
            sys.exit(1)
        async with s.post(AUTH_LOGIN_URL, json={"password": password}) as resp:
            data = await resp.json()
            if not data.get("ok"):
                print(f"  {FAIL} Login failed: {data}")
                sys.exit(1)
            cookies = {c.key: c.value for c in s.cookie_jar}
            return cookies


async def test_health():
    """T1: Health endpoint returns ok + hackathon_mode."""
    print("\n── T1: Health Check ──")
    import aiohttp
    async with aiohttp.ClientSession() as s:
        async with s.get(HEALTH_URL) as resp:
            data = await resp.json()
            report("Health status ok", data.get("status") == "ok")
            report("Deployment mode gcp", data.get("deployment_mode") == "gcp",
                   data.get("deployment_mode", "?"))
            report("Hackathon mode on", data.get("hackathon_mode") is True)
            gemini = data.get("services", {}).get("llm", {}).get("gemini")
            report("Gemini available", gemini is True)


async def test_ws_connect_and_start():
    """T2: WebSocket connects and receives 'listening' status after start."""
    print("\n── T2: WebSocket Connect + Start ──")
    try:
        async with websockets.connect(WS_URL, open_timeout=10) as ws:
            report("WebSocket connected", True)

            await ws.send(json.dumps({"type": "start"}))
            report("Start message sent", True)

            # Wait for status=listening or error
            msg = await asyncio.wait_for(ws.recv(), timeout=30)
            data = json.loads(msg)
            is_listening = (data.get("type") == "status"
                            and data.get("content") == "listening")
            is_error = data.get("type") == "error"

            if is_error:
                report("Gemini session established", False, data.get("content", ""))
            else:
                report("Gemini session established", is_listening,
                       f"type={data.get('type')}, content={data.get('content')}")

            # Send stop to clean up
            await ws.send(json.dumps({"type": "stop"}))

    except Exception as e:
        report("WebSocket connected", False, str(e))


async def test_ws_audio_round_trip():
    """T3: Send silent audio, receive audio response from Gemini."""
    print("\n── T3: Audio Round Trip ──")
    try:
        async with websockets.connect(WS_URL, open_timeout=10) as ws:
            await ws.send(json.dumps({"type": "start"}))
            # Wait for listening
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
            if msg.get("type") == "error":
                report("Session ready", False, msg.get("content", ""))
                return

            report("Session ready", True)

            # Generate 1 second of silence at 16kHz (16-bit PCM)
            # Then a short sine wave to trigger speech detection
            samples = 16000
            silent_pcm = struct.pack(f"<{samples}h", *([0] * samples))
            b64_audio = base64.b64encode(silent_pcm).decode("ascii")
            await ws.send(json.dumps({"type": "audio", "data": b64_audio}))
            report("Sent 1s silent audio", True)

            # Generate a tone burst (440Hz) to simulate speech
            import math
            tone_samples = 16000 * 2  # 2 seconds
            tone_pcm = struct.pack(
                f"<{tone_samples}h",
                *[int(16000 * math.sin(2 * math.pi * 440 * i / 16000))
                  for i in range(tone_samples)]
            )
            b64_tone = base64.b64encode(tone_pcm).decode("ascii")
            await ws.send(json.dumps({"type": "audio", "data": b64_tone}))
            report("Sent 2s tone burst", True)

            # Wait for any response (audio, transcript, status, or ping)
            got_audio = False
            got_transcript = False
            got_any = False
            start = time.time()
            timeout = 30  # seconds

            while time.time() - start < timeout:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=5)
                    data = json.loads(raw)
                    got_any = True
                    msg_type = data.get("type")

                    if msg_type == "audio":
                        got_audio = True
                        audio_bytes = base64.b64decode(data["data"])
                        report("Received audio response", True,
                               f"{len(audio_bytes)} bytes")
                        break
                    elif msg_type == "transcript":
                        got_transcript = True
                        report("Received transcript", True,
                               data.get("content", "")[:60])
                    elif msg_type == "ping":
                        continue
                    elif msg_type == "status":
                        print(f"    {INFO} Status: {data.get('content')}")
                        if data.get("content") == "listening" and got_any:
                            break

                except asyncio.TimeoutError:
                    break

            if not got_audio and not got_transcript:
                report("Received response from Gemini", got_any,
                       "no audio or transcript received — tone may not trigger speech")

            await ws.send(json.dumps({"type": "stop"}))

    except Exception as e:
        report("Audio round trip", False, str(e))


async def test_image_generation():
    """T4: Test image generation directly via Gemini API (not through WebSocket)."""
    print("\n── T4: Image Generation (Direct API) ──")
    try:
        from google import genai
        from google.genai import types
        import os

        api_key = os.environ.get("GOOGLE_API_KEY", "")
        if not api_key:
            # Try reading from .env
            env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
            if os.path.exists(env_path):
                for line in open(env_path):
                    if line.startswith("GOOGLE_API_KEY="):
                        api_key = line.split("=", 1)[1].strip()
                        break

        if not api_key:
            report("Google API key found", False, "Set GOOGLE_API_KEY")
            return

        report("Google API key found", True)

        client = genai.Client(api_key=api_key)
        models = [
            "gemini-3.1-flash-image-preview",
            "gemini-2.5-flash-image",
        ]

        description = (
            "Photorealistic photograph. Shot on 35mm film, Canon EOS R5, 50mm f/1.4 lens. "
            "Shallow depth of field, natural film grain, practical lighting only. "
            "A dimly lit 1940s jazz club in Harlem. A woman in a red dress sits alone at "
            "the bar, cigarette smoke curling upward. The bartender polishes a glass. "
            "Warm amber light from a single pendant lamp."
        )

        for model in models:
            print(f"    {INFO} Trying {model}...")
            start = time.time()
            try:
                gen_config = types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                )
                if "3.1" in model:
                    gen_config.thinking_config = types.ThinkingConfig(thinking_level="MINIMAL")

                response = await client.aio.models.generate_content(
                    model=model,
                    contents=[types.Part.from_text(text=description)],
                    config=gen_config,
                )
                elapsed = time.time() - start

                if (response.candidates
                        and response.candidates[0].content.parts):
                    for part in response.candidates[0].content.parts:
                        if part.inline_data and part.inline_data.data:
                            img_bytes = part.inline_data.data
                            report(f"Image gen ({model})", True,
                                   f"{len(img_bytes)//1024}KB in {elapsed:.1f}s")
                            # Save for inspection
                            out_path = f"/tmp/live_session_test_{model.replace('/', '_')}.png"
                            with open(out_path, "wb") as f:
                                f.write(img_bytes)
                            print(f"    {INFO} Saved to {out_path}")
                            break
                    else:
                        report(f"Image gen ({model})", False,
                               f"No image data in response ({elapsed:.1f}s)")
                else:
                    report(f"Image gen ({model})", False,
                           f"No candidates in response ({elapsed:.1f}s)")

            except Exception as e:
                elapsed = time.time() - start
                report(f"Image gen ({model})", False,
                       f"{e} ({elapsed:.1f}s)")

    except ImportError as e:
        report("google-genai installed", False, str(e))


async def test_ws_keepalive():
    """T5: Verify keepalive pings arrive within expected interval."""
    print("\n── T5: WebSocket Keepalive ──")
    try:
        async with websockets.connect(WS_URL, open_timeout=10) as ws:
            await ws.send(json.dumps({"type": "start"}))
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
            if msg.get("type") == "error":
                report("Keepalive test", False, msg.get("content", ""))
                return

            # Wait for a ping (should come within 20s)
            print(f"    {INFO} Waiting up to 25s for keepalive ping...")
            start = time.time()
            got_ping = False
            while time.time() - start < 25:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=5)
                    data = json.loads(raw)
                    if data.get("type") == "ping":
                        elapsed = time.time() - start
                        got_ping = True
                        report("Keepalive ping received", True, f"after {elapsed:.1f}s")
                        break
                except asyncio.TimeoutError:
                    continue

            if not got_ping:
                report("Keepalive ping received", False, "no ping within 25s")

            await ws.send(json.dumps({"type": "stop"}))

    except Exception as e:
        report("Keepalive test", False, str(e))


async def test_graceful_stop():
    """T6: Clean session stop — no errors after sending stop message."""
    print("\n── T6: Graceful Stop ──")
    try:
        async with websockets.connect(WS_URL, open_timeout=10) as ws:
            await ws.send(json.dumps({"type": "start"}))
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
            if msg.get("type") == "error":
                report("Graceful stop", False, msg.get("content", ""))
                return

            report("Session started", True)

            # Send stop
            await ws.send(json.dumps({"type": "stop"}))
            report("Stop sent", True)

            # Connection should close cleanly
            try:
                # Drain any remaining messages
                while True:
                    raw = await asyncio.wait_for(ws.recv(), timeout=3)
                    data = json.loads(raw)
                    if data.get("type") == "error":
                        report("No error on stop", False, data.get("content", ""))
                        return
            except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
                pass

            report("Clean shutdown", True)

    except Exception as e:
        report("Graceful stop", False, str(e))


async def test_bad_start_message():
    """T7: Server rejects non-start first message."""
    print("\n── T7: Bad Start Message ──")
    try:
        async with websockets.connect(WS_URL, open_timeout=10) as ws:
            await ws.send(json.dumps({"type": "audio", "data": "AAAA"}))
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            is_error = (msg.get("type") == "error"
                        and "start" in msg.get("content", "").lower())
            report("Rejects non-start message", is_error,
                   f"type={msg.get('type')}, content={msg.get('content', '')[:50]}")
    except websockets.exceptions.ConnectionClosed:
        report("Rejects non-start message", True, "connection closed")
    except Exception as e:
        report("Rejects non-start message", False, str(e))


async def main():
    parser = argparse.ArgumentParser(description="Test Live Session")
    parser.add_argument("--quick", action="store_true", help="Connectivity tests only")
    parser.add_argument("--image-only", action="store_true", help="Image generation only")
    args = parser.parse_args()

    print("=" * 60)
    print("  Live Session Test Suite")
    print("=" * 60)

    if args.image_only:
        await test_image_generation()
    elif args.quick:
        await test_health()
        await test_ws_connect_and_start()
        await test_bad_start_message()
    else:
        await test_health()
        await test_ws_connect_and_start()
        await test_bad_start_message()
        await test_graceful_stop()
        await test_ws_keepalive()
        await test_ws_audio_round_trip()
        await test_image_generation()

    # Summary
    print("\n" + "=" * 60)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    print(f"  Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed:
        print(f"\n  {FAIL} Failed tests:")
        for name, ok, detail in results:
            if not ok:
                print(f"    - {name}: {detail}")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
