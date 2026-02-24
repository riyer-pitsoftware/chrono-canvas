/**
 * Capture README screenshots via Playwright.
 *
 * Prerequisites:
 *   - Full stack running (`make dev`) — API on :8000, frontend on :3000, ComfyUI for image gen
 *   - `cd frontend && npm install` (Playwright is a devDep)
 *
 * Usage:
 *   cd frontend && npx tsx ../scripts/capture-screenshots.ts
 *
 * Produces:
 *   docs/images/generated-portrait.png
 *   docs/images/audit-trail.png
 */

import { chromium } from "@playwright/test";
import { resolve, dirname } from "path";
import { existsSync, mkdirSync } from "fs";

const API_BASE = process.env.API_URL ?? "http://localhost:8000";
const FRONTEND_BASE = process.env.FRONTEND_URL ?? "http://localhost:3000";
const POLL_INTERVAL_MS = 2_000;
const TIMEOUT_MS = 180_000;

const REPO_ROOT = resolve(dirname(import.meta.url.replace("file://", "")), "..");
const OUTPUT_DIR = resolve(REPO_ROOT, "docs/images");

// ── Helpers ─────────────────────────────────────────────────────────────────

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${init?.method ?? "GET"} ${path} → ${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

// ── Main ────────────────────────────────────────────────────────────────────

async function main() {
  // Ensure output directory exists
  if (!existsSync(OUTPUT_DIR)) {
    mkdirSync(OUTPUT_DIR, { recursive: true });
  }

  // 1. Health check
  console.log("Checking API health…");
  try {
    await apiFetch("/health");
  } catch (e) {
    console.error(`API is not reachable at ${API_BASE}. Start the stack first (make dev).`);
    process.exit(1);
  }
  console.log("API is healthy.");

  // 2. Trigger generation
  console.log("Triggering generation…");
  const { id: requestId } = await apiFetch<{ id: string }>("/api/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      input_text: "Aryabhata, 5th-century Indian mathematician and astronomer",
    }),
  });
  console.log(`Generation started: ${requestId}`);

  // 3. Poll for completion
  console.log("Waiting for pipeline to complete (timeout 180s)…");
  const start = Date.now();
  let status = "pending";
  while (Date.now() - start < TIMEOUT_MS) {
    const gen = await apiFetch<{ status: string }>(`/api/generate/${requestId}`);
    status = gen.status;
    if (status === "completed" || status === "failed") break;
    process.stdout.write(".");
    await sleep(POLL_INTERVAL_MS);
  }
  console.log();

  if (status !== "completed") {
    console.error(`Generation did not complete (status: ${status}). Screenshots skipped.`);
    process.exit(1);
  }
  console.log("Generation completed.");

  // 4. Launch Playwright
  console.log("Launching browser…");
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    colorScheme: "dark",
  });
  const page = await context.newPage();

  const auditUrl = `${FRONTEND_BASE}/audit/${requestId}`;
  console.log(`Navigating to ${auditUrl}`);
  await page.goto(auditUrl, { waitUntil: "networkidle" });

  // Wait for content to render
  await page.waitForSelector("text=Audit Detail", { timeout: 15_000 });

  // 5. Screenshot 1 — Portrait (hero section with images, metadata, pipeline stepper)
  console.log("Capturing portrait screenshot…");

  // Wait for images to load
  await page.waitForTimeout(2_000);

  // Capture the top portion: header + pipeline timeline + images
  const portraitPath = resolve(OUTPUT_DIR, "generated-portrait.png");
  await page.screenshot({
    path: portraitPath,
    clip: { x: 0, y: 0, width: 1280, height: 800 },
  });
  console.log(`Saved: ${portraitPath}`);

  // 6. Screenshot 2 — Audit trail (LLM calls + validation)
  console.log("Capturing audit trail screenshot…");

  // Scroll to LLM Calls section
  const llmCallsHeading = page.locator("text=LLM Calls").first();
  if (await llmCallsHeading.isVisible()) {
    await llmCallsHeading.scrollIntoViewIfNeeded();
    await page.waitForTimeout(500);

    // Expand first two LLM call entries for detail
    const callButtons = page.locator(
      'div.border.rounded-md > button.w-full'
    );
    const count = await callButtons.count();
    for (let i = 0; i < Math.min(2, count); i++) {
      await callButtons.nth(i).click();
      await page.waitForTimeout(300);
    }
    await page.waitForTimeout(500);
  }

  // Capture the current viewport (LLM calls area)
  const auditPath = resolve(OUTPUT_DIR, "audit-trail.png");
  await page.screenshot({
    path: auditPath,
    fullPage: false,
  });
  console.log(`Saved: ${auditPath}`);

  await browser.close();
  console.log("Done! Screenshots saved to docs/images/");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
