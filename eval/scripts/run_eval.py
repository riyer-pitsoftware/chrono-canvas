#!/usr/bin/env python3
"""Run evaluation cases under a specified condition.

Usage:
    python eval/scripts/run_eval.py --case CCV1-001 --condition D
    python eval/scripts/run_eval.py --all --condition D
    python eval/scripts/run_eval.py --case CCV1-001 --condition A --seed 12345

Reads case definitions from eval/evalset/cases.yaml and condition configs
from eval/configs/baseline{A-D}.yaml. Stores outputs under eval/runs/<run_id>/.
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="Run ChronoCanvas eval cases")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--case", help="Case ID to run (e.g., CCV1-001)")
    group.add_argument("--all", action="store_true", help="Run all cases")
    parser.add_argument(
        "--condition",
        required=True,
        choices=["A", "B", "C", "D"],
        help="Evaluation condition (A-D)",
    )
    parser.add_argument("--seed", type=int, help="Override seed for reproducibility")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be run without executing",
    )

    args = parser.parse_args()

    # TODO: Implement in history-faces-bm4 (Build run orchestrator)
    # 1. Load cases from eval/evalset/cases.yaml
    # 2. Load condition config from eval/configs/baseline{condition}.yaml
    # 3. For each case:
    #    a. Generate run_id: {timestamp}_{case_id}_{condition}
    #    b. Create eval/runs/{run_id}/ directory
    #    c. Execute generation under the condition config
    #    d. Save run_manifest.json (git commit, config, providers, etc.)
    #    e. Save output.png, output_text.md
    #    f. Save audit_trace.json
    #    g. Run heuristic checks and save heuristics.json
    print(f"run_eval.py: not yet implemented (case={args.case}, condition={args.condition})")
    sys.exit(1)


if __name__ == "__main__":
    main()
