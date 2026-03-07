"""LLM provider diagnostics for ChronoCanvas.

Run inside the worker container:
    docker exec chrono-canvas-worker-1 python /app/scripts/test_llm_diagnostics.py [COMMAND]

Commands:
    availability   Check which providers are reachable
    routing        Test RuntimeConfig provider routing (local vs gcp vs none)
    providers      Send a test prompt to each provider
    gemini-json    Test Gemini JSON mode edge cases
    scene-prompt   Test a realistic scene prompt generation call
    anchor-prompt  Test character anchor generation call
    request <ID>   Inspect LLM calls for a specific request
    all            Run all checks (except request)
"""

import asyncio
import json
import sys
import time


def _header(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


async def check_availability() -> None:
    _header("Provider Availability")
    from chronocanvas.llm.router import get_llm_router

    router = get_llm_router()
    avail = await router.check_availability()
    for name, ok in sorted(avail.items()):
        status = "OK" if ok else "UNAVAILABLE"
        print(f"  {name:12s} {status}")


async def check_routing() -> None:
    _header("RuntimeConfig Provider Routing")
    from chronocanvas.llm.base import TaskType
    from chronocanvas.llm.router import get_llm_router
    from chronocanvas.runtime_config import RuntimeConfig

    router = get_llm_router()

    cases = [
        ("local mode (ollama)", {"mode": "local", "llm": {"provider": "ollama", "model": "llama3.2"}}),
        ("gcp mode (gemini)", {"mode": "gcp", "llm": {"provider": "gemini", "model": "gemini-2.5-flash"}}),
        ("no config (None)", None),
    ]
    for label, payload in cases:
        rc = RuntimeConfig.from_request_payload(payload)
        provider = router.get_provider(TaskType.PROMPT_GENERATION, runtime_config=rc)
        print(f"  {label:30s} -> {provider.name}")

    from chronocanvas.config import settings
    print(f"\n  DEPLOYMENT_MODE = {settings.deployment_mode}")
    print(f"  OLLAMA_BASE_URL = {settings.ollama_base_url}")
    print(f"  GEMINI_MODEL    = {settings.gemini_model}")


async def test_providers() -> None:
    _header("Direct Provider Test (JSON mode)")
    from chronocanvas.llm.base import TaskType
    from chronocanvas.llm.router import get_llm_router

    router = get_llm_router()
    prompt = 'Return valid JSON: {"status": "ok", "provider": "unknown"}'

    for name in ["ollama", "gemini", "claude"]:
        t0 = time.perf_counter()
        try:
            resp = await asyncio.wait_for(
                router.generate(
                    prompt=prompt,
                    task_type=TaskType.GENERAL,
                    max_tokens=100,
                    json_mode=True,
                    provider_override=name,
                ),
                timeout=30,
            )
            elapsed = (time.perf_counter() - t0) * 1000
            empty = " ** EMPTY **" if not resp.content.strip() else ""
            print(f"  {name:12s} model={resp.model:25s} {elapsed:7.0f}ms  content={resp.content[:80]!r}{empty}")
        except asyncio.TimeoutError:
            print(f"  {name:12s} TIMEOUT (30s)")
        except Exception as e:
            print(f"  {name:12s} ERROR: {type(e).__name__}: {e}")


async def test_gemini_json() -> None:
    _header("Gemini JSON Mode Edge Cases")
    from google import genai
    from google.genai import types

    from chronocanvas.config import settings

    client = genai.Client(api_key=settings.google_api_key)
    config = types.GenerateContentConfig(
        temperature=0.3,
        max_output_tokens=500,
        response_mime_type="application/json",
    )

    cases = [
        ("simple json", 'Return JSON: {"ok": true}'),
        ("json array", 'Return a JSON array with 2 items: [{"id": 1}, {"id": 2}]'),
        (
            "character anchor",
            'Given character Goldilocks (age 8, female), produce a Visual Anchor.\n'
            'Output ONLY valid JSON: [{"name": "Goldilocks", "visual_anchor": "description"}]',
        ),
    ]

    for label, prompt in cases:
        t0 = time.perf_counter()
        try:
            resp = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=settings.gemini_model, contents=prompt, config=config,
                ),
                timeout=30,
            )
            elapsed = (time.perf_counter() - t0) * 1000
            text = resp.text or ""
            empty = " ** EMPTY **" if not text.strip() else ""
            finish = resp.candidates[0].finish_reason if resp.candidates else "no_candidates"
            tokens = f"in={resp.usage_metadata.prompt_token_count} out={resp.usage_metadata.candidates_token_count}"
            print(f"  {label:20s} {elapsed:7.0f}ms  finish={finish}  {tokens}  {empty}")
            if text.strip():
                print(f"    content={text[:120]!r}")
            else:
                print(f"    !! Empty response — content filter or model issue")
        except asyncio.TimeoutError:
            print(f"  {label:20s} TIMEOUT (30s)")
        except Exception as e:
            print(f"  {label:20s} ERROR: {type(e).__name__}: {e}")


