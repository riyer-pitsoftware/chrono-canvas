"""Service layer for reading eval data from the filesystem.

Reuses aggregation functions from eval/scripts/aggregate_results.py.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import logging
import statistics
from collections import Counter
from pathlib import Path

import yaml

from chronocanvas.config import settings

logger = logging.getLogger(__name__)


def _load_aggregate_module():
    """Dynamically import the aggregation script from the eval directory."""
    script_path = Path(settings.eval_dir).resolve() / "scripts" / "aggregate_results.py"
    if not script_path.exists():
        return None
    spec = importlib.util.spec_from_file_location("aggregate_results", script_path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_agg_mod = _load_aggregate_module()

# Constants / functions from aggregation script (with fallbacks)
SCORE_DIMENSIONS: list[str] = getattr(
    _agg_mod,
    "SCORE_DIMENSIONS",
    [
        "prompt_adherence",
        "visual_coherence",
        "face_usability",
        "period_plausibility",
        "anachronism_avoidance",
        "narrative_image_consistency",
        "uncertainty_signaling_quality",
        "audit_trace_completeness",
    ],
)

CONDITION_ORDER: list[str] = getattr(
    _agg_mod,
    "CONDITION_ORDER",
    [
        "baselineA",
        "baselineB",
        "baselineC",
        "baselineD",
    ],
)


def _normalize_condition(condition: str) -> str:
    """Normalize condition strings like 'baselineD_full_pipeline' -> 'baselineD'."""
    if _agg_mod:
        return _agg_mod._normalize_condition(condition)
    for c in CONDITION_ORDER:
        if condition.startswith(c):
            return c
    if len(condition) == 1 and condition.upper() in "ABCD":
        return f"baseline{condition.upper()}"
    return condition


def _load_all_manifests(runs_dir: Path) -> dict[str, dict]:
    """Load run_manifest.json from every run directory."""
    if _agg_mod:
        return _agg_mod.load_all_manifests(runs_dir)
    manifests: dict[str, dict] = {}
    if not runs_dir.exists():
        return manifests
    for run_dir in sorted(runs_dir.iterdir()):
        manifest_path = run_dir / "run_manifest.json"
        if not manifest_path.exists():
            continue
        with open(manifest_path) as f:
            data = json.load(f)
        manifests[data.get("run_id", run_dir.name)] = data
    return manifests


def _load_all_ratings(ratings_dir: Path) -> list[dict]:
    """Load all CSV files from the ratings directory."""
    if _agg_mod:
        return _agg_mod.load_all_ratings(ratings_dir)
    rows: list[dict] = []
    if not ratings_dir.exists():
        return rows
    for csv_path in sorted(ratings_dir.glob("ratings_*.csv")):
        if csv_path.name == "ratings_template.csv":
            continue
        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                for dim in SCORE_DIMENSIONS:
                    val = row.get(dim, "")
                    row[dim] = int(val) if val.strip() else None
                tags_raw = row.get("failure_tags", "")
                row["failure_tags_list"] = [t.strip() for t in tags_raw.split(";") if t.strip()]
                rows.append(row)
    return rows


def _merge_ratings_with_manifests(ratings: list[dict], manifests: dict[str, dict]) -> list[dict]:
    """Enrich each rating row with manifest metadata."""
    if _agg_mod:
        return _agg_mod.merge_ratings_with_manifests(ratings, manifests)
    merged: list[dict] = []
    for row in ratings:
        run_id = row.get("run_id", "")
        manifest = manifests.get(run_id, {})
        enriched = {**row}
        enriched["total_latency_ms"] = manifest.get("total_latency_ms")
        enriched["total_cost_usd"] = manifest.get("total_cost_usd")
        enriched["success"] = manifest.get("success")
        enriched["total_retries"] = manifest.get("total_retries", 0)
        enriched["trace_complete"] = manifest.get("trace_complete")
        condition = row.get("condition", manifest.get("condition", "unknown"))
        enriched["condition_normalized"] = _normalize_condition(condition)
        merged.append(enriched)
    return merged


def _compute_condition_aggregates(
    merged: list[dict], manifests: dict[str, dict]
) -> dict[str, dict]:
    """Compute per-condition aggregate metrics."""
    if _agg_mod:
        return _agg_mod.compute_condition_aggregates(merged, manifests)
    # Inline fallback
    by_condition: dict[str, list[dict]] = {}
    for row in merged:
        cond = row["condition_normalized"]
        by_condition.setdefault(cond, []).append(row)

    manifests_by_condition: dict[str, list[dict]] = {}
    for m in manifests.values():
        cond = _normalize_condition(m.get("condition", "unknown"))
        manifests_by_condition.setdefault(cond, []).append(m)

    aggregates: dict[str, dict] = {}
    for cond, rows in sorted(by_condition.items()):
        cond_manifests = manifests_by_condition.get(cond, [])
        agg: dict = {"condition": cond, "n_ratings": len(rows)}
        if cond_manifests:
            successes = sum(1 for m in cond_manifests if m.get("success"))
            agg["n_runs"] = len(cond_manifests)
            agg["success_rate"] = successes / len(cond_manifests)
        else:
            agg["n_runs"] = 0
            agg["success_rate"] = 0.0

        for dim in SCORE_DIMENSIONS:
            vals = [r[dim] for r in rows if r[dim] is not None]
            agg[f"{dim}_mean"] = statistics.mean(vals) if vals else None
            agg[f"{dim}_median"] = statistics.median(vals) if vals else None

        costs = [r["total_cost_usd"] for r in rows if r["total_cost_usd"] is not None]
        latencies = [r["total_latency_ms"] for r in rows if r["total_latency_ms"] is not None]
        agg["mean_cost_usd"] = statistics.mean(costs) if costs else None
        agg["mean_latency_ms"] = statistics.mean(latencies) if latencies else None

        all_tags: list[str] = []
        for r in rows:
            all_tags.extend(r.get("failure_tags_list", []))
        agg["failure_tag_counts"] = dict(Counter(all_tags).most_common())
        aggregates[cond] = agg

    return aggregates


def _eval_dir() -> Path:
    return Path(settings.eval_dir)


def _runs_dir() -> Path:
    return _eval_dir() / "runs"


def _ratings_dir() -> Path:
    return _eval_dir() / "ratings"


def _cases_path() -> Path:
    return _eval_dir() / "evalset" / "cases.yaml"


def _load_cases_yaml() -> dict[str, dict]:
    """Load and index cases.yaml by case_id."""
    path = _cases_path()
    if not path.exists():
        return {}
    with open(path) as f:
        data = yaml.safe_load(f)
    cases = data.get("cases", [])
    return {c["id"]: c for c in cases}


def _build_ratings_index() -> dict[str, dict]:
    """Build a lookup from run_id -> rating row."""
    ratings = _load_all_ratings(_ratings_dir())
    index: dict[str, dict] = {}
    for row in ratings:
        run_id = row.get("run_id", "")
        if run_id:
            index[run_id] = row
    return index


def _image_url_for_run(run_id: str) -> str | None:
    """Return the image URL for a run, checking common filenames."""
    run_dir = _runs_dir() / run_id
    for name in ("portrait_final.png", "output.png", "portrait.png"):
        if (run_dir / name).exists():
            return f"/eval-assets/{run_id}/{name}"
    return None


def _is_rejected(run_id: str) -> bool:
    """Check if a run has been soft-rejected."""
    return (_runs_dir() / run_id / "rejected.json").exists()


def reject_run(run_id: str, reason: str | None = None) -> None:
    """Soft-reject a run by writing a rejected.json marker."""
    import datetime

    run_dir = _runs_dir() / run_id
    if not run_dir.exists():
        raise FileNotFoundError(f"Run directory not found: {run_id}")
    marker = {
        "rejected_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "reason": reason,
    }
    (run_dir / "rejected.json").write_text(json.dumps(marker, indent=2))


def unreject_run(run_id: str) -> None:
    """Remove the soft-reject marker from a run."""
    marker = _runs_dir() / run_id / "rejected.json"
    if marker.exists():
        marker.unlink()


def _title_for_case(case_id: str, cases: dict[str, dict]) -> str:
    case = cases.get(case_id)
    if case:
        return case.get("title", case_id)
    return case_id


def list_runs(
    condition: str | None = None,
    case_id: str | None = None,
    include_rejected: bool = False,
) -> list[dict]:
    """List all eval runs with summary info."""
    manifests = _load_all_manifests(_runs_dir())
    ratings_index = _build_ratings_index()
    cases = _load_cases_yaml()

    results = []
    for run_id, manifest in manifests.items():
        m_case_id = manifest.get("case_id", "")
        m_condition = _normalize_condition(manifest.get("condition", "unknown"))

        if condition and m_condition != _normalize_condition(condition):
            continue
        if case_id and m_case_id != case_id:
            continue

        rejected = _is_rejected(run_id)
        if rejected and not include_rejected:
            continue

        results.append(
            {
                "run_id": run_id,
                "case_id": m_case_id,
                "condition": m_condition,
                "success": manifest.get("success", False),
                "image_url": _image_url_for_run(run_id),
                "title": _title_for_case(m_case_id, cases),
                "has_rating": run_id in ratings_index,
                "rejected": rejected,
            }
        )

    results.sort(key=lambda r: r["run_id"])
    return results


def get_run(run_id: str) -> dict | None:
    """Get detailed info for a single run."""
    run_dir = _runs_dir() / run_id
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.exists():
        return None

    with open(manifest_path) as f:
        manifest = json.load(f)

    cases = _load_cases_yaml()
    ratings_index = _build_ratings_index()
    rating = ratings_index.get(run_id)

    output_text = None
    output_text_path = run_dir / "output_text.md"
    if output_text_path.exists():
        output_text = output_text_path.read_text()

    case_id = manifest.get("case_id", "")

    rating_clean = None
    if rating:
        rating_clean = {dim: rating.get(dim) for dim in SCORE_DIMENSIONS}
        rating_clean["freeform_notes"] = rating.get("freeform_notes", "")
        rating_clean["failure_tags"] = rating.get("failure_tags", "")
        rating_clean["rater_id"] = rating.get("rater_id", "")

    return {
        "run_id": run_id,
        "case_id": case_id,
        "condition": _normalize_condition(manifest.get("condition", "unknown")),
        "success": manifest.get("success", False),
        "image_url": _image_url_for_run(run_id),
        "title": _title_for_case(case_id, cases),
        "has_rating": rating is not None,
        "rejected": _is_rejected(run_id),
        "manifest": manifest,
        "rating": rating_clean,
        "output_text": output_text,
    }


def list_cases() -> list[dict]:
    """List all eval cases with their run summaries."""
    cases = _load_cases_yaml()
    runs = list_runs()

    runs_by_case: dict[str, list[dict]] = {}
    for run in runs:
        runs_by_case.setdefault(run["case_id"], []).append(run)

    results = []
    for case_id, case in cases.items():
        results.append(
            {
                "case_id": case_id,
                "title": case.get("title", case_id),
                "subject_type": case.get("subject_type", ""),
                "region": case.get("region", ""),
                "time_period_label": case.get("time_period_label", ""),
                "runs": runs_by_case.get(case_id, []),
            }
        )

    return results


def get_case(case_id: str) -> dict | None:
    """Get a single case with all its runs."""
    cases = _load_cases_yaml()
    case = cases.get(case_id)
    if not case:
        return None

    runs = list_runs(case_id=case_id)
    return {
        "case_id": case_id,
        "title": case.get("title", case_id),
        "subject_type": case.get("subject_type", ""),
        "region": case.get("region", ""),
        "time_period_label": case.get("time_period_label", ""),
        "runs": runs,
    }


def get_dashboard() -> dict:
    """Aggregate stats for the dashboard view."""
    manifests = _load_all_manifests(_runs_dir())
    ratings = _load_all_ratings(_ratings_dir())
    merged = _merge_ratings_with_manifests(ratings, manifests)

    aggregates = _compute_condition_aggregates(merged, manifests)

    conditions = []
    for cond, agg in sorted(aggregates.items()):
        conditions.append(
            {
                "condition": cond,
                "n_runs": agg.get("n_runs", 0),
                "n_ratings": agg.get("n_ratings", 0),
                "success_rate": agg.get("success_rate", 0),
                "mean_cost_usd": agg.get("mean_cost_usd"),
                "mean_latency_ms": agg.get("mean_latency_ms"),
            }
        )

    dimension_scores = []
    for cond, agg in sorted(aggregates.items()):
        for dim in SCORE_DIMENSIONS:
            mean_val = agg.get(f"{dim}_mean")
            median_val = agg.get(f"{dim}_median")
            if mean_val is not None:
                dimension_scores.append(
                    {
                        "condition": cond,
                        "dimension": dim,
                        "mean": round(mean_val, 3),
                        "median": round(median_val, 3) if median_val is not None else 0,
                        "n": agg.get("n_ratings", 0),
                    }
                )

    failure_tags = []
    tag_categories = {
        "visual_artifact_severe": "Visual",
        "bad_composition": "Visual",
        "face_missing": "Visual",
        "face_distorted": "Visual",
        "multi_face_unwanted": "Visual",
        "style_mismatch": "Visual",
        "obvious_anachronism": "Historical",
        "cultural_flattening_generic": "Historical",
        "period_cue_absent": "Historical",
        "wrong_region_style": "Historical",
        "overconfident_historical_claim": "Text",
        "generic_fantasy_prose": "Text",
        "anachronistic_language": "Text",
        "narrative_image_mismatch": "Text",
        "provider_timeout": "System",
        "provider_error": "System",
        "validation_loop_exhausted": "System",
        "face_pipeline_error": "System",
        "trace_incomplete": "System",
        "checkpoint_retry_failure": "System",
    }
    all_tag_counts: dict[str, int] = {}
    for agg in aggregates.values():
        for tag, count in agg.get("failure_tag_counts", {}).items():
            all_tag_counts[tag] = all_tag_counts.get(tag, 0) + count

    for tag, count in sorted(all_tag_counts.items(), key=lambda x: -x[1]):
        failure_tags.append(
            {
                "tag": tag,
                "count": count,
                "category": tag_categories.get(tag, "Other"),
            }
        )

    return {
        "conditions": conditions,
        "dimension_scores": dimension_scores,
        "failure_tags": failure_tags,
        "total_runs": len(manifests),
        "total_rated": len(ratings),
    }
