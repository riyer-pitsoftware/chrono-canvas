#!/usr/bin/env python3
"""Heuristic checks for eval runs — fast, deterministic sanity checks (no LLM calls).

Usage:
    # Single run
    python eval/scripts/heuristics.py eval/runs/<run_id>

    # Multiple runs
    python eval/scripts/heuristics.py eval/runs/*/
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

# Add backend src to path for security imports
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "backend" / "src"))

from chronocanvas.security import validate_image_magic  # noqa: E402

# Minimum acceptable resolution (width, height)
MIN_RESOLUTION = (768, 1024)

# ── OpenCV face detection (optional) ─────────────────────────────────────────

try:
    import cv2

    _CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    _FACE_CASCADE = cv2.CascadeClassifier(_CASCADE_PATH)
    _HAS_OPENCV = True
except ImportError:
    _HAS_OPENCV = False


def _detect_faces(image_path: Path) -> int | None:
    """Return number of faces detected, or None if OpenCV unavailable."""
    if not _HAS_OPENCV:
        return None
    img = cv2.imread(str(image_path))
    if img is None:
        return 0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = _FACE_CASCADE.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
    return len(faces)


# ── Individual check functions ───────────────────────────────────────────────


def check_file_valid(run_dir: Path) -> bool:
    """Check output.png has valid image magic bytes."""
    output = run_dir / "output.png"
    if not output.exists():
        return False
    data = output.read_bytes()
    return validate_image_magic(data)


def check_resolution(run_dir: Path) -> tuple[bool, list[int] | None]:
    """Check output.png meets minimum resolution. Returns (ok, [w, h] or None)."""
    output = run_dir / "output.png"
    if not output.exists():
        return False, None
    try:
        with Image.open(output) as img:
            w, h = img.size
        return (w >= MIN_RESOLUTION[0] and h >= MIN_RESOLUTION[1]), [w, h]
    except Exception:
        return False, None


def check_faces(run_dir: Path) -> tuple[bool | None, int | None]:
    """Detect faces in output.png. Returns (detected, count) — None if opencv missing."""
    output = run_dir / "output.png"
    if not output.exists():
        return None, None
    count = _detect_faces(output)
    if count is None:
        return None, None
    return count > 0, count


def check_audit_event_count(run_dir: Path) -> int:
    """Count events in audit_trace.json agent_trace."""
    audit_path = run_dir / "audit_trace.json"
    if not audit_path.exists():
        return 0
    try:
        audit = json.loads(audit_path.read_text())
        return len(audit.get("agent_trace", []))
    except Exception:
        return 0


def check_retry_count(run_dir: Path) -> int:
    """Count validation entries with passed=False in audit trace."""
    audit_path = run_dir / "audit_trace.json"
    if not audit_path.exists():
        return 0
    try:
        audit = json.loads(audit_path.read_text())
        agent_trace = audit.get("agent_trace", [])
        return sum(
            1 for t in agent_trace
            if t.get("agent") == "validation" and not t.get("passed", True)
        )
    except Exception:
        return 0


def check_latency_ms(run_dir: Path) -> float | None:
    """Extract total_latency_ms from run_manifest.json."""
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.exists():
        return None
    try:
        manifest = json.loads(manifest_path.read_text())
        return manifest.get("total_latency_ms")
    except Exception:
        return None


# ── Main runner ──────────────────────────────────────────────────────────────


def run_heuristics(run_dir: Path) -> dict:
    """Run all heuristic checks on a run directory and write heuristics.json."""
    run_dir = Path(run_dir)

    file_valid = check_file_valid(run_dir)
    resolution_ok, resolution = check_resolution(run_dir)
    face_detected, face_count = check_faces(run_dir)
    audit_event_count = check_audit_event_count(run_dir)
    retry_count = check_retry_count(run_dir)
    latency_ms = check_latency_ms(run_dir)

    checks = {
        "file_valid": file_valid,
        "resolution_ok": resolution_ok,
        "resolution": resolution,
        "face_detected": face_detected,
        "face_count": face_count,
        "audit_event_count": audit_event_count,
        "retry_count": retry_count,
        "latency_ms": latency_ms,
    }

    # passed = all boolean checks that are not None must be True
    boolean_checks = ["file_valid", "resolution_ok", "face_detected"]
    failures = [k for k in boolean_checks if checks[k] is False]
    passed = len(failures) == 0

    result = {
        "run_id": run_dir.name,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "passed": passed,
        "failures": failures,
    }

    (run_dir / "heuristics.json").write_text(json.dumps(result, indent=2))
    return result


# ── CLI ──────────────────────────────────────────────────────────────────────


def main():
    if len(sys.argv) < 2:
        print("Usage: python heuristics.py <run_dir> [<run_dir> ...]", file=sys.stderr)
        sys.exit(1)

    dirs = [Path(d) for d in sys.argv[1:]]
    total_passed = 0
    total = 0

    for run_dir in dirs:
        if not run_dir.is_dir():
            print(f"Skipping {run_dir} (not a directory)")
            continue
        total += 1
        result = run_heuristics(run_dir)
        status = "PASS" if result["passed"] else f"FAIL ({', '.join(result['failures'])})"
        print(f"  {run_dir.name}: {status}")
        if result["passed"]:
            total_passed += 1

    if total:
        print(f"\n{total_passed}/{total} passed")


if __name__ == "__main__":
    main()
