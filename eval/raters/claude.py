"""Claude vision rater for ChronoCanvas eval scoring.

Uses Anthropic's Claude vision API to score eval runs on the 8-dimension rubric.
Requires ANTHROPIC_API_KEY environment variable.

Usage:
    from eval.raters.claude import ClaudeRater
    rater = ClaudeRater()
    result = await rater.rate_run(run_dir, case, rubric_text)
"""

from __future__ import annotations

import base64
import json
import logging
import os
from pathlib import Path

from . import BaseRater, RatingResult, SCORE_DIMENSIONS, load_manifest

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-5-20250929"


class ClaudeRater(BaseRater):
    """AI rater using Anthropic Claude vision."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.2,
    ):
        super().__init__(rater_id="claude-vision")
        self.model = model
        self.temperature = temperature

    async def rate_run(
        self,
        run_dir: Path,
        case: dict,
        rubric_text: str,
    ) -> RatingResult:
        """Score a single run using Claude vision."""
        # Lazy import so the module can be imported without anthropic installed
        from anthropic import AsyncAnthropic

        manifest = load_manifest(run_dir)
        run_id = manifest["run_id"] if manifest else run_dir.name
        case_id = manifest["case_id"] if manifest else case["id"]
        condition = manifest.get("condition", "unknown") if manifest else "unknown"

        system_prompt = self.build_system_prompt(case, rubric_text)
        user_content = self._build_user_content(run_dir, case)

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY environment variable is required")

        client = AsyncAnthropic(api_key=api_key)

        response = await client.messages.create(
            model=self.model,
            max_tokens=1024,
            temperature=self.temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )

        raw = response.content[0].text
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        cost = self._estimate_cost(input_tokens, output_tokens)

        logger.info(
            "Claude rating for %s: %d input tokens, %d output tokens, ~$%.4f",
            run_id,
            input_tokens,
            output_tokens,
            cost,
        )

        return self._parse_response(raw, run_id, case_id, condition)

    def _build_user_content(self, run_dir: Path, case: dict) -> list[dict]:
        """Build multimodal user message with image and text artifacts."""
        content: list[dict] = []

        # Add the generated image
        image_path = run_dir / "output.png"
        if image_path.exists():
            image_b64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": image_b64,
                },
            })

        # Add text context
        text_parts = [f"**Case:** {case.get('title', 'Unknown')}"]

        output_text_path = run_dir / "output_text.md"
        if output_text_path.exists():
            output_text = output_text_path.read_text()
            text_parts.append(f"\n**Generated Text:**\n{output_text}")

        audit_path = run_dir / "audit_trace.json"
        if audit_path.exists():
            try:
                audit = json.loads(audit_path.read_text())
                agent_trace = audit.get("agent_trace", [])
                if agent_trace:
                    trace_summary = []
                    for entry in agent_trace:
                        agent = entry.get("agent", "unknown")
                        status = entry.get("status", "unknown")
                        trace_summary.append(f"  - {agent}: {status}")
                    text_parts.append(
                        f"\n**Audit Trace Summary ({len(agent_trace)} events):**\n"
                        + "\n".join(trace_summary)
                    )
                else:
                    text_parts.append("\n**Audit Trace:** Empty (no agent trace events)")
            except json.JSONDecodeError:
                text_parts.append("\n**Audit Trace:** Could not parse")
        else:
            text_parts.append("\n**Audit Trace:** Not available")

        content.append({"type": "text", "text": "\n".join(text_parts)})
        return content

    def _parse_response(
        self,
        raw: str,
        run_id: str,
        case_id: str,
        condition: str,
    ) -> RatingResult:
        """Parse structured JSON response into RatingResult."""
        # Claude may wrap JSON in markdown code fences
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            # Strip code fence markers
            lines = cleaned.split("\n")
            # Remove first line (```json or ```)
            lines = lines[1:]
            # Remove last line (```)
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.error("Failed to parse response as JSON: %s", raw[:200])
            raise ValueError(f"Rater returned invalid JSON: {raw[:200]}")

        scores = {}
        for dim in SCORE_DIMENSIONS:
            val = data.get(dim)
            if val is not None:
                score = int(val)
                if not 0 <= score <= 3:
                    logger.warning("Score out of range for %s: %d, clamping", dim, score)
                    score = max(0, min(3, score))
                scores[dim] = score
            else:
                logger.warning("Missing score for dimension: %s", dim)
                scores[dim] = 0

        failure_tags = data.get("failure_tags", [])
        if isinstance(failure_tags, str):
            failure_tags = [t.strip() for t in failure_tags.split(";") if t.strip()]

        return RatingResult(
            run_id=run_id,
            case_id=case_id,
            rater_id=self.rater_id,
            condition=condition,
            scores=scores,
            freeform_notes=data.get("freeform_notes", ""),
            failure_tags=failure_tags,
        )

    @staticmethod
    def _estimate_cost(input_tokens: int, output_tokens: int) -> float:
        """Rough cost estimate for Claude Sonnet 4.5 (per-token pricing)."""
        # Sonnet 4.5: $3/M input, $15/M output
        return (input_tokens * 3.0 / 1_000_000) + (output_tokens * 15.0 / 1_000_000)
