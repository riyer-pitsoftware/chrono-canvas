#!/usr/bin/env bash
# Quick redeploy — build, push, deploy, verify. No infra changes.
#
# Usage:
#   cd /path/to/chrono-canvas
#   export GCP_PROJECT_ID=gen-lang-client-0925647028
#   bash deploy/cloudrun/redeploy.sh
set -euo pipefail
exec bash "$(dirname "$0")/deploy-all.sh" --from=4 --skip-wait "$@"
