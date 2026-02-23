#!/usr/bin/env python3
"""Generate a portrait via ComfyUI without the ChronoCanvas pipeline.

Covers Baselines A (minimal prompt) and B (human-refined prompt).

Usage:
    python eval/scripts/direct_comfyui.py --case CCV1-001 --condition A
    python eval/scripts/direct_comfyui.py --case CCV1-001 --condition B --seed 12345
    python eval/scripts/direct_comfyui.py --case CCV1-001 --condition A --comfyui-url http://localhost:8188
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import yaml

logger = logging.getLogger(__name__)

EVAL_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = EVAL_ROOT.parent

# ── Prompt templates ─────────────────────────────────────────────────────────

def build_minimal_prompt(case: dict) -> str:
    """Baseline A: bare-minimum prompt from case metadata."""
    title = case["title"]
    period = case.get("time_period_label", "")
    region = case.get("region", "")
    parts = [f"Portrait of {title}"]
    if period:
        parts.append(period)
    if region:
        parts.append(region)
    return ", ".join(parts)


def build_improved_prompt(case: dict) -> str:
    """Baseline B: human-refined prompt with style and era cues."""
    title = case["title"]
    region = case.get("region", "")
    start = case.get("time_period_start", "")
    end = case.get("time_period_end", "")
    period = case.get("time_period_label", "")
    style = ", ".join(case.get("style_guidance", [])) or "illustrative realism"
    setting = case.get("setting_context", "")

    era = f"circa {start}–{end}" if start and end else period

    parts = [
        f"A historically informed oil painting portrait of {title}",
        region,
        era,
    ]
    if setting:
        parts.append(f"in a {setting.lower()} setting")
    parts.append("period-appropriate attire and cultural markers")
    parts.append(style)
    parts.append("detailed face, clear features, dignified composition")

    return ", ".join(p for p in parts if p)


DEFAULT_NEGATIVE = (
    "blurry, low quality, modern clothing, anachronistic elements, "
    "text, watermark, signature, frame, border, cartoon, anime"
)


# ── ComfyUI SDXL workflow (matches comfyui_client.py) ────────────────────────

def build_sdxl_workflow(
    prompt: str,
    negative_prompt: str,
    width: int,
    height: int,
    seed: int,
    checkpoint: str,
) -> dict:
    return {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": checkpoint},
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": ["1", 1]},
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative_prompt, "clip": ["1", 1]},
        },
        "4": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": 30,
                "cfg": 7.0,
                "sampler_name": "dpmpp_2m",
                "scheduler": "karras",
                "denoise": 1.0,
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
            },
        },
        "6": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["5", 0], "vae": ["1", 2]},
        },
        "7": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "chronocanvas_eval", "images": ["6", 0]},
        },
    }


# ── ComfyUI interaction ──────────────────────────────────────────────────────

async def submit_and_download(
    comfyui_url: str,
    workflow: dict,
    output_path: Path,
    timeout: float = 600.0,
) -> float:
    """Submit workflow to ComfyUI, poll for completion, download image.

    Returns latency in milliseconds.
    """
    t0 = time.monotonic()
    async with httpx.AsyncClient(timeout=timeout) as client:
        # Submit
        resp = await client.post(f"{comfyui_url}/prompt", json={"prompt": workflow})
        resp.raise_for_status()
        prompt_id = resp.json()["prompt_id"]

        # Poll
        interval = 1.0
        elapsed = 0.0
        while elapsed < timeout:
            resp = await client.get(f"{comfyui_url}/history/{prompt_id}")
            resp.raise_for_status()
            history = resp.json()

            if prompt_id in history:
                outputs = history[prompt_id].get("outputs", {})
                for node_output in outputs.values():
                    images = node_output.get("images", [])
                    if images:
                        img = images[0]
                        img_resp = await client.get(
                            f"{comfyui_url}/view",
                            params={
                                "filename": img["filename"],
                                "subfolder": img.get("subfolder", ""),
                                "type": img.get("type", "output"),
                            },
                        )
                        img_resp.raise_for_status()
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        output_path.write_bytes(img_resp.content)
                        latency_ms = (time.monotonic() - t0) * 1000
                        return latency_ms

            await asyncio.sleep(interval)
            elapsed += interval

        raise TimeoutError(f"ComfyUI prompt {prompt_id} did not complete within {timeout}s")


# ── Run manifest ─────────────────────────────────────────────────────────────

def get_git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            text=True,
        ).strip()
    except Exception:
        return "unknown"


def build_manifest(
    run_id: str,
    case_id: str,
    condition: str,
    seed: int,
    checkpoint: str,
    comfyui_url: str,
    latency_ms: float,
    prompt_used: str,
) -> dict:
    return {
        "run_id": run_id,
        "eval_version": "chronocanvas-evalset-v1",
        "case_id": case_id,
        "condition": f"baseline{condition}_{'oneshot_minimal' if condition == 'A' else 'oneshot_improved'}",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "app_version": "0.1.0",
        "config_profile": f"eval-baseline{condition}",
        "llm_provider": None,
        "llm_model": None,
        "image_provider": "comfyui",
        "image_model": checkpoint,
        "face_pipeline_enabled": False,
        "validation_retry_enabled": False,
        "max_retries": 0,
        "seed": seed,
        "prompt_used": prompt_used,
        "total_latency_ms": round(latency_ms, 1),
        "total_cost_usd": 0.0,
        "success": True,
        "terminal_state": "completed",
        "runtime_env": {
            "comfyui_url": comfyui_url,
        },
    }


# ── Main ─────────────────────────────────────────────────────────────────────

def load_cases() -> list[dict]:
    cases_path = EVAL_ROOT / "evalset" / "cases.yaml"
    if not cases_path.exists():
        print(f"Error: {cases_path} not found", file=sys.stderr)
        sys.exit(1)
    with open(cases_path) as f:
        data = yaml.safe_load(f)
    return data.get("cases", [])


def find_case(cases: list[dict], case_id: str) -> dict:
    for c in cases:
        if c["id"] == case_id:
            return c
    print(f"Error: case {case_id} not found in cases.yaml", file=sys.stderr)
    sys.exit(1)


async def run_single(
    case: dict,
    condition: str,
    seed: int,
    comfyui_url: str,
    checkpoint: str,
    width: int,
    height: int,
    dry_run: bool,
) -> str | None:
    """Run a single case. Returns run_id or None if dry-run."""
    case_id = case["id"]

    if condition == "A":
        prompt = build_minimal_prompt(case)
    else:
        prompt = build_improved_prompt(case)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    run_id = f"{ts}_{case_id}_baseline{condition}"
    run_dir = EVAL_ROOT / "runs" / run_id

    print(f"\n{'='*60}")
    print(f"Case:      {case_id} — {case['title']}")
    print(f"Condition: Baseline {condition}")
    print(f"Run ID:    {run_id}")
    print(f"Prompt:    {prompt[:100]}{'...' if len(prompt) > 100 else ''}")
    print(f"Seed:      {seed}")

    if dry_run:
        print("[DRY RUN] Skipping generation")
        return None

    output_path = run_dir / "output.png"
    latency_ms = await submit_and_download(
        comfyui_url,
        build_sdxl_workflow(prompt, DEFAULT_NEGATIVE, width, height, seed, checkpoint),
        output_path,
    )

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
    manifest_path = run_dir / "run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    # Save prompt as output_text.md
    text_path = run_dir / "output_text.md"
    text_path.write_text(f"# Baseline {condition} — {case['title']}\n\n**Prompt:** {prompt}\n")

    print(f"Output:    {output_path}")
    print(f"Latency:   {latency_ms:.0f}ms")
    print(f"Manifest:  {manifest_path}")
    return run_id


async def async_main(args: argparse.Namespace) -> None:
    cases = load_cases()
    if not cases:
        print("Error: no cases found in cases.yaml", file=sys.stderr)
        sys.exit(1)

    # Load condition config for defaults
    config_path = EVAL_ROOT / "configs" / f"baseline{args.condition}.yaml"
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
    else:
        config = {}

    img_config = config.get("image_generation", {})
    checkpoint = args.checkpoint or img_config.get("model", "juggernautXL_v9.safetensors")
    comfyui_url = args.comfyui_url
    width = 768
    height = 1024

    if args.case:
        target_cases = [find_case(cases, args.case)]
    else:
        target_cases = cases

    run_ids = []
    for case in target_cases:
        seed = args.seed if args.seed is not None else case.get("seed_recommendation", 42)
        run_id = await run_single(
            case=case,
            condition=args.condition,
            seed=seed,
            comfyui_url=comfyui_url,
            checkpoint=checkpoint,
            width=width,
            height=height,
            dry_run=args.dry_run,
        )
        if run_id:
            run_ids.append(run_id)

    if run_ids:
        print(f"\nCompleted {len(run_ids)} run(s)")


def main():
    parser = argparse.ArgumentParser(
        description="Direct ComfyUI generation for eval baselines A/B"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--case", help="Case ID to run (e.g., CCV1-001)")
    group.add_argument("--all", action="store_true", help="Run all cases")
    parser.add_argument(
        "--condition",
        required=True,
        choices=["A", "B"],
        help="Baseline condition (A=minimal, B=improved)",
    )
    parser.add_argument("--seed", type=int, help="Override seed for reproducibility")
    parser.add_argument(
        "--comfyui-url",
        default="http://localhost:8188",
        help="ComfyUI API URL (default: http://localhost:8188)",
    )
    parser.add_argument(
        "--checkpoint",
        help="SDXL checkpoint filename (default: from config)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be run without executing",
    )

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
