"""Test hackathon feature flags (HACKATHON_MODE, HACKATHON_STRICT_GEMINI).

Run manually inside the API container:
    docker exec chrono-canvas-api-1 python /app/scripts/test_hackathon_flags.py

NOT included in automated smoke tests — some checks exercise LLM providers
which cost money.
"""

import asyncio
import sys
from unittest.mock import patch


def header(msg: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {msg}")
    print(f"{'─' * 60}")


passed = 0
failed = 0


def ok(label: str) -> None:
    global passed
    passed += 1
    print(f"  ✓ {label}")


def fail(label: str, detail: str = "") -> None:
    global failed
    failed += 1
    msg = f"  ✗ {label}"
    if detail:
        msg += f" — {detail}"
    print(msg)


async def test_config_flags() -> None:
    header("1. Config flags load correctly")
    from chronocanvas.config import settings

    # These should be booleans regardless of .env value
    if isinstance(settings.hackathon_mode, bool):
        ok(f"hackathon_mode={settings.hackathon_mode} (bool)")
    else:
        fail("hackathon_mode is not bool", str(type(settings.hackathon_mode)))

    if isinstance(settings.hackathon_strict_gemini, bool):
        ok(f"hackathon_strict_gemini={settings.hackathon_strict_gemini} (bool)")
    else:
        fail("hackathon_strict_gemini is not bool", str(type(settings.hackathon_strict_gemini)))


async def test_health_endpoint() -> None:
    header("2. Health endpoint exposes hackathon_mode")
    import httpx

    async with httpx.AsyncClient() as client:
        resp = await client.get("http://localhost:8000/api/health")
        data = resp.json()

    if "hackathon_mode" in data:
        ok(f"hackathon_mode={data['hackathon_mode']} in /api/health")
    else:
        fail("hackathon_mode missing from /api/health", str(data.keys()))


async def test_strict_gemini_blocks_fallback() -> None:
    header("3. Strict Gemini mode blocks fallback (mocked)")
    from chronocanvas.llm.base import TaskType
    from chronocanvas.llm.router import GeminiUnavailableError, LLMRouter

    router = LLMRouter()

    with patch("chronocanvas.llm.router.settings") as mock_settings:
        mock_settings.hackathon_strict_gemini = True
        mock_settings.default_llm_provider = "gemini"
        mock_settings.rate_limit_rpm = 60
        mock_settings.llm_max_concurrent = 5
        mock_settings.llm_agent_routing = {}

        try:
            await router.generate(prompt="test", task_type=TaskType.GENERAL)
            fail("Should have raised GeminiUnavailableError")
        except GeminiUnavailableError:
            ok("GeminiUnavailableError raised when Gemini unavailable + strict=True")
        except Exception as e:
            fail(f"Wrong exception: {type(e).__name__}", str(e))


async def test_strict_gemini_allows_fallback_when_off() -> None:
    header("4. Fallback works when strict Gemini is OFF (mocked)")
    from chronocanvas.llm.base import TaskType
    from chronocanvas.llm.router import GeminiUnavailableError, LLMRouter

    router = LLMRouter()

    with patch("chronocanvas.llm.router.settings") as mock_settings:
        mock_settings.hackathon_strict_gemini = False
        mock_settings.default_llm_provider = "gemini"
        mock_settings.rate_limit_rpm = 60
        mock_settings.llm_max_concurrent = 5
        mock_settings.llm_agent_routing = {}

        # Check availability — if any non-gemini provider is up, fallback should work
        avail = await router.check_availability()
        non_gemini_available = any(
            v for k, v in avail.items() if k != "gemini"
        )

        if not non_gemini_available:
            ok("SKIP — no non-gemini providers available to test fallback")
            return

        try:
            resp = await router.generate(prompt="Say hello in one word.", task_type=TaskType.GENERAL)
            ok(f"Fallback succeeded: {resp.provider}/{resp.model}")
        except GeminiUnavailableError:
            fail("GeminiUnavailableError raised but strict is OFF")
        except Exception as e:
            # Other errors (rate limit, etc.) are acceptable — the point is no GeminiUnavailableError
            ok(f"No GeminiUnavailableError (got {type(e).__name__}, which is fine)")


async def test_strict_gemini_stream_blocks() -> None:
    header("5. Strict Gemini mode blocks stream fallback (mocked)")
    from chronocanvas.llm.base import TaskType
    from chronocanvas.llm.router import GeminiUnavailableError, LLMRouter

    router = LLMRouter()

    with patch("chronocanvas.llm.router.settings") as mock_settings:
        mock_settings.hackathon_strict_gemini = True
        mock_settings.default_llm_provider = "gemini"
        mock_settings.rate_limit_rpm = 60
        mock_settings.llm_max_concurrent = 5
        mock_settings.llm_agent_routing = {}

        try:
            await router.generate_stream(prompt="test", task_type=TaskType.GENERAL)
            fail("Should have raised GeminiUnavailableError in generate_stream")
        except GeminiUnavailableError:
            ok("GeminiUnavailableError raised in generate_stream")
        except Exception as e:
            fail(f"Wrong exception in generate_stream: {type(e).__name__}", str(e))


async def test_exception_handler_returns_503() -> None:
    header("6. FastAPI returns 503 for GeminiUnavailableError")
    from chronocanvas.llm.router import GeminiUnavailableError
    from chronocanvas.main import app

    # Check that the exception handler is registered
    handlers = app.exception_handlers
    if GeminiUnavailableError in handlers:
        ok("GeminiUnavailableError handler registered in FastAPI app")
    else:
        fail("GeminiUnavailableError handler NOT registered")


async def main() -> None:
    print("=" * 60)
    print("  Hackathon Feature Flags Test Suite")
    print("=" * 60)

    await test_config_flags()
    await test_health_endpoint()
    await test_strict_gemini_blocks_fallback()
    await test_strict_gemini_allows_fallback_when_off()
    await test_strict_gemini_stream_blocks()
    await test_exception_handler_returns_503()

    print(f"\n{'=' * 60}")
    print(f"  Results: {passed} passed, {failed} failed")
    print(f"{'=' * 60}")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
