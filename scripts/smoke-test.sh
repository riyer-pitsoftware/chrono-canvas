#!/usr/bin/env bash
# smoke-test.sh — Verify a running ChronoCanvas instance passes cold-start checks
# Usage: bash scripts/smoke-test.sh
# Exit code 0 = all checks pass, 1 = failure
set -euo pipefail

PASS=0
FAIL=0

green() { printf "\033[32m  ✔ %s\033[0m\n" "$*"; }
red()   { printf "\033[31m  ✘ %s\033[0m\n" "$*"; }
bold()  { printf "\033[1m%s\033[0m\n" "$*"; }

check() {
    local desc="$1"
    shift
    if "$@" >/dev/null 2>&1; then
        green "$desc"
        PASS=$((PASS + 1))
    else
        red "$desc"
        FAIL=$((FAIL + 1))
    fi
}

bold "ChronoCanvas — Smoke Test"
echo ""

# ── API health ────────────────────────────────────────────────────────
check "API /api/health returns 200" \
    curl -sf http://localhost:8000/api/health

# ── OpenAPI docs ──────────────────────────────────────────────────────
check "Swagger docs available at /docs" \
    curl -sf http://localhost:8000/docs

# ── Seed data loaded (figures endpoint) ───────────────────────────────
check "GET /api/figures returns data" \
    bash -c 'curl -sf http://localhost:8000/api/figures | python3 -c "import sys,json; d=json.load(sys.stdin); assert len(d)>0"'

# ── Seed data loaded (periods endpoint) ───────────────────────────────
check "GET /api/periods returns data" \
    bash -c 'curl -sf http://localhost:8000/api/periods | python3 -c "import sys,json; d=json.load(sys.stdin); assert len(d)>0"'

# ── Frontend serves HTML ──────────────────────────────────────────────
check "Frontend returns HTML at :3000" \
    bash -c 'curl -sf http://localhost:3000 | grep -q "</html>"'

# ── WebSocket endpoint responds ───────────────────────────────────────
check "WebSocket upgrade path exists (/ws)" \
    bash -c 'curl -sf -o /dev/null -w "%{http_code}" http://localhost:8000/ws 2>&1 | grep -qE "4[0-9]{2}"'

# ── Generation endpoint accepts POST ─────────────────────────────────
check "POST /api/generate returns 200/201" \
    bash -c 'curl -sf -X POST http://localhost:8000/api/generate -H "Content-Type: application/json" -d "{\"input_text\":\"Leonardo da Vinci, Renaissance painter\"}" -o /dev/null -w "%{http_code}" | grep -qE "2[0-9]{2}"'

# ── Docker containers healthy ────────────────────────────────────────
check "All docker compose services are running" \
    bash -c 'docker compose -f docker-compose.dev.yml ps --format json | python3 -c "
import sys, json
lines = sys.stdin.read().strip().split(chr(10))
services = [json.loads(l) for l in lines if l.strip()]
assert len(services) >= 4, f\"Expected >=4 services, got {len(services)}\"
for s in services:
    state = s.get(\"State\", \"\")
    assert state == \"running\", f\"{s.get(\"Name\")}: {state}\"
"'

# ── Summary ───────────────────────────────────────────────────────────
echo ""
bold "Results: ${PASS} passed, ${FAIL} failed"

if [ "$FAIL" -gt 0 ]; then
    echo ""
    red "Some checks failed. Run 'make logs' to investigate."
    exit 1
else
    green "All smoke tests passed!"
    exit 0
fi
