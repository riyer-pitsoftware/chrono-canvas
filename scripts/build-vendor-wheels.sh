#!/usr/bin/env bash
# Build neo-modules wheel into vendor/ for Docker image installs.
# Called by Makefile (neo-wheel target) and Cloud Run build scripts.
set -euo pipefail
VENDOR_DIR="$(cd "$(dirname "$0")/.." && pwd)/vendor"
mkdir -p "$VENDOR_DIR"
pip wheel --no-deps --wheel-dir="$VENDOR_DIR" ../neo-mumbai-noir/
echo "Built: $(ls "$VENDOR_DIR"/neo_modules-*.whl)"