async def test_scene_prompt() -> None:
    _header("Scene Prompt Generation (realistic)")
    from chronocanvas.llm.base import TaskType
    from chronocanvas.llm.router import get_llm_router

    router = get_llm_router()
    prompt = (
        "You are an expert at writing image generation prompts for Google Imagen.\n"
        "Generate a vivid, detailed prompt for the following scene from a story.\n\n"
        "SCENE DESCRIPTION: A young girl discovers a cozy cottage in the forest\n"
        "CHARACTERS IN SCENE: Goldilocks\n"
        "MOOD: curious, adventurous\n"
        "SETTING: Deep forest clearing with a thatched-roof cottage\n\n"
        "CHARACTER VISUAL ANCHORS:\n"
        "- Goldilocks: (no details available)\n\n"
        "Requirements:\n"
        "- Write in natural, descriptive prose\n"
        "- Write 100-200 words\n"
        "- Specify camera setup, lighting, environment\n\n"
        'Output ONLY valid JSON:\n'
        '{"image_prompt": "the detailed positive prompt...", '
        '"negative_prompt": "low quality, blurry..."}'
    )

    t0 = time.perf_counter()
    try:
        resp = await asyncio.wait_for(
            router.generate(
                prompt=prompt,
                task_type=TaskType.PROMPT_GENERATION,
                temperature=0.7,
                max_tokens=4000,
                json_mode=True,
                agent_name="scene_prompt_generation",
            ),
            timeout=60,
        )
        elapsed = (time.perf_counter() - t0) * 1000
        empty = " ** EMPTY **" if not resp.content.strip() else ""
        print(f"  provider={resp.provider}  model={resp.model}  {elapsed:.0f}ms")
        print(f"  tokens: in={resp.input_tokens} out={resp.output_tokens}")
        if resp.content.strip():
            # Try to parse the JSON
            try:
                content = resp.content
                parsed = json.loads(content[content.find("{"):content.rfind("}") + 1])
                print(f"  image_prompt: {parsed.get('image_prompt', '')[:120]}...")
                print(f"  negative_prompt: {parsed.get('negative_prompt', '')[:80]}")
                print("  PASS: Valid JSON response")
            except (json.JSONDecodeError, ValueError) as e:
                print(f"  FAIL: JSON parse error: {e}")
                print(f"  raw: {resp.content[:200]!r}")
        else:
            print(f"  FAIL: Empty response{empty}")
    except asyncio.TimeoutError:
        print("  FAIL: TIMEOUT (60s)")
    except Exception as e:
        print(f"  FAIL: {type(e).__name__}: {e}")


