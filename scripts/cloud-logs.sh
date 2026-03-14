#!/usr/bin/env bash
# Fetch Cloud Run logs for ChronoCanvas debugging.
#
# Usage:
#   bash scripts/cloud-logs.sh [OPTIONS]
#
# Options:
#   --freshness=DURATION  Time window (default: 5m). Examples: 5m, 30m, 1h
#   --severity=LEVEL      Minimum severity (default: all). Examples: WARNING, ERROR
#   --service=NAME        Service filter (default: both). Examples: chronocanvas-api, chronocanvas-frontend
#   --search=TERM         Search for a specific term in results
#   --limit=N             Max log entries (default: 200)
#
# Environment:
#   Sources GCP_PROJECT_ID from .env automatically.
#   Requires gcloud CLI with active auth.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/.logs"
ENV_FILE="$PROJECT_ROOT/.env"

# ── Parse arguments ──────────────────────────────────────────
FRESHNESS="5m"
SEVERITY=""
SERVICE=""
SEARCH=""
LIMIT=200

for arg in "$@"; do
  case "$arg" in
    --freshness=*) FRESHNESS="${arg#--freshness=}" ;;
    --severity=*)  SEVERITY="${arg#--severity=}" ;;
    --service=*)   SERVICE="${arg#--service=}" ;;
    --search=*)    SEARCH="${arg#--search=}" ;;
    --limit=*)     LIMIT="${arg#--limit=}" ;;
    -h|--help)
      head -17 "$0" | tail -15
      exit 0
      ;;
  esac
done

# ── Load environment ─────────────────────────────────────────
if [ -z "${GCP_PROJECT_ID:-}" ]; then
  if [ -f "$ENV_FILE" ]; then
    # Export all non-comment, non-empty lines from .env
    while IFS= read -r line; do
      # Skip comments and blank lines
      [[ "$line" =~ ^#.*$ || -z "$line" ]] && continue
      export "$line" 2>/dev/null || true
    done < "$ENV_FILE"
  fi
fi

if [ -z "${GCP_PROJECT_ID:-}" ]; then
  echo "ERROR: GCP_PROJECT_ID not set and not found in $ENV_FILE" >&2
  exit 1
fi

# ── Ensure output directory ──────────────────────────────────
mkdir -p "$LOG_DIR"

# ── Build filter ─────────────────────────────────────────────
FILTER='resource.type="cloud_run_revision"'

if [ -n "$SERVICE" ]; then
  FILTER="$FILTER AND resource.labels.service_name=\"$SERVICE\""
else
  FILTER="$FILTER AND (resource.labels.service_name=\"chronocanvas-api\" OR resource.labels.service_name=\"chronocanvas-frontend\")"
fi

if [ -n "$SEVERITY" ]; then
  FILTER="$FILTER AND severity>=$SEVERITY"
fi

# ── Fetch logs ───────────────────────────────────────────────
TIMESTAMP=$(date -u +"%Y%m%d_%H%M%S")
OUTFILE="$LOG_DIR/cloudrun_${TIMESTAMP}.json"

echo "Fetching logs: freshness=$FRESHNESS, severity=${SEVERITY:-all}, service=${SERVICE:-both}, limit=$LIMIT"
echo "Filter: $FILTER"
echo ""

gcloud logging read "$FILTER" \
  --project="$GCP_PROJECT_ID" \
  --freshness="$FRESHNESS" \
  --limit="$LIMIT" \
  --format=json \
  > "$OUTFILE" 2>&1

# ── Count and summarize ──────────────────────────────────────
ENTRY_COUNT=$(python3 -c "import json,sys; data=json.load(open('$OUTFILE')); print(len(data))" 2>/dev/null || echo "0")
echo "Fetched $ENTRY_COUNT log entries → $OUTFILE"

if [ "$ENTRY_COUNT" = "0" ]; then
  echo "No logs found in the last $FRESHNESS."
  exit 0
fi

# ── Extract readable summary ─────────────────────────────────
SUMMARY_FILE="$LOG_DIR/cloudrun_${TIMESTAMP}_summary.txt"

python3 -c "
import json, sys

with open('$OUTFILE') as f:
    entries = json.load(f)

for e in entries:
    ts = e.get('timestamp', '?')[:23]
    sev = e.get('severity', '?')
    svc = e.get('resource', {}).get('labels', {}).get('service_name', '?')

    # Extract message from jsonPayload or textPayload
    msg = e.get('textPayload', '')
    if not msg:
        jp = e.get('jsonPayload', {})
        msg = jp.get('message', '')
        if not msg:
            # Try httpRequest
            hr = e.get('httpRequest', {})
            if hr:
                msg = f\"{hr.get('requestMethod','')} {hr.get('requestUrl','')} → {hr.get('status','')}\";

    # Source location if available
    src = e.get('sourceLocation', {})
    loc = ''
    if src:
        loc = f\" [{src.get('file','').split('/')[-1]}:{src.get('line','')}]\"

    print(f'{ts}  {sev:<8} {svc:<25} {msg}{loc}')
" > "$SUMMARY_FILE" 2>&1

echo ""
cat "$SUMMARY_FILE"

# ── Optional search ──────────────────────────────────────────
if [ -n "$SEARCH" ]; then
  echo ""
  echo "=== Search: '$SEARCH' ==="
  grep -i "$SEARCH" "$SUMMARY_FILE" || echo "No matches for '$SEARCH'"
fi

echo ""
echo "Full JSON: $OUTFILE"
echo "Summary:   $SUMMARY_FILE"
