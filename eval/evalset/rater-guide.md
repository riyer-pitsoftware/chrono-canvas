# ChronoCanvas EvalSet v1 - Rater Guide

## Overview

You are scoring outputs from ChronoCanvas, a system that generates historically-informed portraits. Your role is to evaluate **plausibility and quality**, not historical truth.

## Before You Start

1. Read `rubric.md` thoroughly - it defines the 0-3 scale and all 8 scoring dimensions.
2. Familiarize yourself with the case list in `cases.yaml` - each case includes `must_include`, `must_not_include`, and `anachronism_watchlist` fields that guide scoring.
3. Review the `uncertainty_notes` for each case - these tell you what is knowable vs. speculative for the given historical context.

## Scoring Principles

### Score plausibility, not truth
You are not a historian grading an exam. You are evaluating whether the output is **period-plausible** and free of obvious errors. A plausible output may not be "correct" in a scholarly sense, and that is fine.

### Use the case constraints
Each case specifies `must_include` and `must_not_include` items. Use these as concrete scoring anchors:
- If a `must_include` item is present: positive signal for prompt adherence and period plausibility
- If a `must_not_include` item is present: negative signal, score accordingly
- Check the `anachronism_watchlist` for each case before scoring Dimension 5

### Avoid over-penalizing stylistic variation
If period cues are preserved and constraints are met, do not penalize artistic choices (color palette, composition style, level of detail). The rubric measures plausibility, not aesthetic preference.

### Focus on observable issues
Score what you can see. Do not speculate about what the system "might have done wrong" internally. If the output looks good and meets constraints, score it accordingly.

### Note concrete evidence for low scores
When scoring 0 or 1 on any dimension, write a brief note in `freeform_notes` describing the specific issue (e.g., "visible wristwatch on left wrist", "face completely distorted", "modern suit jacket").

## Workflow

1. Open the rating packet for each run (image + generated text + audit trace summary)
2. Read the case's `prompt_brief` and constraints
3. Score all 8 dimensions using the 0-3 scale from `rubric.md`
4. Tag any failure types from the taxonomy (semicolon-separated in `failure_tags` column)
5. Add freeform notes for anything notable - especially low scores
6. Move to the next run

## Blinding (if applicable)

If you are scoring blinded packets, you will not see condition labels (A/B/C/D). This is intentional - score the output on its own merits without knowing which pipeline produced it.

## Rating CSV Format

Fill in one row per run with these columns:

| Column | Description |
|--------|-------------|
| `run_id` | Unique run identifier |
| `case_id` | Case ID (e.g., CCV1-001) |
| `rater_id` | Your rater ID |
| `condition` | Condition label (A/B/C/D) or "blinded" |
| `prompt_adherence` | 0-3 |
| `visual_coherence` | 0-3 |
| `face_usability` | 0-3 |
| `period_plausibility` | 0-3 |
| `anachronism_avoidance` | 0-3 |
| `narrative_image_consistency` | 0-3 |
| `uncertainty_signaling_quality` | 0-3 |
| `audit_trace_completeness` | 0-3 |
| `freeform_notes` | Free text observations |
| `failure_tags` | Semicolon-separated tags from taxonomy |

## Common Pitfalls

- **Anchoring bias**: Score each run independently. Don't let a very good or bad run shift your scale for subsequent runs.
- **Halo effect**: A beautiful image can still have anachronisms. Score each dimension separately.
- **Leniency for "close enough"**: If the case says `must_not_include: "modern eyewear"` and you see glasses, that is a clear miss regardless of overall quality.
- **Audit trace scoring**: For Baseline A/B runs, audit traces will be minimal by design. Score what is present, not what the system architecture lacks.