async def test_anchor_prompt() -> None:
    _header("Character Anchor Generation (realistic)")
    from chronocanvas.llm.base import TaskType
    from chronocanvas.llm.router import get_llm_router

    router = get_llm_router()
    char_json = json.dumps(
        [
            {"name": "Goldilocks", "age": "8", "gender": "female"},
            {"name": "Papa Bear", "age": "adult", "gender": "male", "ethnicity": "brown bear"},
        ],
        indent=2,
    )
    prompt = (
        "You are a character design consultant for a visual storyboard. "
        "Given the character data below, produce a canonical Visual Anchor for each character.\n\n"
        f"CHARACTERS:\n{char_json}\n\n"
        "Output ONLY valid JSON — a list of objects:\n"
        '[{"name": "CharName", "visual_anchor": "2-3 sentence description..."}]'
    )

    t0 = time.perf_counter()
    try:
        resp = await asyncio.wait_for(
            router.generate(
                prompt=prompt,
                task_type=TaskType.PROMPT_GENERATION,
                temperature=0.3,
                max_tokens=4000,
                json_mode=True,
                agent_name="character_anchor_generation",
            ),
            timeout=60,
        )
        elapsed = (time.perf_counter() - t0) * 1000
        print(f"  provider={resp.provider}  model={resp.model}  {elapsed:.0f}ms")
        print(f"  tokens: in={resp.input_tokens} out={resp.output_tokens}")
        if resp.content.strip():
            try:
                content = resp.content
                anchors = json.loads(content[content.find("["):content.rfind("]") + 1])
                for a in anchors:
                    print(f"  {a['name']}: {a['visual_anchor'][:100]}...")
                print("  PASS: Valid JSON response")
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                print(f"  FAIL: Parse error: {e}")
                print(f"  raw: {resp.content[:200]!r}")
        else:
            print("  FAIL: Empty response")
    except asyncio.TimeoutError:
        print("  FAIL: TIMEOUT (60s)")
    except Exception as e:
        print(f"  FAIL: {type(e).__name__}: {e}")


async def inspect_request(request_id: str) -> None:
    _header(f"Request LLM Calls: {request_id}")
    from chronocanvas.db.engine import async_session
    from chronocanvas.db.repositories.requests import RequestRepository

    async with async_session() as session:
        repo = RequestRepository(session)
        req = await repo.get(request_id)
        if not req:
            print(f"  Request {request_id} not found")
            return

        print(f"  status: {req.status}")
        print(f"  current_agent: {req.current_agent}")
        print(f"  run_type: {req.run_type}")
        print(f"  error: {req.error_message or '(none)'}")
        print(f"  created: {req.created_at}")
        print(f"  updated: {req.updated_at}")

        calls = req.llm_calls or []
        if not calls:
            print("\n  No LLM calls recorded")
        else:
            print(f"\n  LLM Calls ({len(calls)}):")
            total_cost = 0.0
            for i, call in enumerate(calls):
                cost = call.get("cost", 0.0)
                total_cost += cost
                out_tok = call.get("output_tokens", 0)
                warn = " ** 0 output tokens! **" if out_tok == 0 else ""
                empty_warn = ""
                raw = call.get("raw_response", "")
                if isinstance(raw, str) and not raw.strip():
                    empty_warn = " ** EMPTY RESPONSE **"
                print(
                    f"    {i}: agent={call.get('agent'):30s} "
                    f"provider={call.get('provider'):8s} "
                    f"model={call.get('model', 'n/a'):25s} "
                    f"in={call.get('input_tokens', 0):5d} "
                    f"out={out_tok:5d} "
                    f"cost=${cost:.6f} "
                    f"req={call.get('requested_provider', 'n/a')} "
                    f"fallback={call.get('fallback', False)}"
                    f"{warn}{empty_warn}"
                )
            print(f"\n  Total cost: ${total_cost:.6f}")

        costs = req.llm_costs
        if costs:
            print(f"\n  Aggregated costs: {json.dumps(costs, indent=4)}")


async def run_all() -> None:
    await check_availability()
    await check_routing()
    await test_providers()
    await test_gemini_json()
    await test_anchor_prompt()
    await test_scene_prompt()


COMMANDS = {
    "availability": check_availability,
    "routing": check_routing,
    "providers": test_providers,
    "gemini-json": test_gemini_json,
    "scene-prompt": test_scene_prompt,
    "anchor-prompt": test_anchor_prompt,
    "all": run_all,
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(__doc__)
        print("Available commands:", ", ".join(sorted(COMMANDS.keys())) + ", request <ID>")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "request":
        if len(sys.argv) < 3:
            print("Usage: test_llm_diagnostics.py request <REQUEST_ID>")
            sys.exit(1)
        asyncio.run(inspect_request(sys.argv[2]))
    elif cmd in COMMANDS:
        asyncio.run(COMMANDS[cmd]())
    else:
        print(f"Unknown command: {cmd}")
        print("Available commands:", ", ".join(sorted(COMMANDS.keys())) + ", request <ID>")
        sys.exit(1)


if __name__ == "__main__":
    main()
