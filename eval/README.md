# ChronoCanvas EvalSet v1

A plausibility-oriented evaluation harness for ChronoCanvas that measures
**historical plausibility**, **system quality**, and **operational reliability**
without overclaiming "historical accuracy."

## What This Eval Measures

1. **Output Quality** - Is the output visually coherent and usable?
2. **Historical Plausibility** - Is the output broadly period-plausible and free of obvious anachronisms?
3. **System Quality** - Is the pipeline reliable, traceable, and transparent in cost/latency?

## What This Eval Does NOT Measure

- Ground-truth historical face accuracy
- Scholarly correctness of disputed historical interpretations
- Universal image model quality
- Objective truth of visual reconstructions

## Structure

```
eval/
  configs/           # Condition configs (baselineA-D.yaml)
  evalset/           # Case definitions, rubric, rater guide
    cases.yaml       # 30 curated cases (10-case pilot first)
    rubric.md        # 0-3 scoring rubric, 8 dimensions
    rater-guide.md   # Instructions for human raters
  runs/              # Per-run artifacts (manifests, outputs, traces)
  ratings/           # Human rating CSVs
  reports/           # Aggregate summaries and failure analysis
  scripts/           # Orchestration and aggregation scripts
```

## Conditions

| Condition | Description |
|-----------|-------------|
| **A** | One-shot T2I, minimal prompt |
| **B** | One-shot T2I, human-refined prompt |
| **C** | ChronoCanvas pipeline, no validation/face |
| **D** | ChronoCanvas full pipeline |

## Quick Start

```bash
# Run eval for a single case + condition
python eval/scripts/run_eval.py --case CCV1-001 --condition D

# Export rating packets for human scoring
python eval/scripts/export_rater_packets.py --runs-dir eval/runs --output-dir eval/ratings/packets

# Aggregate results after scoring
python eval/scripts/aggregate_results.py --ratings eval/ratings/ --runs eval/runs/ --output eval/reports/
```

## Pilot-First Approach

Start with a 10-case pilot (Baseline A vs D only, 1 rater) before expanding to the full 30 cases. A partial, honest eval is more credible than a large unfinished benchmark.

## Claim Posture

Use calibrated language:
- "historically informed", "period-plausible", "heuristically validated"
- Never: "historically accurate", "truthful reconstruction", "verified likeness"
