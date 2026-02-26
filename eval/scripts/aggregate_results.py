#!/usr/bin/env python3
"""Aggregate eval ratings and run metrics into summary reports.

Usage:
    python eval/scripts/aggregate_results.py \\
        --ratings eval/ratings/ \\
        --runs eval/runs/ \\
        --output eval/reports/

    # Only include specific conditions
    python eval/scripts/aggregate_results.py \\
        --ratings eval/ratings/ --runs eval/runs/ --output eval/reports/ \\
        --conditions A D

Merges ratings CSVs with run manifests to produce:
  - reports/summary.csv       (condition-level aggregates)
  - reports/results.csv       (row-level merged results)
  - reports/summary.md        (formatted report)
  - reports/failure-analysis.md
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import statistics
import sys
from collections import Counter
from pathlib import Path

logger = logging.getLogger(__name__)

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

KEY_DIMENSIONS = [
    "prompt_adherence",
    "visual_coherence",
    "face_usability",
    "period_plausibility",
    "anachronism_avoidance",
]

# Condition display order
CONDITION_ORDER = ["baselineA", "baselineB", "baselineC", "baselineD"]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_all_ratings(ratings_dir: Path) -> list[dict]:
    """Load all CSV files from the ratings directory."""
    rows: list[dict] = []
    for csv_path in sorted(ratings_dir.glob("ratings_*.csv")):
        if csv_path.name == "ratings_template.csv":
            continue
        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Parse numeric scores
                for dim in SCORE_DIMENSIONS:
                    val = row.get(dim, "")
                    row[dim] = int(val) if val.strip() else None
                # Parse failure_tags
                tags_raw = row.get("failure_tags", "")
                row["failure_tags_list"] = [
                    t.strip() for t in tags_raw.split(";") if t.strip()
                ]
                row["_source_csv"] = csv_path.name
                rows.append(row)
    return rows


def load_all_manifests(runs_dir: Path) -> dict[str, dict]:
    """Load run_manifest.json from every run directory. Keyed by run_id."""
    manifests: dict[str, dict] = {}
    if not runs_dir.exists():
        return manifests
    for run_dir in sorted(runs_dir.iterdir()):
        manifest_path = run_dir / "run_manifest.json"
        if not manifest_path.exists():
            continue
        with open(manifest_path) as f:
            data = json.load(f)
        run_id = data.get("run_id", run_dir.name)
        manifests[run_id] = data
    return manifests


def merge_ratings_with_manifests(
    ratings: list[dict], manifests: dict[str, dict]
) -> list[dict]:
    """Enrich each rating row with manifest metadata."""
    merged: list[dict] = []
    for row in ratings:
        run_id = row.get("run_id", "")
        manifest = manifests.get(run_id, {})
        enriched = {**row}
        enriched["total_latency_ms"] = manifest.get("total_latency_ms")
        enriched["total_cost_usd"] = manifest.get("total_cost_usd")
        enriched["llm_cost_usd"] = manifest.get("llm_cost_usd")
        enriched["image_cost_usd"] = manifest.get("image_cost_usd")
        enriched["success"] = manifest.get("success")
        enriched["total_retries"] = manifest.get("total_retries", 0)
        enriched["trace_complete"] = manifest.get("trace_complete")
        enriched["terminal_state"] = manifest.get("terminal_state")
        enriched["heuristic_pass"] = manifest.get("heuristic_pass")
        # Normalize condition name for grouping
        condition = row.get("condition", manifest.get("condition", "unknown"))
        enriched["condition_normalized"] = _normalize_condition(condition)
        merged.append(enriched)
    return merged


def _normalize_condition(condition: str) -> str:
    """Normalize condition strings like 'baselineD_full_pipeline' → 'baselineD'."""
    for c in CONDITION_ORDER:
        if condition.startswith(c) or condition == c[-1]:
            return c
    # Try single letter match (e.g. "D" → "baselineD")
    if len(condition) == 1 and condition.upper() in "ABCD":
        return f"baseline{condition.upper()}"
    return condition


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def compute_condition_aggregates(
    merged: list[dict], manifests: dict[str, dict]
) -> dict[str, dict]:
    """Compute per-condition aggregate metrics."""
    # Group by condition
    by_condition: dict[str, list[dict]] = {}
    for row in merged:
        cond = row["condition_normalized"]
        by_condition.setdefault(cond, []).append(row)

    # Also group manifests by condition for success rate (includes unrated runs)
    manifests_by_condition: dict[str, list[dict]] = {}
    for m in manifests.values():
        cond = _normalize_condition(m.get("condition", "unknown"))
        manifests_by_condition.setdefault(cond, []).append(m)

    aggregates: dict[str, dict] = {}
    for cond in sorted(by_condition.keys(), key=_condition_sort_key):
        rows = by_condition[cond]
        cond_manifests = manifests_by_condition.get(cond, [])
        agg: dict = {"condition": cond, "n_ratings": len(rows)}

        # Success rate (from manifests, not ratings)
        if cond_manifests:
            successes = sum(1 for m in cond_manifests if m.get("success"))
            agg["n_runs"] = len(cond_manifests)
            agg["success_rate"] = successes / len(cond_manifests)
        else:
            agg["n_runs"] = 0
            agg["success_rate"] = 0.0

        # Rubric dimension means and medians
        for dim in SCORE_DIMENSIONS:
            vals = [r[dim] for r in rows if r[dim] is not None]
            if vals:
                agg[f"{dim}_mean"] = statistics.mean(vals)
                agg[f"{dim}_median"] = statistics.median(vals)
            else:
                agg[f"{dim}_mean"] = None
                agg[f"{dim}_median"] = None

        # Cost and latency
        costs = [r["total_cost_usd"] for r in rows if r["total_cost_usd"] is not None]
        latencies = [
            r["total_latency_ms"] for r in rows if r["total_latency_ms"] is not None
        ]
        agg["mean_cost_usd"] = statistics.mean(costs) if costs else None
        agg["mean_latency_ms"] = statistics.mean(latencies) if latencies else None
        agg["median_latency_ms"] = statistics.median(latencies) if latencies else None

        # Cost per successful output
        successful_costs = [
            r["total_cost_usd"]
            for r in rows
            if r["total_cost_usd"] is not None and r.get("success")
        ]
        agg["cost_per_success_usd"] = (
            statistics.mean(successful_costs) if successful_costs else None
        )

        # Retry distribution
        retries = [r["total_retries"] for r in rows if r["total_retries"] is not None]
        agg["mean_retries"] = statistics.mean(retries) if retries else None
        retry_counts = Counter(retries)
        agg["retry_distribution"] = dict(sorted(retry_counts.items()))

        # Trace completeness rate
        traced = [r["trace_complete"] for r in rows if r["trace_complete"] is not None]
        agg["trace_completeness_rate"] = (
            sum(1 for t in traced if t) / len(traced) if traced else None
        )

        # Failure tag distribution
        all_tags: list[str] = []
        for r in rows:
            all_tags.extend(r.get("failure_tags_list", []))
        agg["failure_tag_counts"] = dict(Counter(all_tags).most_common())

        aggregates[cond] = agg

    return aggregates


def compute_deltas(
    aggregates: dict[str, dict], baseline: str = "baselineA"
) -> dict[str, dict[str, float | None]]:
    """Compute rubric deltas vs the baseline condition."""
    base = aggregates.get(baseline)
    if not base:
        return {}
    deltas: dict[str, dict[str, float | None]] = {}
    for cond, agg in aggregates.items():
        if cond == baseline:
            continue
        d: dict[str, float | None] = {}
        for dim in SCORE_DIMENSIONS:
            base_val = base.get(f"{dim}_mean")
            cond_val = agg.get(f"{dim}_mean")
            if base_val is not None and cond_val is not None:
                d[dim] = round(cond_val - base_val, 3)
            else:
                d[dim] = None
        deltas[cond] = d
    return deltas


def compute_inter_rater_agreement(merged: list[dict]) -> dict[str, dict]:
    """Compute inter-rater agreement for runs scored by multiple raters."""
    # Group by run_id
    by_run: dict[str, list[dict]] = {}
    for row in merged:
        by_run.setdefault(row["run_id"], []).append(row)

    # Only consider runs with 2+ raters
    multi_rated = {k: v for k, v in by_run.items() if len(v) >= 2}
    if not multi_rated:
        return {"n_multi_rated_runs": 0}

    # For each pair of raters, compute mean absolute difference per dimension
    pair_diffs: dict[str, list[float]] = {dim: [] for dim in SCORE_DIMENSIONS}

    for run_id, rows in multi_rated.items():
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                for dim in SCORE_DIMENSIONS:
                    a = rows[i].get(dim)
                    b = rows[j].get(dim)
                    if a is not None and b is not None:
                        pair_diffs[dim].append(abs(a - b))

    agreement: dict[str, dict] = {
        "n_multi_rated_runs": len(multi_rated),
        "mean_abs_diff": {},
    }
    for dim in SCORE_DIMENSIONS:
        diffs = pair_diffs[dim]
        agreement["mean_abs_diff"][dim] = (
            round(statistics.mean(diffs), 3) if diffs else None
        )

    return agreement


def _condition_sort_key(cond: str) -> tuple:
    """Sort conditions in A, B, C, D order."""
    for i, c in enumerate(CONDITION_ORDER):
        if cond == c:
            return (i,)
    return (99, cond)


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------


def write_results_csv(merged: list[dict], output_path: Path) -> None:
    """Write row-level merged results to CSV."""
    columns = [
        "run_id",
        "case_id",
        "rater_id",
        "condition",
        "condition_normalized",
        *SCORE_DIMENSIONS,
        "freeform_notes",
        "failure_tags",
        "total_latency_ms",
        "total_cost_usd",
        "llm_cost_usd",
        "image_cost_usd",
        "success",
        "total_retries",
        "trace_complete",
        "terminal_state",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in merged:
            out = {k: row.get(k, "") for k in columns}
            for dim in SCORE_DIMENSIONS:
                v = row.get(dim)
                out[dim] = str(v) if v is not None else ""
            writer.writerow(out)


def write_summary_csv(aggregates: dict[str, dict], output_path: Path) -> None:
    """Write condition-level aggregates to CSV."""
    columns = [
        "condition",
        "n_runs",
        "n_ratings",
        "success_rate",
        *[f"{dim}_mean" for dim in SCORE_DIMENSIONS],
        *[f"{dim}_median" for dim in SCORE_DIMENSIONS],
        "mean_cost_usd",
        "cost_per_success_usd",
        "mean_latency_ms",
        "median_latency_ms",
        "mean_retries",
        "trace_completeness_rate",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for cond in sorted(aggregates.keys(), key=_condition_sort_key):
            agg = aggregates[cond]
            row = {}
            for col in columns:
                v = agg.get(col)
                if isinstance(v, float):
                    row[col] = f"{v:.4f}" if "cost" in col else f"{v:.3f}"
                elif v is None:
                    row[col] = ""
                else:
                    row[col] = str(v)
            writer.writerow(row)


def _fmt(val, fmt_str=".2f") -> str:
    if val is None:
        return "—"
    return f"{val:{fmt_str}}"


def _fmt_cost(val) -> str:
    if val is None:
        return "—"
    return f"${val:.4f}"


def _fmt_latency(val) -> str:
    if val is None:
        return "—"
    return f"{val / 1000:.1f}s"


def _fmt_pct(val) -> str:
    if val is None:
        return "—"
    return f"{val:.0%}"


def write_summary_md(
    aggregates: dict[str, dict],
    deltas: dict[str, dict],
    agreement: dict[str, dict],
    output_path: Path,
) -> None:
    """Write formatted summary report in markdown."""
    conditions = sorted(aggregates.keys(), key=_condition_sort_key)

    lines: list[str] = []
    lines.append("# ChronoCanvas Evaluation Summary")
    lines.append("")

    # §1 Purpose
    lines.append("## 1. Purpose of EvalSet v1")
    lines.append("")
    lines.append(
        "This evaluation measures how well ChronoCanvas's multi-agent pipeline "
        "produces historically plausible, visually coherent portrait outputs "
        "compared to direct text-to-image baselines."
    )
    lines.append("")

    # §2 What this eval measures
    lines.append("## 2. What This Eval Measures")
    lines.append("")
    lines.append(
        "Eight dimensions scored 0–3: prompt adherence, visual coherence, "
        "face usability, period plausibility, anachronism avoidance, "
        "narrative-image consistency, uncertainty signaling, and audit trace completeness."
    )
    lines.append("")

    # §3 What it does not measure
    lines.append("## 3. What It Does NOT Measure")
    lines.append("")
    lines.append(
        "- Scholarly historical accuracy (we measure plausibility, not truth)\n"
        "- Artistic merit or aesthetic preference\n"
        "- End-user satisfaction or usability\n"
        "- Real-time performance under load"
    )
    lines.append("")

    # §4 Dataset composition
    total_runs = sum(a["n_runs"] for a in aggregates.values())
    total_ratings = sum(a["n_ratings"] for a in aggregates.values())
    lines.append("## 4. Dataset Composition")
    lines.append("")
    lines.append(
        f"- **Total runs:** {total_runs}\n"
        f"- **Total ratings:** {total_ratings}\n"
        f"- **Conditions:** {len(conditions)}"
    )
    lines.append("")

    # §5 Conditions tested
    lines.append("## 5. Conditions Tested")
    lines.append("")
    lines.append("| Condition | Description |")
    lines.append("|-----------|-------------|")
    condition_desc = {
        "baselineA": "Direct T2I, minimal prompt",
        "baselineB": "Direct T2I, human-refined prompt",
        "baselineC": "ChronoCanvas pipeline (no face/validation)",
        "baselineD": "ChronoCanvas full pipeline",
    }
    for cond in conditions:
        desc = condition_desc.get(cond, cond)
        lines.append(f"| {cond} | {desc} |")
    lines.append("")

    # §6 Key results
    lines.append("## 6. Key Results")
    lines.append("")

    # Main results table
    header = (
        "| Condition | Success Rate | Period Plausibility | "
        "Anachronism Avoidance | Face Usability | "
        "Mean Cost | Mean Latency | Trace Completeness |"
    )
    sep = "|" + "|".join(["---"] * 8) + "|"
    lines.append(header)
    lines.append(sep)
    for cond in conditions:
        a = aggregates[cond]
        lines.append(
            f"| {cond} "
            f"| {_fmt_pct(a['success_rate'])} "
            f"| {_fmt(a.get('period_plausibility_mean'))} "
            f"| {_fmt(a.get('anachronism_avoidance_mean'))} "
            f"| {_fmt(a.get('face_usability_mean'))} "
            f"| {_fmt_cost(a.get('mean_cost_usd'))} "
            f"| {_fmt_latency(a.get('mean_latency_ms'))} "
            f"| {_fmt_pct(a.get('trace_completeness_rate'))} |"
        )
    lines.append("")

    # Full dimension table
    lines.append("### All Dimensions (Mean Scores)")
    lines.append("")
    dim_header = "| Condition | " + " | ".join(
        d.replace("_", " ").title() for d in SCORE_DIMENSIONS
    ) + " |"
    dim_sep = "|" + "|".join(["---"] * (len(SCORE_DIMENSIONS) + 1)) + "|"
    lines.append(dim_header)
    lines.append(dim_sep)
    for cond in conditions:
        a = aggregates[cond]
        vals = " | ".join(_fmt(a.get(f"{d}_mean")) for d in SCORE_DIMENSIONS)
        lines.append(f"| {cond} | {vals} |")
    lines.append("")

    # Deltas table
    if deltas:
        lines.append("### Rubric Deltas vs Baseline A")
        lines.append("")
        delta_header = "| Condition | " + " | ".join(
            d.replace("_", " ").title() for d in SCORE_DIMENSIONS
        ) + " |"
        lines.append(delta_header)
        lines.append(dim_sep)
        for cond in sorted(deltas.keys(), key=_condition_sort_key):
            d = deltas[cond]
            vals = " | ".join(
                _fmt(d.get(dim), "+.2f") if d.get(dim) is not None else "—"
                for dim in SCORE_DIMENSIONS
            )
            lines.append(f"| {cond} | {vals} |")
        lines.append("")

    # §7 Representative examples placeholder
    lines.append("## 7. Representative Examples")
    lines.append("")
    lines.append("*To be populated with specific run examples after review.*")
    lines.append("")

    # §8 Failure taxonomy summary
    lines.append("## 8. Failure Taxonomy Summary")
    lines.append("")
    all_tags: Counter = Counter()
    for agg in aggregates.values():
        all_tags.update(agg.get("failure_tag_counts", {}))
    if all_tags:
        lines.append("| Failure Tag | Count |")
        lines.append("|-------------|-------|")
        for tag, count in all_tags.most_common():
            lines.append(f"| `{tag}` | {count} |")
    else:
        lines.append("No failure tags recorded.")
    lines.append("")

    # §9 Inter-rater agreement
    lines.append("## 9. Inter-Rater Agreement")
    lines.append("")
    n_multi = agreement.get("n_multi_rated_runs", 0)
    if n_multi > 0:
        lines.append(f"Runs scored by multiple raters: **{n_multi}**")
        lines.append("")
        lines.append("Mean absolute score difference per dimension:")
        lines.append("")
        lines.append("| Dimension | Mean Abs Diff |")
        lines.append("|-----------|---------------|")
        for dim in SCORE_DIMENSIONS:
            v = agreement.get("mean_abs_diff", {}).get(dim)
            lines.append(f"| {dim.replace('_', ' ').title()} | {_fmt(v)} |")
    else:
        lines.append("No runs were scored by multiple raters.")
    lines.append("")

    # §10 Limitations and next steps
    lines.append("## 10. Limitations")
    lines.append("")
    lines.append(
        "- Small dataset (pilot); conclusions are directional, not definitive\n"
        "- AI raters may have systematic biases vs human raters\n"
        "- Cost/latency data reflects local dev environment, not production\n"
        "- Direct baselines (A/B) lack text output, limiting text-dependent dimensions"
    )
    lines.append("")
    lines.append("## 11. Next Steps")
    lines.append("")
    lines.append(
        "- Expand to 30 cases for statistical power\n"
        "- Collect human ratings for inter-rater calibration\n"
        "- Run under production-like infrastructure for cost/latency accuracy\n"
        "- Add v1.1 dimensions if gaps emerge"
    )
    lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines))


def write_failure_analysis_md(
    aggregates: dict[str, dict], output_path: Path
) -> None:
    """Write failure taxonomy analysis report."""
    conditions = sorted(aggregates.keys(), key=_condition_sort_key)

    lines: list[str] = []
    lines.append("# Failure Analysis")
    lines.append("")
    lines.append(
        "Failure tags from the evaluation taxonomy, aggregated by condition. "
        "Tags are assigned when a dimension scores 0 or 1."
    )
    lines.append("")

    # Overall tag counts
    all_tags: Counter = Counter()
    for agg in aggregates.values():
        all_tags.update(agg.get("failure_tag_counts", {}))

    if not all_tags:
        lines.append("No failure tags were recorded across any condition.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(lines))
        return

    lines.append("## Overall Failure Tag Distribution")
    lines.append("")
    lines.append("| Failure Tag | Total Count |")
    lines.append("|-------------|-------------|")
    for tag, count in all_tags.most_common():
        lines.append(f"| `{tag}` | {count} |")
    lines.append("")

    # Categorized breakdown
    categories = {
        "Visual": [
            "visual_artifact_severe", "bad_composition", "face_missing",
            "face_distorted", "multi_face_unwanted", "style_mismatch",
        ],
        "Historical": [
            "obvious_anachronism", "cultural_flattening_generic",
            "period_cue_absent", "wrong_region_style",
        ],
        "Text": [
            "overconfident_historical_claim", "generic_fantasy_prose",
            "anachronistic_language", "narrative_image_mismatch",
        ],
        "System": [
            "provider_timeout", "provider_error", "validation_loop_exhausted",
            "face_pipeline_error", "trace_incomplete", "checkpoint_retry_failure",
        ],
    }

    lines.append("## Failure Tags by Category")
    lines.append("")
    for cat_name, cat_tags in categories.items():
        found = {t: all_tags[t] for t in cat_tags if t in all_tags}
        if found:
            lines.append(f"### {cat_name}")
            lines.append("")
            lines.append("| Tag | Count |")
            lines.append("|-----|-------|")
            for tag, count in sorted(found.items(), key=lambda x: -x[1]):
                lines.append(f"| `{tag}` | {count} |")
            lines.append("")

    # Per-condition breakdown
    lines.append("## Failure Tags by Condition")
    lines.append("")
    for cond in conditions:
        agg = aggregates[cond]
        tags = agg.get("failure_tag_counts", {})
        if not tags:
            continue
        lines.append(f"### {cond}")
        lines.append("")
        lines.append("| Tag | Count |")
        lines.append("|-----|-------|")
        for tag, count in sorted(tags.items(), key=lambda x: -x[1]):
            lines.append(f"| `{tag}` | {count} |")
        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Aggregate ChronoCanvas eval results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --ratings eval/ratings/ --runs eval/runs/ --output eval/reports/
  %(prog)s --ratings eval/ratings/ --runs eval/runs/ --output eval/reports/ --conditions A D
""",
    )
    parser.add_argument(
        "--ratings", required=True, help="Directory containing rating CSVs"
    )
    parser.add_argument(
        "--runs", required=True, help="Directory containing run artifacts"
    )
    parser.add_argument(
        "--output", required=True, help="Output directory for reports"
    )
    parser.add_argument(
        "--conditions",
        nargs="*",
        help="Only include these conditions (e.g. A D)",
    )

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    ratings_dir = Path(args.ratings)
    runs_dir = Path(args.runs)
    output_dir = Path(args.output)

    # 1. Load data
    logger.info("Loading ratings from %s", ratings_dir)
    ratings = load_all_ratings(ratings_dir)
    logger.info("Loaded %d rating rows", len(ratings))

    logger.info("Loading run manifests from %s", runs_dir)
    manifests = load_all_manifests(runs_dir)
    logger.info("Loaded %d run manifests", len(manifests))

    if not ratings:
        print("No ratings found. Nothing to aggregate.", file=sys.stderr)
        sys.exit(1)

    # 2. Merge
    merged = merge_ratings_with_manifests(ratings, manifests)

    # 3. Filter conditions if requested
    if args.conditions:
        allowed = {f"baseline{c.upper()}" for c in args.conditions}
        merged = [r for r in merged if r["condition_normalized"] in allowed]
        manifests = {
            k: v
            for k, v in manifests.items()
            if _normalize_condition(v.get("condition", "")) in allowed
        }
        if not merged:
            print("No ratings match the requested conditions.", file=sys.stderr)
            sys.exit(1)

    # 4. Aggregate
    aggregates = compute_condition_aggregates(merged, manifests)
    deltas = compute_deltas(aggregates)
    agreement = compute_inter_rater_agreement(merged)

    # 5. Write outputs
    results_csv = output_dir / "results.csv"
    summary_csv = output_dir / "summary.csv"
    summary_md = output_dir / "summary.md"
    failure_md = output_dir / "failure-analysis.md"

    write_results_csv(merged, results_csv)
    logger.info("Wrote %s (%d rows)", results_csv, len(merged))

    write_summary_csv(aggregates, summary_csv)
    logger.info("Wrote %s (%d conditions)", summary_csv, len(aggregates))

    write_summary_md(aggregates, deltas, agreement, summary_md)
    logger.info("Wrote %s", summary_md)

    write_failure_analysis_md(aggregates, failure_md)
    logger.info("Wrote %s", failure_md)

    # Print summary to stdout
    print(f"\n{'─' * 60}")
    print(f"Aggregated {len(merged)} ratings across {len(aggregates)} condition(s)")
    print(f"\nOutputs:")
    print(f"  {results_csv}")
    print(f"  {summary_csv}")
    print(f"  {summary_md}")
    print(f"  {failure_md}")

    print(f"\nKey Metrics by Condition:")
    for cond in sorted(aggregates.keys(), key=_condition_sort_key):
        a = aggregates[cond]
        print(f"\n  {cond} (n={a['n_ratings']} ratings, {a['n_runs']} runs):")
        print(f"    Success rate:     {_fmt_pct(a['success_rate'])}")
        for dim in KEY_DIMENSIONS:
            print(f"    {dim:30s} {_fmt(a.get(f'{dim}_mean'))}")
        print(f"    Mean cost:        {_fmt_cost(a.get('mean_cost_usd'))}")
        print(f"    Mean latency:     {_fmt_latency(a.get('mean_latency_ms'))}")


if __name__ == "__main__":
    main()
