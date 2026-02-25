#!/usr/bin/env python3
"""Run AI raters against completed eval runs.

Usage:
    # Rate all runs with the Codex rater
    python eval/scripts/rate.py --rater codex

    # Rate specific runs
    python eval/scripts/rate.py --rater codex --runs 2026-02-24T14-32-05Z_CCV1-001_baselineD

    # Rate runs matching a condition
    python eval/scripts/rate.py --rater codex --condition D

    # Rate runs matching a case
    python eval/scripts/rate.py --rater codex --case CCV1-001

    # Use a specific model
    python eval/scripts/rate.py --rater codex --model gpt-4o-mini

    # Dry run (list what would be rated)
    python eval/scripts/rate.py --rater codex --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add parent dirs so imports work when run as a script
EVAL_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = EVAL_ROOT.parent
sys.path.insert(0, str(REPO_ROOT))

from eval.raters import load_manifest

logger = logging.getLogger(__name__)


def discover_runs(
    runs_dir: Path,
    run_ids: list[str] | None = None,
    condition: str | None = None,
    case_id: str | None = None,
) -> list[Path]:
    """Find run directories matching the given filters."""
    if not runs_dir.exists():
        return []

    candidates = sorted(runs_dir.iterdir())
    results = []

    for run_dir in candidates:
        if not run_dir.is_dir():
            continue
        if not (run_dir / "run_manifest.json").exists():
            continue

        # Filter by explicit run IDs
        if run_ids and run_dir.name not in run_ids:
            continue

        manifest = load_manifest(run_dir)
        if not manifest:
            continue

        # Filter by condition
        if condition:
            run_condition = manifest.get("condition", "")
            if condition not in run_condition and f"baseline{condition}" != run_condition:
                continue

        # Filter by case
        if case_id and manifest.get("case_id") != case_id:
            continue

        # Only rate successful runs
        if not manifest.get("success", False):
            logger.info("Skipping failed run: %s", run_dir.name)
            continue

        results.append(run_dir)

    return results


def make_rater(rater_name: str, model: str | None = None, temperature: float = 0.2):
    """Instantiate a rater by name."""
    if rater_name == "codex":
        from eval.raters.codex import CodexRater
        return CodexRater(
            model=model or "gpt-4o",
            temperature=temperature,
        )
    else:
        print(f"Error: unknown rater '{rater_name}'", file=sys.stderr)
        print("Available raters: codex", file=sys.stderr)
        sys.exit(1)


async def async_main(args: argparse.Namespace) -> None:
    runs_dir = EVAL_ROOT / "runs"

    run_ids = None
    if args.runs:
        run_ids = [r.strip() for r in args.runs.split(",")]

    run_dirs = discover_runs(
        runs_dir,
        run_ids=run_ids,
        condition=args.condition,
        case_id=args.case,
    )

    if not run_dirs:
        print("No matching runs found.", file=sys.stderr)
        print(f"  Checked: {runs_dir}", file=sys.stderr)
        if args.condition:
            print(f"  Condition filter: {args.condition}", file=sys.stderr)
        if args.case:
            print(f"  Case filter: {args.case}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(run_dirs)} run(s) to rate with '{args.rater}':")
    for rd in run_dirs:
        manifest = load_manifest(rd)
        case_id = manifest.get("case_id", "?") if manifest else "?"
        cond = manifest.get("condition", "?") if manifest else "?"
        print(f"  {rd.name}  (case={case_id}, condition={cond})")

    if args.dry_run:
        print("\n[DRY RUN] No ratings generated.")
        return

    rater = make_rater(args.rater, model=args.model, temperature=args.temperature)
    output_csv = EVAL_ROOT / "ratings" / f"ratings_{rater.rater_id}.csv"

    results = await rater.rate_runs(run_dirs, output_csv)

    # Summary
    if results:
        print(f"\n{'─'*60}")
        print(f"Rated {len(results)} run(s) → {output_csv}")
        avg_scores = {}
        for dim in ("prompt_adherence", "visual_coherence", "face_usability",
                     "period_plausibility", "anachronism_avoidance"):
            vals = [r.scores.get(dim, 0) for r in results]
            avg_scores[dim] = sum(vals) / len(vals)
        print("Average scores (key dimensions):")
        for dim, avg in avg_scores.items():
            print(f"  {dim}: {avg:.2f}")
    else:
        print("No runs were successfully rated.")


def main():
    parser = argparse.ArgumentParser(
        description="Run AI raters against completed eval runs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --rater codex
  %(prog)s --rater codex --condition D
  %(prog)s --rater codex --case CCV1-001
  %(prog)s --rater codex --model gpt-4o-mini
  %(prog)s --rater codex --dry-run
""",
    )
    parser.add_argument(
        "--rater",
        required=True,
        help="Rater to use (codex)",
    )
    parser.add_argument(
        "--runs",
        help="Comma-separated run IDs to rate (default: all successful runs)",
    )
    parser.add_argument(
        "--condition",
        help="Filter runs by condition (A, B, C, D)",
    )
    parser.add_argument(
        "--case",
        help="Filter runs by case ID (e.g. CCV1-001)",
    )
    parser.add_argument(
        "--model",
        help="Override the model used by the rater",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.2,
        help="Temperature for the rater model (default: 0.2)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List runs that would be rated without scoring",
    )

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
