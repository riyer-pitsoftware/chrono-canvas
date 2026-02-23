#!/usr/bin/env python3
"""Run evaluation cases under specified conditions.

Usage:
    # Single case, single condition
    python eval/scripts/run_eval.py --cases CCV1-001 --conditions D

    # Multiple cases and conditions
    python eval/scripts/run_eval.py --cases CCV1-001,CCV1-002 --conditions A,D

    # All cases, two conditions
    python eval/scripts/run_eval.py --cases all --conditions A,D --seed 42

    # Dry run (print plan without executing)
    python eval/scripts/run_eval.py --cases all --conditions A,D --dry-run

Conditions A/B use direct_comfyui.py (standalone ComfyUI generation).
Conditions C/D use the ChronoCanvas API (POST /api/generate, then poll).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import yaml

logger = logging.getLogger(__name__)

EVAL_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = EVAL_ROOT.parent
SCRIPTS_DIR = EVAL_ROOT / "scripts"

# How long to wait for the pipeline to complete (seconds)
PIPELINE_POLL_TIMEOUT = 600
PIPELINE_POLL_INTERVAL = 2

TERMINAL_STATUSES = {"completed", "failed"}


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            text=True,
        ).strip()
    except Exception:
        return "unknown"


def load_cases() -> list[dict]:
    cases_path = EVAL_ROOT / "evalset" / "cases.yaml"
    if not cases_path.exists():
        print(f"Error: {cases_path} not found", file=sys.stderr)
        sys.exit(1)
    with open(cases_path) as f:
        data = yaml.safe_load(f)
    return data.get("cases", [])


def load_condition_config(condition: str) -> dict:
    config_path = EVAL_ROOT / "configs" / f"baseline{condition}.yaml"
    if not config_path.exists():
        print(f"Error: {config_path} not found", file=sys.stderr)
        sys.exit(1)
    with open(config_path) as f:
        return yaml.safe_load(f) or {}


def resolve_cases(cases: list[dict], case_spec: str) -> list[dict]:
    if case_spec == "all":
        return cases
    ids = [c.strip() for c in case_spec.split(",")]
    case_map = {c["id"]: c for c in cases}
    resolved = []
    for cid in ids:
        if cid not in case_map:
            print(f"Error: case {cid} not found in cases.yaml", file=sys.stderr)
            sys.exit(1)
        resolved.append(case_map[cid])
    return resolved


def make_run_id(case_id: str, condition: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    return f"{ts}_{case_id}_baseline{condition}"


# ── Direct execution (Baselines A/B) ────────────────────────────────────────

async def run_direct(
    case: dict,
    condition: str,
    seed: int,
    config: dict,
    dry_run: bool,
    comfyui_url: str,
) -> dict | None:
    """Run a direct ComfyUI generation via direct_comfyui.py subprocess."""
    # We import and call the module directly instead of subprocess to share
    # the async loop and get structured results.
    # Import here to avoid top-level dependency on direct_comfyui internals.
    sys.path.insert(0, str(SCRIPTS_DIR))
    from direct_comfyui import (
        DEFAULT_NEGATIVE,
        build_improved_prompt,
        build_manifest,
        build_minimal_prompt,
        build_sdxl_workflow,
        submit_and_download,
    )

    case_id = case["id"]
    run_id = make_run_id(case_id, condition)
    run_dir = EVAL_ROOT / "runs" / run_id

    prompt = build_minimal_prompt(case) if condition == "A" else build_improved_prompt(case)

    img_config = config.get("image_generation", {})
    checkpoint = img_config.get("checkpoint", "juggernautXL_v9.safetensors")
    width = img_config.get("width", 768)
    height = img_config.get("height", 1024)

    print(f"  [{case_id}] Baseline {condition} (direct) — {case['title'][:50]}")

    if dry_run:
        print(f"    [DRY RUN] prompt: {prompt[:80]}...")
        return None

    run_dir.mkdir(parents=True, exist_ok=True)
    output_path = run_dir / "output.png"

    try:
        latency_ms = await submit_and_download(
            comfyui_url,
            build_sdxl_workflow(prompt, DEFAULT_NEGATIVE, width, height, seed, checkpoint),
            output_path,
        )
    except Exception as e:
        logger.error("Direct generation failed for %s: %s", case_id, e)
        manifest = {
            "run_id": run_id,
            "eval_version": "chronocanvas-evalset-v1",
            "case_id": case_id,
            "condition": f"baseline{condition}",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "git_commit": get_git_commit(),
            "success": False,
            "terminal_state": "provider_error",
            "error_message": str(e),
        }
        (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2))
        print(f"    FAILED: {e}")
        return manifest

    manifest = build_manifest(
        run_id=run_id,
        case_id=case_id,
        condition=condition,
        seed=seed,
        checkpoint=checkpoint,
        comfyui_url=comfyui_url,
        latency_ms=latency_ms,
        prompt_used=prompt,
    )
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2))
    (run_dir / "output_text.md").write_text(
        f"# Baseline {condition} — {case['title']}\n\n**Prompt:** {prompt}\n"
    )

    print(f"    OK — {latency_ms:.0f}ms — {run_dir.name}")
    return manifest


# ── Pipeline execution (Baselines C/D) ──────────────────────────────────────

async def run_pipeline(
    case: dict,
    condition: str,
    seed: int,
    config: dict,
    dry_run: bool,
    api_url: str,
) -> dict | None:
    """Run a case through the ChronoCanvas API and collect artifacts."""
    case_id = case["id"]
    run_id = make_run_id(case_id, condition)
    run_dir = EVAL_ROOT / "runs" / run_id

    print(f"  [{case_id}] Baseline {condition} (pipeline) — {case['title'][:50]}")

    if dry_run:
        print(f"    [DRY RUN] POST {api_url}/api/generate")
        return None

    run_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()

    async with httpx.AsyncClient(timeout=PIPELINE_POLL_TIMEOUT) as client:
        # 1. Start generation
        try:
            resp = await client.post(
                f"{api_url}/api/generate",
                json={"input_text": case["prompt_brief"].strip()},
            )
            resp.raise_for_status()
            gen = resp.json()
            request_id = gen["id"]
        except Exception as e:
            logger.error("Pipeline start failed for %s: %s", case_id, e)
            manifest = _error_manifest(run_id, case_id, condition, str(e))
            (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2))
            print(f"    FAILED to start: {e}")
            return manifest

        # 2. Poll until terminal status
        elapsed = 0.0
        final = gen
        while elapsed < PIPELINE_POLL_TIMEOUT:
            await asyncio.sleep(PIPELINE_POLL_INTERVAL)
            elapsed += PIPELINE_POLL_INTERVAL
            try:
                resp = await client.get(f"{api_url}/api/generate/{request_id}")
                resp.raise_for_status()
                final = resp.json()
            except Exception as e:
                logger.warning("Poll error for %s: %s", request_id, e)
                continue

            if final.get("status") in TERMINAL_STATUSES:
                break

        latency_ms = (time.monotonic() - t0) * 1000
        success = final.get("status") == "completed"

        # 3. Fetch audit trail
        audit = {}
        try:
            resp = await client.get(f"{api_url}/api/generate/{request_id}/audit")
            resp.raise_for_status()
            audit = resp.json()
        except Exception as e:
            logger.warning("Audit fetch failed for %s: %s", request_id, e)

        # 4. Fetch images and download the first one
        images = []
        try:
            resp = await client.get(f"{api_url}/api/generate/{request_id}/images")
            resp.raise_for_status()
            images = resp.json()
        except Exception as e:
            logger.warning("Images fetch failed for %s: %s", request_id, e)

        if images:
            img = images[0]
            file_path = img.get("file_path", "")
            filename = file_path.split("/")[-1] if file_path else ""
            if filename:
                try:
                    img_resp = await client.get(
                        f"{api_url}/output/{request_id}/{filename}"
                    )
                    img_resp.raise_for_status()
                    (run_dir / "output.png").write_bytes(img_resp.content)
                except Exception as e:
                    logger.warning("Image download failed for %s: %s", request_id, e)

        # 5. Save artifacts
        (run_dir / "audit_trace.json").write_text(json.dumps(audit, indent=2, default=str))

        # Build output_text.md from generation data
        text_parts = [f"# Baseline {condition} — {case['title']}\n"]
        if final.get("generated_prompt"):
            text_parts.append(f"**Generated Prompt:** {final['generated_prompt']}\n")
        if final.get("research_data"):
            text_parts.append(f"**Research Data:** {json.dumps(final['research_data'], indent=2)}\n")
        (run_dir / "output_text.md").write_text("\n".join(text_parts))

        # 6. Build manifest
        llm_costs = audit.get("llm_costs") or final.get("llm_costs") or {}
        llm_calls = audit.get("llm_calls") or final.get("llm_calls") or []
        token_input = sum(c.get("input_tokens", 0) for c in llm_calls)
        token_output = sum(c.get("output_tokens", 0) for c in llm_calls)
        total_cost = sum(c.get("cost", 0) or 0 for c in llm_calls)

        agent_trace = audit.get("agent_trace") or final.get("agent_trace") or []
        retry_count = sum(1 for t in agent_trace if t.get("agent") == "validation" and not t.get("passed", True))

        pipeline_cfg = config.get("pipeline", {})
        manifest = {
            "run_id": run_id,
            "eval_version": "chronocanvas-evalset-v1",
            "case_id": case_id,
            "condition": config.get("condition", f"baseline{condition}"),
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "git_commit": get_git_commit(),
            "app_version": "0.1.0",
            "config_profile": f"eval-baseline{condition}",
            "llm_provider": config.get("llm", {}).get("provider"),
            "llm_model": config.get("llm", {}).get("model"),
            "image_provider": config.get("image_generation", {}).get("provider", "comfyui"),
            "image_model": config.get("image_generation", {}).get("checkpoint"),
            "face_pipeline_enabled": pipeline_cfg.get("facefusion_enabled", False),
            "face_search_enabled": pipeline_cfg.get("face_search_enabled", False),
            "validation_retry_enabled": pipeline_cfg.get("validation_retry_enabled", False),
            "max_retries": pipeline_cfg.get("max_retries", 0),
            "seed": seed,
            "prompt_used": final.get("generated_prompt", ""),
            "success": success,
            "terminal_state": final.get("status", "unknown"),
            "total_latency_ms": round(latency_ms, 1),
            "token_input_count": token_input,
            "token_output_count": token_output,
            "llm_cost_usd": total_cost,
            "image_cost_usd": 0.0,
            "total_cost_usd": total_cost,
            "total_retries": retry_count,
            "audit_event_count": len(agent_trace),
            "trace_complete": bool(agent_trace),
            "error_message": final.get("error_message"),
            "runtime_env": {
                "api_url": api_url,
            },
        }
        (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2))

        status_icon = "OK" if success else "FAILED"
        print(f"    {status_icon} — {latency_ms:.0f}ms — {run_dir.name}")
        return manifest


def _error_manifest(run_id: str, case_id: str, condition: str, error: str) -> dict:
    return {
        "run_id": run_id,
        "eval_version": "chronocanvas-evalset-v1",
        "case_id": case_id,
        "condition": f"baseline{condition}",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "success": False,
        "terminal_state": "provider_error",
        "error_message": error,
    }


# ── Main ─────────────────────────────────────────────────────────────────────

async def async_main(args: argparse.Namespace) -> None:
    all_cases = load_cases()
    if not all_cases:
        print("Error: no cases found in cases.yaml", file=sys.stderr)
        sys.exit(1)

    target_cases = resolve_cases(all_cases, args.cases)
    conditions = [c.strip() for c in args.conditions.split(",")]

    results: list[dict] = []

    for condition in conditions:
        config = load_condition_config(condition)
        mode = config.get("mode", "pipeline")

        print(f"\n{'='*60}")
        print(f"Condition: Baseline {condition} ({mode})")
        print(f"Cases:     {len(target_cases)}")
        print(f"{'='*60}")

        for case in target_cases:
            seed = args.seed if args.seed is not None else case.get("seed_recommendation", 42)

            if mode == "direct":
                manifest = await run_direct(
                    case=case,
                    condition=condition,
                    seed=seed,
                    config=config,
                    dry_run=args.dry_run,
                    comfyui_url=args.comfyui_url,
                )
            else:
                manifest = await run_pipeline(
                    case=case,
                    condition=condition,
                    seed=seed,
                    config=config,
                    dry_run=args.dry_run,
                    api_url=args.api_url,
                )

            if manifest:
                results.append(manifest)

    # Summary
    if results:
        succeeded = sum(1 for r in results if r.get("success"))
        failed = len(results) - succeeded
        print(f"\n{'─'*60}")
        print(f"Summary: {succeeded} succeeded, {failed} failed, {len(results)} total")


def main():
    parser = argparse.ArgumentParser(
        description="ChronoCanvas eval runner — execute cases across conditions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --cases CCV1-001 --conditions D
  %(prog)s --cases CCV1-001,CCV1-002 --conditions A,D
  %(prog)s --cases all --conditions A,D --seed 42
  %(prog)s --cases all --conditions A,B,C,D --dry-run
""",
    )
    parser.add_argument(
        "--cases",
        required=True,
        help="Comma-separated case IDs or 'all'",
    )
    parser.add_argument(
        "--conditions",
        required=True,
        help="Comma-separated conditions (A, B, C, D)",
    )
    parser.add_argument("--seed", type=int, help="Override seed for all runs")
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="ChronoCanvas API URL for pipeline conditions (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--comfyui-url",
        default="http://localhost:8188",
        help="ComfyUI API URL for direct conditions (default: http://localhost:8188)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print plan without executing",
    )

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
