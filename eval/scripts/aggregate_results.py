#!/usr/bin/env python3
"""Aggregate eval ratings and run metrics into summary reports.

Usage:
    python eval/scripts/aggregate_results.py \\
        --ratings eval/ratings/ \\
        --runs eval/runs/ \\
        --output eval/reports/

Merges human ratings CSVs with run manifests to produce:
  - reports/summary.csv   (condition-level aggregates)
  - reports/summary.md    (formatted report)
  - reports/failure-analysis.md
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="Aggregate ChronoCanvas eval results")
    parser.add_argument("--ratings", required=True, help="Directory containing rating CSVs")
    parser.add_argument("--runs", required=True, help="Directory containing run artifacts")
    parser.add_argument("--output", required=True, help="Output directory for reports")

    args = parser.parse_args()

    # TODO: Implement aggregation
    # 1. Load all ratings CSVs from --ratings directory
    # 2. Load run_manifest.json from each run in --runs
    # 3. Merge ratings with run metadata (cost, latency, success, retries)
    # 4. Compute per-condition aggregates:
    #    - success rate
    #    - mean/median rubric scores per dimension
    #    - mean cost, latency
    #    - cost per successful output
    #    - retry distribution
    #    - failure mode distribution
    #    - audit trace completeness rate
    # 5. Compute rubric deltas vs Baseline A
    # 6. Write summary.csv
    # 7. Write summary.md (using template from eval_dump.md §18)
    # 8. Write failure-analysis.md from failure_tags
    print(f"aggregate_results.py: not yet implemented (ratings={args.ratings})")
    sys.exit(1)


if __name__ == "__main__":
    main()
