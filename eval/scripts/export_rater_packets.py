#!/usr/bin/env python3
"""Export rater-friendly scoring packets from completed eval runs.

Usage:
    python eval/scripts/export_rater_packets.py \\
        --runs-dir eval/runs \\
        --output-dir eval/ratings/packets

    # Blind condition labels and randomize order:
    python eval/scripts/export_rater_packets.py \\
        --runs-dir eval/runs \\
        --output-dir eval/ratings/packets \\
        --blind --randomize

    # Filter to specific cases or conditions:
    python eval/scripts/export_rater_packets.py \\
        --runs-dir eval/runs \\
        --output-dir eval/ratings/packets \\
        --case CCV1-001 --condition A

Produces:
  packets/
    index.html              — gallery of all runs with inline scoring forms
    ratings_template.csv    — pre-filled CSV template for scoring
    <run_id>/
      context.md            — case constraints + audit summary
      output.png            — symlink/copy of generated image
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import shutil
import string
import sys
from pathlib import Path

EVAL_ROOT = Path(__file__).resolve().parent.parent
CASES_PATH = EVAL_ROOT / "evalset" / "cases.yaml"
RUBRIC_PATH = EVAL_ROOT / "evalset" / "rubric.md"
RATINGS_TEMPLATE = EVAL_ROOT / "ratings" / "ratings_template.csv"

SCORE_DIMENSIONS = [
    "prompt_adherence",
    "visual_coherence",
    "face_usability",
    "period_plausibility",
    "anachronism_avoidance",
    "narrative_image_consistency",
    "uncertainty_signaling_quality",
    "audit_trace_completeness",
]

CSV_COLUMNS = [
    "run_id",
    "case_id",
    "rater_id",
    "condition",
    *SCORE_DIMENSIONS,
    "freeform_notes",
    "failure_tags",
]


def load_cases() -> dict[str, dict]:
    import yaml

    with open(CASES_PATH) as f:
        data = yaml.safe_load(f)
    return {c["id"]: c for c in data.get("cases", [])}


def discover_runs(runs_dir: Path) -> list[Path]:
    """Find run directories that have a manifest and output image."""
    runs = []
    for child in sorted(runs_dir.iterdir()):
        if not child.is_dir():
            continue
        if (child / "run_manifest.json").exists():
            runs.append(child)
    return runs


def load_manifest(run_dir: Path) -> dict | None:
    path = run_dir / "run_manifest.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def build_blind_map(conditions: set[str]) -> dict[str, str]:
    """Map real condition labels to blinded IDs."""
    labels = sorted(conditions)
    shuffled = list(range(1, len(labels) + 1))
    random.shuffle(shuffled)
    return {label: f"Condition {n}" for label, n in zip(labels, shuffled)}


def build_context_md(manifest: dict, case: dict | None, condition_label: str) -> str:
    """Build a markdown context file for a rater reviewing this run."""
    lines = [f"# Scoring Packet: {manifest['run_id']}\n"]

    lines.append(f"**Condition:** {condition_label}")
    lines.append(f"**Case:** {manifest.get('case_id', 'unknown')}")
    if case:
        lines.append(f"**Subject:** {case.get('title', 'Unknown')}")
        lines.append(f"**Region:** {case.get('region', 'Unknown')}")
        lines.append(
            f"**Time Period:** {case.get('time_period_label', 'Unknown')} "
            f"({case.get('time_period_start', '?')} to {case.get('time_period_end', '?')})"
        )
        lines.append(f"**Setting:** {case.get('setting_context', 'Unknown')}")
        lines.append(f"**Evidence Level:** {case.get('evidence_level', 'Unknown')}")
    lines.append("")

    # Prompt brief
    if case and case.get("prompt_brief"):
        lines.append("## Prompt Brief\n")
        lines.append(case["prompt_brief"].strip())
        lines.append("")

    # Constraints
    if case:
        if case.get("must_include"):
            lines.append("## Must Include\n")
            for item in case["must_include"]:
                lines.append(f"- {item}")
            lines.append("")

        if case.get("must_not_include"):
            lines.append("## Must NOT Include\n")
            for item in case["must_not_include"]:
                lines.append(f"- {item}")
            lines.append("")

        if case.get("anachronism_watchlist"):
            lines.append("## Anachronism Watchlist\n")
            for item in case["anachronism_watchlist"]:
                lines.append(f"- {item}")
            lines.append("")

        if case.get("uncertainty_notes"):
            lines.append("## Uncertainty Notes\n")
            lines.append(case["uncertainty_notes"].strip())
            lines.append("")

    # Run metadata from manifest
    lines.append("## Run Metadata\n")
    terminal = manifest.get("terminal_state", "unknown")
    lines.append(f"- **Status:** {terminal}")
    if manifest.get("latency_ms") is not None:
        lines.append(f"- **Latency:** {manifest['latency_ms']:.0f} ms")
    if manifest.get("total_cost") is not None:
        lines.append(f"- **Cost:** ${manifest['total_cost']:.4f}")
    if manifest.get("tokens_in") is not None:
        lines.append(f"- **Tokens:** {manifest.get('tokens_in', 0)} in / {manifest.get('tokens_out', 0)} out")
    if manifest.get("retry_count") is not None:
        lines.append(f"- **Retries:** {manifest['retry_count']}")
    if manifest.get("heuristic_pass") is not None:
        heur_status = "PASS" if manifest["heuristic_pass"] else "FAIL"
        lines.append(f"- **Heuristic Check:** {heur_status}")
        if manifest.get("heuristic_failures"):
            for fail in manifest["heuristic_failures"]:
                lines.append(f"  - {fail}")
    lines.append("")

    # Generated text excerpt (if present)
    text_path = Path(manifest.get("_run_dir", "")) / "output_text.md"
    if text_path.exists():
        text = text_path.read_text().strip()
        if text:
            lines.append("## Generated Text\n")
            # Truncate very long text
            if len(text) > 3000:
                text = text[:3000] + "\n\n*[truncated]*"
            lines.append(text)
            lines.append("")

    return "\n".join(lines)


def build_html_gallery(packets: list[dict], output_dir: Path) -> str:
    """Build an HTML gallery page with inline scoring forms."""
    rows_html = []
    for pkt in packets:
        run_id = pkt["run_id"]
        case_id = pkt["case_id"]
        condition = pkt["condition_label"]
        title = pkt.get("title", case_id)

        # Score inputs
        score_inputs = []
        for dim in SCORE_DIMENSIONS:
            label = dim.replace("_", " ").title()
            radios = "".join(
                f'<label><input type="radio" name="{run_id}_{dim}" value="{v}"> {v}</label> '
                for v in range(4)
            )
            score_inputs.append(f'<div class="dim"><span class="dim-label">{label}:</span> {radios}</div>')
        scores_html = "\n".join(score_inputs)

        # Check for image
        img_tag = ""
        for ext in ("png", "jpg", "jpeg", "webp"):
            if (output_dir / run_id / f"output.{ext}").exists():
                img_tag = f'<img src="{run_id}/output.{ext}" alt="Generated portrait" />'
                break

        rows_html.append(f"""
    <div class="packet" id="{run_id}">
      <h2>{title}</h2>
      <p class="meta"><strong>Run:</strong> {run_id} &middot; <strong>Condition:</strong> {condition} &middot; <strong>Case:</strong> {case_id}</p>
      <div class="content">
        <div class="image">{img_tag}</div>
        <div class="scoring">
          <h3>Scores (0-3)</h3>
          {scores_html}
          <div class="dim">
            <span class="dim-label">Notes:</span>
            <textarea name="{run_id}_notes" rows="2" cols="40"></textarea>
          </div>
          <div class="dim">
            <span class="dim-label">Failure Tags:</span>
            <input type="text" name="{run_id}_tags" placeholder="semicolon-separated" size="40" />
          </div>
          <p><a href="{run_id}/context.md" target="_blank">View full context</a></p>
        </div>
      </div>
    </div>""")

    body = "\n".join(rows_html)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>ChronoCanvas Rater Packet</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; background: #f8f9fa; }}
    h1 {{ border-bottom: 2px solid #333; padding-bottom: 8px; }}
    .packet {{ background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 20px; margin-bottom: 24px; }}
    .packet h2 {{ margin-top: 0; color: #2c3e50; }}
    .meta {{ color: #666; font-size: 0.9em; }}
    .content {{ display: flex; gap: 24px; flex-wrap: wrap; }}
    .image {{ flex: 1; min-width: 300px; }}
    .image img {{ max-width: 100%; height: auto; border-radius: 4px; border: 1px solid #eee; }}
    .scoring {{ flex: 1; min-width: 300px; }}
    .dim {{ margin-bottom: 8px; }}
    .dim-label {{ display: inline-block; width: 220px; font-weight: 500; font-size: 0.9em; }}
    .dim label {{ margin-right: 8px; font-size: 0.9em; }}
    textarea, input[type="text"] {{ font-family: inherit; }}
    .toc {{ background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 16px; margin-bottom: 24px; }}
    .toc a {{ text-decoration: none; color: #2980b9; }}
    .toc a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <h1>ChronoCanvas Rater Packet</h1>
  <p>{len(packets)} runs to score. See <a href="https://github.com/your-org/chrono-canvas/blob/main/eval/evalset/rubric.md">rubric</a> and <a href="https://github.com/your-org/chrono-canvas/blob/main/eval/evalset/rater-guide.md">rater guide</a> for scoring instructions.</p>

  <div class="toc">
    <strong>Table of Contents</strong>
    <ul>
      {"".join(f'<li><a href="#{p["run_id"]}">{p.get("title", p["case_id"])} ({p["condition_label"]})</a></li>' for p in packets)}
    </ul>
  </div>

  {body}
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(
        description="Export rater scoring packets from completed eval runs"
    )
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=EVAL_ROOT / "runs",
        help="Directory containing run artifacts (default: eval/runs)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=EVAL_ROOT / "ratings" / "packets",
        help="Output directory for packets (default: eval/ratings/packets)",
    )
    parser.add_argument(
        "--blind",
        action="store_true",
        help="Blind condition labels (replace with 'Condition N')",
    )
    parser.add_argument(
        "--randomize",
        action="store_true",
        help="Randomize presentation order",
    )
    parser.add_argument(
        "--case",
        action="append",
        dest="cases",
        help="Filter to specific case ID(s) (repeatable)",
    )
    parser.add_argument(
        "--condition",
        action="append",
        dest="conditions",
        help="Filter to specific condition(s) (repeatable, e.g. A B C D)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for --blind and --randomize",
    )

    args = parser.parse_args()

    # Load case definitions
    case_map = load_cases()

    # Discover runs
    run_dirs = discover_runs(args.runs_dir)
    if not run_dirs:
        print(f"No completed runs found in {args.runs_dir}")
        sys.exit(1)

    # Load manifests and filter
    entries: list[dict] = []
    for run_dir in run_dirs:
        manifest = load_manifest(run_dir)
        if not manifest:
            continue
        manifest["_run_dir"] = str(run_dir)

        case_id = manifest.get("case_id", "")
        condition = manifest.get("condition", "")

        # Apply filters
        if args.cases and case_id not in args.cases:
            continue
        if args.conditions:
            # Match on condition letter (A/B/C/D) or full label
            cond_letter = condition[0].upper() if condition else ""
            if not any(
                c.upper() == cond_letter or c.upper() == condition.upper()
                for c in args.conditions
            ):
                continue

        # Check for output image
        has_image = any((run_dir / f"output.{ext}").exists() for ext in ("png", "jpg", "jpeg", "webp"))
        if not has_image:
            print(f"  Skipping {run_dir.name}: no output image")
            continue

        entries.append(manifest)

    if not entries:
        print("No runs matched filters.")
        sys.exit(1)

    print(f"Found {len(entries)} runs to export.")

    # Set random seed
    if args.seed is not None:
        random.seed(args.seed)
    elif args.blind or args.randomize:
        random.seed(42)

    # Build blind map
    blind_map: dict[str, str] = {}
    if args.blind:
        all_conditions = {m.get("condition", "unknown") for m in entries}
        blind_map = build_blind_map(all_conditions)
        print(f"  Blinding {len(blind_map)} conditions")

    # Randomize order
    if args.randomize:
        random.shuffle(entries)

    # Create output directory
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build packets
    packets: list[dict] = []
    for manifest in entries:
        run_id = manifest["run_id"]
        case_id = manifest.get("case_id", "unknown")
        condition = manifest.get("condition", "unknown")
        case = case_map.get(case_id)

        condition_label = blind_map.get(condition, condition) if args.blind else condition

        # Create per-run directory
        pkt_dir = output_dir / run_id
        pkt_dir.mkdir(parents=True, exist_ok=True)

        # Copy output image
        run_dir = Path(manifest["_run_dir"])
        for ext in ("png", "jpg", "jpeg", "webp"):
            src = run_dir / f"output.{ext}"
            if src.exists():
                shutil.copy2(src, pkt_dir / f"output.{ext}")
                break

        # Write context.md
        context = build_context_md(manifest, case, condition_label)
        (pkt_dir / "context.md").write_text(context)

        packets.append({
            "run_id": run_id,
            "case_id": case_id,
            "condition": condition,
            "condition_label": condition_label,
            "title": case.get("title", case_id) if case else case_id,
        })

    # Write HTML gallery
    html = build_html_gallery(packets, output_dir)
    (output_dir / "index.html").write_text(html)

    # Write pre-filled CSV template
    csv_path = output_dir / "ratings_template.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for pkt in packets:
            writer.writerow({
                "run_id": pkt["run_id"],
                "case_id": pkt["case_id"],
                "rater_id": "",
                "condition": pkt["condition_label"],
                **{dim: "" for dim in SCORE_DIMENSIONS},
                "freeform_notes": "",
                "failure_tags": "",
            })

    print(f"\nExported {len(packets)} packets to {output_dir}/")
    print(f"  Gallery:  {output_dir / 'index.html'}")
    print(f"  Template: {csv_path}")
    if args.blind:
        # Save blind key for later unblinding
        key_path = output_dir / ".blind_key.json"
        key_path.write_text(json.dumps(blind_map, indent=2))
        print(f"  Blind key: {key_path} (do not share with rater)")


if __name__ == "__main__":
    main()
