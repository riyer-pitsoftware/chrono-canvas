# ChronoCanvas Evaluation Summary

## 1. Purpose of EvalSet v1

This evaluation measures how well ChronoCanvas's multi-agent pipeline produces historically plausible, visually coherent portrait outputs compared to direct text-to-image baselines.

## 2. What This Eval Measures

Eight dimensions scored 0–3: prompt adherence, visual coherence, face usability, period plausibility, anachronism avoidance, narrative-image consistency, uncertainty signaling, and audit trace completeness.

## 3. What It Does NOT Measure

- Scholarly historical accuracy (we measure plausibility, not truth)
- Artistic merit or aesthetic preference
- End-user satisfaction or usability
- Real-time performance under load

## 4. Dataset Composition

- **Total runs:** 9
- **Total ratings:** 8
- **Conditions:** 1

## 5. Conditions Tested

| Condition | Description |
|-----------|-------------|
| baselineD | ChronoCanvas full pipeline |

## 6. Key Results

| Condition | Success Rate | Period Plausibility | Anachronism Avoidance | Face Usability | Mean Cost | Mean Latency | Trace Completeness |
|---|---|---|---|---|---|---|---|
| baselineD | 89% | 0.75 | 0.50 | 3.00 | $0.0000 | 282.0s | 100% |

### All Dimensions (Mean Scores)

| Condition | Prompt Adherence | Visual Coherence | Face Usability | Period Plausibility | Anachronism Avoidance | Narrative Image Consistency | Uncertainty Signaling Quality | Audit Trace Completeness |
|---|---|---|---|---|---|---|---|---|
| baselineD | 1.00 | 2.88 | 3.00 | 0.75 | 0.50 | 0.25 | 0.00 | 0.25 |

## 7. Representative Examples

*To be populated with specific run examples after review.*

## 8. Failure Taxonomy Summary

| Failure Tag | Count |
|-------------|-------|
| `trace_incomplete` | 8 |
| `overconfident_historical_claim` | 8 |
| `narrative_image_mismatch` | 7 |
| `period_cue_absent` | 6 |
| `obvious_anachronism` | 5 |
| `wrong_region_style` | 4 |
| `cultural_flattening_generic` | 4 |
| `modern_braiding_styles` | 1 |
| `anachronistic_language` | 1 |
| `style_mismatch` | 1 |

## 9. Inter-Rater Agreement

No runs were scored by multiple raters.

## 10. Limitations

- Small dataset (pilot); conclusions are directional, not definitive
- AI raters may have systematic biases vs human raters
- Cost/latency data reflects local dev environment, not production
- Direct baselines (A/B) lack text output, limiting text-dependent dimensions

## 11. Next Steps

- Expand to 30 cases for statistical power
- Collect human ratings for inter-rater calibration
- Run under production-like infrastructure for cost/latency accuracy
- Add v1.1 dimensions if gaps emerge
