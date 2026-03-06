#!/usr/bin/env bash
# Master deployment script — runs all steps in sequence with monitoring.
#
# Usage:
#   cd /path/to/chrono-canvas
#   export GCP_PROJECT_ID=gen-lang-client-0925647028
#   bash deploy/cloudrun/deploy-all.sh [--from=STEP] [--tag=TAG] [--dry-run]
#
# Options:
#   --from=N     Start from step N (e.g., --from=4 to skip infra setup)
#   --tag=TAG    Use a specific image tag (overrides git HEAD / state file)
#   --dry-run    Print what would run without executing
#   --skip-wait  Don't pause between steps (for CI)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/scripts" && pwd)"
FROM_STEP=1
DRY_RUN=false
SKIP_WAIT=false

for arg in "$@"; do
  case "$arg" in
    --from=*) FROM_STEP="${arg#--from=}" ;;
    --tag=*) export DEPLOY_TAG="${arg#--tag=}" ;;
    --dry-run) DRY_RUN=true ;;
    --skip-wait) SKIP_WAIT=true ;;
  esac
done

STEPS=(
  "01-enable-apis.sh:Enable GCP APIs:60"
  "02-create-infra.sh:Create infrastructure (Cloud SQL, Redis, VPC):0"
  "03-setup-secrets.sh:Set up Secret Manager secrets:0"
  "04-build-push.sh:Build and push Docker images:0"
  "05-deploy-services.sh:Deploy Cloud Run services:0"
  "06-verify.sh:Verify deployment:0"
)

total=${#STEPS[@]}
passed=0
failed=0
skipped=0

log()   { echo "$(date '+%H:%M:%S') | $*"; }
ok()    { echo "$(date '+%H:%M:%S') | ✅ $*"; }
fail()  { echo "$(date '+%H:%M:%S') | ❌ $*"; }
info()  { echo "$(date '+%H:%M:%S') | ℹ️  $*"; }

banner() {
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "  STEP $1/$total — $2"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

run_step() {
  local script="$1"
  local desc="$2"
  local wait_after="$3"
  local step_num="${script:0:2}"
  local step_int=$((10#$step_num))

  if [ "$step_int" -lt "$FROM_STEP" ]; then
    info "Skipping step $step_num ($desc)"
    skipped=$((skipped + 1))
    return 0
  fi

  banner "$step_num" "$desc"

  if [ "$DRY_RUN" = true ]; then
    info "[dry-run] Would run: bash ${SCRIPT_DIR}/${script}"
    skipped=$((skipped + 1))
    return 0
  fi

  local start_time=$SECONDS
  local log_file="/tmp/cloudrun-deploy-step-${step_num}.log"

  # Run the step, tee to log and stdout
  if bash "${SCRIPT_DIR}/${script}" 2>&1 | tee "$log_file"; then
    local elapsed=$(( SECONDS - start_time ))
    ok "$desc (${elapsed}s)"
    passed=$((passed + 1))

    # Wait for API propagation if needed
    if [ "$wait_after" -gt 0 ] && [ "$SKIP_WAIT" = false ]; then
      echo ""
      info "Waiting ${wait_after}s for API propagation..."
      sleep "$wait_after"
    fi
  else
    local elapsed=$(( SECONDS - start_time ))
    fail "$desc (${elapsed}s)"
    failed=$((failed + 1))
    echo ""
    fail "Step $step_num failed. Log: $log_file"
    fail "Fix the issue and resume with: bash deploy/cloudrun/deploy-all.sh --from=$step_int"
    return 1
  fi
}

# ── Pre-flight checks ────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  ChronoCanvas Cloud Run — Full Deployment               ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  Project:  ${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}        "
echo "║  Region:   ${GCP_REGION:-us-central1}                   "
echo "║  Tag:      ${DEPLOY_TAG:-<auto>}                        "
echo "║  Starting: step ${FROM_STEP}                            "
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

if [ "$DRY_RUN" = true ]; then
  info "DRY RUN — no commands will be executed"
fi

# Check gcloud auth
if ! gcloud auth list --format="value(account)" 2>/dev/null | head -1 | grep -q '@'; then
  fail "Not authenticated with gcloud. Run: gcloud auth login"
  exit 1
fi
ok "gcloud authenticated as $(gcloud auth list --format='value(account)' 2>/dev/null | head -1)"

# Check Docker
if ! docker info &>/dev/null; then
  fail "Docker is not running. Start Docker Desktop first."
  exit 1
fi
ok "Docker is running"
echo ""

# ── Run steps ────────────────────────────────────────────────────────
DEPLOY_START=$SECONDS

for step in "${STEPS[@]}"; do
  IFS=':' read -r script desc wait_after <<< "$step"
  run_step "$script" "$desc" "$wait_after" || exit 1
done

# ── Secrets reminder ─────────────────────────────────────────────────
if [ "$FROM_STEP" -le 3 ] && [ "$DRY_RUN" = false ]; then
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "  ⚠️  REMINDER: Set your real API keys if you haven't yet!"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  echo "  echo -n 'YOUR_KEY' | gcloud secrets versions add chronocanvas-google-api-key --data-file=-"
  echo "  echo -n 'YOUR_KEY' | gcloud secrets versions add chronocanvas-anthropic-api-key --data-file=-"
fi

# ── Summary ──────────────────────────────────────────────────────────
total_time=$(( SECONDS - DEPLOY_START ))
echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Deployment Summary                                      ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  ✅ Passed:  ${passed}                                  "
echo "║  ⏭  Skipped: ${skipped}                                 "
echo "║  ❌ Failed:  ${failed}                                  "
echo "║  ⏱  Time:    ${total_time}s                             "
echo "╚══════════════════════════════════════════════════════════╝"

if [ "$failed" -gt 0 ]; then
  exit 1
fi
