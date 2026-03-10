#!/usr/bin/env bash
# Build neo-modules wheel into vendor/ for Docker image installs.
# Called by Makefile (neo-wheel target) and Cloud Run build scripts.
set -euo pipefail
VENDOR_DIR="$(cd "$(dirname "$0")/.." && pwd)/vendor"
mkdir -p "$VENDOR_DIR"

# Skip rebuild if wheel already exists
if ls "$VENDOR_DIR"/neo_modules-*.whl &>/dev/null; then
  echo "Wheel already exists: $(ls "$VENDOR_DIR"/neo_modules-*.whl)"
  exit 0
fi

NEO_DIR="$(cd "$(dirname "$0")/../../neo-mumbai-noir" 2>/dev/null && pwd)" || true
if [ -z "$NEO_DIR" ] || [ ! -f "$NEO_DIR/pyproject.toml" ]; then
  echo "ERROR: neo-mumbai-noir not found at ../neo-mumbai-noir/ and no pre-built wheel in vendor/"
  exit 1
fi

pip wheel --no-deps --wheel-dir="$VENDOR_DIR" "$NEO_DIR"
echo "Built: $(ls "$VENDOR_DIR"/neo_modules-*.whl)"
