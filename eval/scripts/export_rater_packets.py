#!/usr/bin/env python3
"""Export rater-friendly scoring packets from completed eval runs.

Usage:
    python eval/scripts/export_rater_packets.py \\
        --runs-dir eval/runs \\
        --output-dir eval/ratings/packets \\
        --blind

Assembles a per-run scoring view containing:
  - Output image
  - Generated text
  - Audit trace summary (if available)
  - Case constraints (must_include, must_not_include, anachronism_watchlist)

With --blind, condition labels are replaced with randomized IDs.
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="Export rater scoring packets")
    parser.add_argument("--runs-dir", required=True, help="Directory containing run artifacts")
    parser.add_argument("--output-dir", required=True, help="Output directory for packets")
    parser.add_argument(
        "--blind",
        action="store_true",
        help="Blind condition labels for unbiased scoring",
    )
    parser.add_argument(
        "--randomize",
        action="store_true",
        help="Randomize presentation order",
    )

    args = parser.parse_args()

    # TODO: Implement packet export
    # 1. Scan --runs-dir for completed runs (those with run_manifest.json)
    # 2. Load case definitions from eval/evalset/cases.yaml
    # 3. For each run:
    #    a. Copy/link output image
    #    b. Include generated text
    #    c. Include audit trace summary
    #    d. Include case constraints for scorer reference
    #    e. If --blind, replace condition label with random ID
    # 4. If --randomize, shuffle presentation order
    # 5. Generate index/manifest for the packet set
    # 6. Copy ratings_template.csv into output directory
    print(f"export_rater_packets.py: not yet implemented (runs={args.runs_dir})")
    sys.exit(1)


if __name__ == "__main__":
    main()
