#!/usr/bin/env python3
"""ChronoCanvas post-deploy smoke test.

Exercises the full generation pipeline end-to-end:
  1. POST /api/generate  — create a portrait request
  2. Poll until completed/failed (timeout 5 min)
  3. GET  /api/generate/{id}/images — verify images exist
  4. GET  /api/generate/{id}/audit  — verify LLM calls recorded

Usage (inside API container):
    python /app/scripts/smoke_test.py

Usage (from host):
    docker exec chrono-canvas-api-1 python /app/scripts/smoke_test.py
"""

from __future__ import annotations

import json
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE_URL = "http://localhost:8000"
TIMEOUT_SECONDS = 300  # 5 minutes
POLL_INTERVAL = 5


def _request(method: str, path: str, body: dict | None = None) -> dict:
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body else None
    req = Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except HTTPError as exc:
        print(f"  HTTP {exc.code}: {exc.read().decode()[:200]}")
        raise


def main() -> int:
    results: list[tuple[str, bool, str]] = []

    # --- Step 1: Create generation request ---
    print("1. Creating generation request...")
    try:
        resp = _request("POST", "/api/generate", {
            "input_text": "Hatshepsut, the pharaoh of ancient Egypt",
            "run_type": "portrait",
        })
        request_id = resp["id"]
        print(f"   Created: {request_id}")
        results.append(("Create request", True, request_id))
    except Exception as exc:
        results.append(("Create request", False, str(exc)))
        _print_summary(results)
        return 1

    # --- Step 2: Poll until completed/failed ---
    print(f"2. Polling status (timeout {TIMEOUT_SECONDS}s)...")
    start = time.time()
    status = "pending"
    while time.time() - start < TIMEOUT_SECONDS:
        try:
            resp = _request("GET", f"/api/generate/{request_id}")
            status = resp.get("status", "unknown")
            agent = resp.get("current_agent", "")
            elapsed = int(time.time() - start)
            print(f"   [{elapsed:3d}s] status={status} agent={agent}")
            if status in ("completed", "failed"):
                break
        except Exception:
            pass
        time.sleep(POLL_INTERVAL)

    if status == "completed":
        results.append(("Pipeline completed", True, f"{int(time.time() - start)}s"))
    elif status == "failed":
        error = resp.get("error_message", "unknown error")
        results.append(("Pipeline completed", False, f"FAILED: {error}"))
        _print_summary(results)
        return 1
    else:
        msg = f"TIMEOUT after {TIMEOUT_SECONDS}s (status={status})"
        results.append(("Pipeline completed", False, msg))
        _print_summary(results)
        return 1

    # --- Step 3: Check images ---
    print("3. Checking images...")
    try:
        images = _request("GET", f"/api/generate/{request_id}/images")
        count = len(images) if isinstance(images, list) else 0
        if count > 0:
            providers = {img.get("provider", "?") for img in images}
            results.append(("Images exist", True, f"{count} image(s), providers={providers}"))
            print(f"   {count} image(s) found, providers={providers}")
        else:
            results.append(("Images exist", False, "0 images returned"))
    except Exception as exc:
        results.append(("Images exist", False, str(exc)))

    # --- Step 4: Check audit trail ---
    print("4. Checking audit trail...")
    try:
        audit = _request("GET", f"/api/generate/{request_id}/audit")
        llm_calls = len(audit.get("llm_calls", []))
        total_cost = audit.get("total_cost", 0.0)
        has_calls = llm_calls > 0
        results.append(("Audit: LLM calls", has_calls, f"{llm_calls} call(s)"))
        results.append(("Audit: costs tracked", total_cost > 0, f"${total_cost:.4f}"))
        print(f"   LLM calls: {llm_calls}, total cost: ${total_cost:.4f}")
    except Exception as exc:
        results.append(("Audit trail", False, str(exc)))

    _print_summary(results)
    return 0 if all(ok for _, ok, _ in results) else 1


def _print_summary(results: list[tuple[str, bool, str]]) -> None:
    print("\n" + "=" * 60)
    print("SMOKE TEST SUMMARY")
    print("=" * 60)
    for name, ok, detail in results:
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}: {detail}")

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\n  {passed}/{total} checks passed")
    if passed == total:
        print("  All checks passed!")
    else:
        print("  Some checks FAILED.")
    print("=" * 60)


if __name__ == "__main__":
    sys.exit(main())
