#!/usr/bin/env bash
# deploy-mark.sh — Record that a deploy just happened.
#
# Usage:
#   bash scripts/deploy-mark.sh local          # mark local as deployed
#   bash scripts/deploy-mark.sh remote         # mark remote as deployed
#   bash scripts/deploy-mark.sh remote --url   # mark + fetch Cloud Run URLs
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

STATUS_FILE=".deploy-status.json"
CURRENT_COMMIT="$(git rev-parse --short HEAD)"
NOW="$(date '+%Y-%m-%d %H:%M:%S')"

has_jq() { command -v jq &>/dev/null; }

if ! has_jq; then
  echo "Error: jq is required. Install with: brew install jq"
  exit 1
fi

# Initialize status file if missing
if [ ! -f "$STATUS_FILE" ]; then
  cat > "$STATUS_FILE" <<'JSON'
{
  "local": {
    "last_deployed_commit": null,
    "last_deployed_at": null
  },
  "remote": {
    "last_deployed_commit": null,
    "last_deployed_at": null,
    "deploy_tag": null,
    "api_url": null,
    "frontend_url": null
  }
}
JSON
fi

case "${1:-}" in
  local)
    jq --arg c "$CURRENT_COMMIT" --arg t "$NOW" \
      '.local.last_deployed_commit = $c | .local.last_deployed_at = $t' \
      "$STATUS_FILE" > "${STATUS_FILE}.tmp" && mv "${STATUS_FILE}.tmp" "$STATUS_FILE"
    echo "✔ Marked local deploy: $CURRENT_COMMIT @ $NOW"
    ;;

  remote)
    DEPLOY_TAG="${DEPLOY_TAG:-$CURRENT_COMMIT}"
    API_URL=""
    FRONTEND_URL=""
    MANIFEST_FILE="deploy/cloudrun/.build-manifest.json"

    # Try to fetch Cloud Run URLs
    if [[ "${2:-}" == "--url" ]] || [[ "${2:-}" == "--urls" ]]; then
      if command -v gcloud &>/dev/null; then
        GCP_PROJECT_ID="${GCP_PROJECT_ID:-gen-lang-client-0925647028}"
        GCP_REGION="${GCP_REGION:-us-central1}"
        API_URL="$(gcloud run services describe chronocanvas-api \
          --project "$GCP_PROJECT_ID" --region "$GCP_REGION" \
          --format 'value(status.url)' 2>/dev/null || echo "")"
        FRONTEND_URL="$(gcloud run services describe chronocanvas-frontend \
          --project "$GCP_PROJECT_ID" --region "$GCP_REGION" \
          --format 'value(status.url)' 2>/dev/null || echo "")"
      fi
    fi

    # Merge build manifest if it exists (written by 04-build-push.sh)
    if [ -f "$MANIFEST_FILE" ]; then
      jq --arg c "$CURRENT_COMMIT" --arg t "$NOW" --arg tag "$DEPLOY_TAG" \
         --arg api "$API_URL" --arg fe "$FRONTEND_URL" \
         --slurpfile manifest "$MANIFEST_FILE" \
        '.remote.last_deployed_commit = $c | .remote.last_deployed_at = $t |
         .remote.deploy_tag = $tag |
         .remote.build = $manifest[0] |
         (if $api != "" then .remote.api_url = $api else . end) |
         (if $fe != "" then .remote.frontend_url = $fe else . end)' \
        "$STATUS_FILE" > "${STATUS_FILE}.tmp" && mv "${STATUS_FILE}.tmp" "$STATUS_FILE"
    else
      jq --arg c "$CURRENT_COMMIT" --arg t "$NOW" --arg tag "$DEPLOY_TAG" \
         --arg api "$API_URL" --arg fe "$FRONTEND_URL" \
        '.remote.last_deployed_commit = $c | .remote.last_deployed_at = $t |
         .remote.deploy_tag = $tag |
         (if $api != "" then .remote.api_url = $api else . end) |
         (if $fe != "" then .remote.frontend_url = $fe else . end)' \
        "$STATUS_FILE" > "${STATUS_FILE}.tmp" && mv "${STATUS_FILE}.tmp" "$STATUS_FILE"
    fi

    echo "✔ Marked remote deploy: $CURRENT_COMMIT (tag: $DEPLOY_TAG) @ $NOW"
    [ -n "$API_URL" ] && echo "  API: $API_URL"
    [ -n "$FRONTEND_URL" ] && echo "  Frontend: $FRONTEND_URL"
    if [ -f "$MANIFEST_FILE" ]; then
      echo "  API image:      $(jq -r '.images.api.image' "$MANIFEST_FILE")"
      echo "  API digest:     $(jq -r '.images.api.digest' "$MANIFEST_FILE")"
      echo "  FE image:       $(jq -r '.images.frontend.image' "$MANIFEST_FILE")"
      echo "  FE digest:      $(jq -r '.images.frontend.digest' "$MANIFEST_FILE")"
      echo "  Build commit:   $(jq -r '.git_short' "$MANIFEST_FILE") $(jq -r '.git_message' "$MANIFEST_FILE")"
      echo "  Dirty build:    $(jq -r '.git_dirty' "$MANIFEST_FILE")"
    fi
    ;;

  *)
    echo "Usage: $0 local|remote [--url]"
    echo ""
    echo "  local   — Record that local Docker Compose was redeployed"
    echo "  remote  — Record that Cloud Run was redeployed"
    echo "    --url — Also fetch and save Cloud Run service URLs"
    exit 1
    ;;
esac
