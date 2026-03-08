#!/usr/bin/env bash
# deploy-status.sh — Show what changed and what needs redeploying.
#
# Usage:
#   bash scripts/deploy-status.sh          # full status
#   bash scripts/deploy-status.sh local    # local only
#   bash scripts/deploy-status.sh remote   # remote only
#
# Reads .deploy-status.json for last-deployed state.
# After deploying, run: bash scripts/deploy-mark.sh local|remote
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

STATUS_FILE=".deploy-status.json"
CURRENT_COMMIT="$(git rev-parse --short HEAD)"
CURRENT_BRANCH="$(git branch --show-current)"

# ── Helpers ──────────────────────────────────────────────────────────
has_jq() { command -v jq &>/dev/null; }
has_gcloud() { command -v gcloud &>/dev/null; }

read_field() {
  local field="$1"
  if [ -f "$STATUS_FILE" ] && has_jq; then
    jq -r "$field // empty" "$STATUS_FILE" 2>/dev/null
  fi
}

# Figure out which services are affected by a set of changed files
classify_changes() {
  local files="$1"
  local needs_api=false needs_worker=false needs_frontend=false needs_neo=false
  local needs_docker=false needs_deploy=false needs_db=false

  while IFS= read -r f; do
    [ -z "$f" ] && continue
    case "$f" in
      backend/src/chronocanvas/worker*|backend/src/chronocanvas/pipelines/*|backend/src/chronocanvas/agents/*)
        needs_worker=true; needs_api=true ;;
      backend/src/chronocanvas/api/*|backend/src/chronocanvas/main.py|backend/src/chronocanvas/config.py)
        needs_api=true ;;
      backend/src/chronocanvas/*)
        needs_api=true; needs_worker=true ;;
      backend/alembic/*|backend/migrations/*)
        needs_db=true; needs_api=true ;;
      backend/pyproject.toml|backend/requirements*.txt)
        needs_api=true; needs_worker=true ;;
      frontend/src/*|frontend/public/*|frontend/index.html|frontend/package.json|frontend/vite.config.*)
        needs_frontend=true ;;
      docker/*|Dockerfile*|docker-compose*)
        needs_docker=true ;;
      deploy/cloudrun/*|deploy/gke/*)
        needs_deploy=true ;;
      neo-mumbai-noir/*|vendor/*)
        needs_neo=true; needs_api=true; needs_worker=true ;;
      .env|.env.*)
        needs_api=true; needs_worker=true; needs_frontend=true ;;
    esac
  done <<< "$files"

  local services=()
  $needs_api && services+=("api")
  $needs_worker && services+=("worker")
  $needs_frontend && services+=("frontend")
  $needs_db && services+=("db-migrate")
  $needs_neo && services+=("neo-wheel")
  $needs_docker && services+=("docker-rebuild")
  $needs_deploy && services+=("deploy-config")

  echo "${services[*]:-none}"
}

# ── Header ───────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════"
echo "  ChronoCanvas Deploy Status"
echo "═══════════════════════════════════════════════════════"
echo "  Branch:  $CURRENT_BRANCH"
echo "  HEAD:    $CURRENT_COMMIT ($(git log -1 --format='%s' HEAD))"
echo "  Dirty:   $(git diff --quiet && git diff --cached --quiet && echo 'no' || echo 'YES — uncommitted changes')"
echo ""

# ── Check for uncommitted changes ────────────────────────────────────
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "  ⚠  Uncommitted changes detected. Commit before deploying."
  echo ""
  UNCOMMITTED_FILES="$(git diff --name-only; git diff --cached --name-only)"
  UNCOMMITTED_SERVICES="$(classify_changes "$UNCOMMITTED_FILES")"
  echo "  Uncommitted changes affect: $UNCOMMITTED_SERVICES"
  echo ""
fi

# ── LOCAL STATUS ─────────────────────────────────────────────────────
show_local() {
  echo "───────────────────────────────────────────────────────"
  echo "  LOCAL (Docker Compose)"
  echo "───────────────────────────────────────────────────────"

  local last_commit
  last_commit="$(read_field '.local.last_deployed_commit')"
  local last_time
  last_time="$(read_field '.local.last_deployed_at')"

  if [ -z "$last_commit" ]; then
    echo "  Last deployed:  never"
    echo "  Status:         ⚠  No deployment recorded"
    echo ""
    echo "  → Deploy:  make up   (auto-marks on success)"
  else
    echo "  Last deployed:  $last_commit @ $last_time"

    if [ "$last_commit" = "$CURRENT_COMMIT" ]; then
      echo "  Status:         ✔  Up to date"
    else
      local changed_files
      changed_files="$(git diff --name-only "$last_commit"..HEAD 2>/dev/null || echo "")"
      local commit_count
      commit_count="$(git rev-list --count "$last_commit"..HEAD 2>/dev/null || echo "?")"

      if [ -z "$changed_files" ]; then
        echo "  Status:         ⚠  Can't diff (commit $last_commit not found)"
        echo "  → Deploy:  make restart"
      else
        local services
        services="$(classify_changes "$changed_files")"
        echo "  Status:         ✘  $commit_count commit(s) behind"
        echo "  Changed:        $services"
        echo ""

        # Show the commits
        echo "  Commits since last deploy:"
        git log --oneline "$last_commit"..HEAD | sed 's/^/    /'
        echo ""

        # Give specific advice
        if [[ "$services" == *"docker-rebuild"* ]] || [[ "$services" == *"neo-wheel"* ]]; then
          echo "  → Deploy:  make restart   (full rebuild needed)"
        elif [[ "$services" == *"db-migrate"* ]]; then
          echo "  → Deploy:  make restart && make migrate"
        elif [[ "$services" == *"api"* ]] || [[ "$services" == *"worker"* ]]; then
          echo "  → Deploy:  containers auto-reload via bind mounts (dev mode)"
          echo "             OR make restart (if deps changed)"
        elif [[ "$services" == *"frontend"* ]]; then
          echo "  → Deploy:  frontend auto-reloads via Vite HMR (dev mode)"
        else
          echo "  → Deploy:  make restart"
        fi
      fi
    fi
    echo ""

    # Show running containers
    echo "  Running containers:"
    if docker compose -f docker-compose.dev.yml ps --format '{{.Service}}\t{{.Status}}' 2>/dev/null | grep -q .; then
      docker compose -f docker-compose.dev.yml ps --format '{{.Service}}\t{{.Status}}' 2>/dev/null | sed 's/^/    /'
    else
      echo "    (none running)"
    fi
  fi
  echo ""
  echo "  (auto-marked on make up / make restart)"
  echo ""
}

# ── REMOTE STATUS ────────────────────────────────────────────────────
show_remote() {
  echo "───────────────────────────────────────────────────────"
  echo "  REMOTE (Cloud Run)"
  echo "───────────────────────────────────────────────────────"

  local last_commit
  last_commit="$(read_field '.remote.last_deployed_commit')"
  local last_time
  last_time="$(read_field '.remote.last_deployed_at')"
  local deploy_tag
  deploy_tag="$(read_field '.remote.deploy_tag')"
  local api_url
  api_url="$(read_field '.remote.api_url')"
  local frontend_url
  frontend_url="$(read_field '.remote.frontend_url')"

  if [ -z "$last_commit" ]; then
    echo "  Last deployed:  never"
    echo "  Status:         ⚠  No deployment recorded"
    echo ""
    echo "  → First deploy (full infra + services):"
    echo "       export GCP_PROJECT_ID=gen-lang-client-0925647028"
    echo "       bash deploy/cloudrun/deploy-all.sh && bash scripts/deploy-mark.sh remote --url"
    echo "  → Subsequent deploys:  make deploy-remote  (auto-marks)"
  else
    echo "  Last deployed:  $last_commit @ $last_time"
    [ -n "$deploy_tag" ] && echo "  Image tag:      $deploy_tag"
    [ -n "$api_url" ] && echo "  API:            $api_url"
    [ -n "$frontend_url" ] && echo "  Frontend:       $frontend_url"

    if [ "$last_commit" = "$CURRENT_COMMIT" ]; then
      echo "  Status:         ✔  Up to date"
    else
      local changed_files
      changed_files="$(git diff --name-only "$last_commit"..HEAD 2>/dev/null || echo "")"
      local commit_count
      commit_count="$(git rev-list --count "$last_commit"..HEAD 2>/dev/null || echo "?")"

      if [ -z "$changed_files" ]; then
        echo "  Status:         ⚠  Can't diff (commit $last_commit not found)"
      else
        local services
        services="$(classify_changes "$changed_files")"
        echo "  Status:         ✘  $commit_count commit(s) behind"
        echo "  Needs update:   $services"
        echo ""

        echo "  Commits since last deploy:"
        git log --oneline "$last_commit"..HEAD | sed 's/^/    /'
        echo ""

        # Specific advice for remote
        if [[ "$services" == *"deploy-config"* ]]; then
          echo "  → Deploy:  bash deploy/cloudrun/deploy-all.sh --from=5"
          echo "             (deploy config changed — re-run service deploy)"
        elif [[ "$services" == *"api"* ]] || [[ "$services" == *"worker"* ]] || [[ "$services" == *"frontend"* ]]; then
          echo "  → Deploy:  bash deploy/cloudrun/redeploy.sh"
          echo "             (builds images, pushes, deploys services)"
        else
          echo "  → Deploy:  bash deploy/cloudrun/redeploy.sh"
        fi
      fi
    fi
  fi
  echo ""
  echo "  (auto-marked on make deploy-remote)"
  echo ""
}

# ── QUICK REFERENCE ──────────────────────────────────────────────────
show_cheatsheet() {
  echo "───────────────────────────────────────────────────────"
  echo "  CHEAT SHEET"
  echo "───────────────────────────────────────────────────────"
  echo ""
  echo "  Local (dev mode, hot reload):"
  echo "    make up                          # start/rebuild, auto-marks"
  echo "    make restart                     # full restart, auto-marks"
  echo "    make health                      # check services"
  echo "    make smoke-test                  # end-to-end test"
  echo ""
  echo "  Remote (Cloud Run):"
  echo "    make deploy-remote               # build+push+deploy, auto-marks"
  echo ""
  echo "  Status is tracked automatically — no manual steps needed."
  echo ""
}

# ── Main ─────────────────────────────────────────────────────────────
case "${1:-all}" in
  local)  show_local ;;
  remote) show_remote ;;
  all)    show_local; show_remote; show_cheatsheet ;;
  *)      echo "Usage: $0 [local|remote|all]"; exit 1 ;;
esac
