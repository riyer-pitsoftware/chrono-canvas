"""AI raters for ChronoCanvas eval scoring.

Each rater takes run artifacts (image, text, audit trace) and a case definition,
then scores across the 8-dimension rubric (0-3 scale).
"""

from __future__ import annotations

import csv
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

EVAL_ROOT = Path(__file__).resolve().parent.parent
CASES_PATH = EVAL_ROOT / "evalset" / "cases.yaml"
RUBRIC_PATH = EVAL_ROOT / "evalset" / "rubric.md"

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


@dataclass
class RatingResult:
    """Structured rating from an AI rater."""

    run_id: str
    case_id: str
    rater_id: str
    condition: str
    scores: dict[str, int]  # dimension -> 0-3
    freeform_notes: str = ""
    failure_tags: list[str] = field(default_factory=list)

    def to_csv_row(self) -> dict[str, str]:
        row = {
            "run_id": self.run_id,
            "case_id": self.case_id,
            "rater_id": self.rater_id,
            "condition": self.condition,
            "freeform_notes": self.freeform_notes,
            "failure_tags": ";".join(self.failure_tags),
        }
        for dim in SCORE_DIMENSIONS:
            row[dim] = str(self.scores.get(dim, ""))
        return row


class BaseRater(ABC):
    """Abstract base class for AI raters."""

    rater_id: str

    def __init__(self, rater_id: str):
        self.rater_id = rater_id

    @abstractmethod
    async def rate_run(
        self,
        run_dir: Path,
        case: dict,
        rubric_text: str,
    ) -> RatingResult:
        """Score a single run against the rubric.

        Args:
            run_dir: Path to run directory (contains output.png, output_text.md, etc.)
            case: Case definition from cases.yaml
            rubric_text: Full rubric markdown text
        """
        ...

    async def rate_runs(
        self,
        run_dirs: list[Path],
        output_csv: Path,
    ) -> list[RatingResult]:
        """Score multiple runs and write results to CSV."""
        cases = load_cases()
        case_map = {c["id"]: c for c in cases}
        rubric_text = RUBRIC_PATH.read_text()

        results: list[RatingResult] = []
        for run_dir in run_dirs:
            manifest = load_manifest(run_dir)
            if not manifest:
                logger.warning("Skipping %s: no manifest", run_dir.name)
                continue

            case_id = manifest["case_id"]
            case = case_map.get(case_id)
            if not case:
                logger.warning("Skipping %s: case %s not found", run_dir.name, case_id)
                continue

            if not (run_dir / "output.png").exists():
                logger.warning("Skipping %s: no output.png", run_dir.name)
                continue

            logger.info("Rating %s (case %s)...", run_dir.name, case_id)
            try:
                result = await self.rate_run(run_dir, case, rubric_text)
                results.append(result)
                logger.info(
                    "  Scores: %s  Tags: %s",
                    {k: v for k, v in result.scores.items()},
                    result.failure_tags,
                )
            except Exception:
                logger.exception("Failed to rate %s", run_dir.name)

        if results:
            write_ratings_csv(results, output_csv)
            logger.info("Wrote %d ratings to %s", len(results), output_csv)

        return results

    def build_system_prompt(self, case: dict, rubric_text: str) -> str:
        """Build the scoring prompt with rubric and case constraints."""
        must_include = "\n".join(f"  - {item}" for item in case.get("must_include", []))
        must_not_include = "\n".join(f"  - {item}" for item in case.get("must_not_include", []))
        anachronisms = "\n".join(f"  - {item}" for item in case.get("anachronism_watchlist", []))
        uncertainty = case.get("uncertainty_notes", "No specific notes.")

        return f"""You are an expert evaluator for ChronoCanvas, a historical portrait generation system.
You will be shown a generated portrait image along with its associated text output and case context.
Score the output on 8 dimensions using the rubric below. Each dimension is scored 0-3.

IMPORTANT: Score plausibility, not historical truth. A plausible output may not be scholarly accurate, and that is fine.

## Rubric

{rubric_text}

## Case Context

**Subject:** {case.get('title', 'Unknown')}
**Region:** {case.get('region', 'Unknown')}
**Time Period:** {case.get('time_period_label', 'Unknown')} ({case.get('time_period_start', '?')} to {case.get('time_period_end', '?')})
**Setting:** {case.get('setting_context', 'Unknown')}
**Evidence Level:** {case.get('evidence_level', 'Unknown')}

### Must Include (positive anchors):
{must_include or '  (none specified)'}

### Must NOT Include (negative anchors):
{must_not_include or '  (none specified)'}

### Anachronism Watchlist:
{anachronisms or '  (none specified)'}

### Uncertainty Notes:
{uncertainty}

## Response Format

You MUST respond with valid JSON only. No other text before or after.

{{
  "prompt_adherence": <0-3>,
  "visual_coherence": <0-3>,
  "face_usability": <0-3>,
  "period_plausibility": <0-3>,
  "anachronism_avoidance": <0-3>,
  "narrative_image_consistency": <0-3>,
  "uncertainty_signaling_quality": <0-3>,
  "audit_trace_completeness": <0-3>,
  "freeform_notes": "<brief notes on key observations, especially for low scores>",
  "failure_tags": ["<tag1>", "<tag2>"]
}}

Score each dimension independently. Use the case constraints as concrete anchors.
For dimensions 6-8 (text-dependent), if no text is available, score based on what you can assess and note the gap.
"""


def load_cases() -> list[dict]:
    with open(CASES_PATH) as f:
        data = yaml.safe_load(f)
    return data.get("cases", [])


def load_manifest(run_dir: Path) -> dict | None:
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.exists():
        return None
    with open(manifest_path) as f:
        return json.load(f)


def write_ratings_csv(results: list[RatingResult], output_path: Path) -> None:
    """Write or append ratings to CSV file."""
    file_exists = output_path.exists()
    existing_run_ids: set[str] = set()

    if file_exists:
        with open(output_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_run_ids.add(row.get("run_id", ""))

    # Filter out duplicates
    new_results = [r for r in results if r.run_id not in existing_run_ids]
    if not new_results:
        logger.info("All ratings already exist in %s, skipping write", output_path)
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        if not file_exists:
            writer.writeheader()
        for result in new_results:
            writer.writerow(result.to_csv_row())
