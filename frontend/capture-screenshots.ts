/**
 * Capture README screenshots via Playwright.
 *
 * Prerequisites:
 *   - Full stack running (`make dev`) — API on :8000, frontend on :3000
 *   - `cd frontend && npm install` (Playwright is a devDep)
 *   - Chromium browser installed: `cd frontend && npx playwright install chromium`
 *
 * Usage:
 *   cd frontend && npm run capture-screenshots
 *   cd frontend && npm run capture-screenshots -- --request-id <existing-id>
 *
 * Produces:
 *   docs/images/generated-portrait.png
 *   docs/images/audit-trail.png
 */

import { chromium } from "playwright";
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

  // Parse --request-id from CLI args
  const requestIdArg = (() => {
    const idx = process.argv.indexOf("--request-id");
    return idx !== -1 && process.argv[idx + 1] ? process.argv[idx + 1] : null;
  })();

  // 1. Health check
  console.log("Checking API health…");
  try {
    await apiFetch("/api/health");
  } catch {
    console.error(`API is not reachable at ${API_BASE}. Start the stack first (make dev).`);
    process.exit(1);
  }
  console.log("API is healthy.");

  let requestId: string;

  if (requestIdArg) {
    // Use existing generation
    requestId = requestIdArg;
    console.log(`Using existing generation: ${requestId}`);
    const gen = await apiFetch<{ status: string }>(`/api/generate/${requestId}`);
    if (gen.status !== "completed") {
      console.error(`Generation ${requestId} is not completed (status: ${gen.status}).`);
      process.exit(1);
    }
  } else {
    // 2. Trigger new generation
    console.log("Triggering generation…");
    const { id } = await apiFetch<{ id: string }>("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        input_text: "Aryabhata, 5th-century Indian mathematician and astronomer",
      }),
    });
    requestId = id;
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

  // Load the SPA then navigate client-side (Zustand router doesn't read URL path)
  console.log(`Loading app and navigating to audit detail for ${requestId}`);
  await page.goto(FRONTEND_BASE, { waitUntil: "networkidle", timeout: 30_000 });

  // Wait for dashboard to render
  await page.waitForSelector("text=Dashboard", { timeout: 10_000 });

  // Click Audit in sidebar
  await page.locator("nav >> text=Audit").click();
  await page.waitForTimeout(1_500);

  // On the audit list page, find our request and click it
  // The audit list shows request IDs — look for the first few chars
  const shortId = requestId.slice(0, 8);
  const auditRow = page.locator(`text=${shortId}`).first();
  if (await auditRow.isVisible({ timeout: 5_000 }).catch(() => false)) {
    await auditRow.click();
  } else {
    // Fallback: go back to dashboard, click the generation by name
    console.log("Request not found in audit list, trying dashboard…");
    await page.locator("nav >> text=Dashboard").click();
    await page.waitForTimeout(1_000);
    // Click "Leonardo da Vinci" (or the first completed generation)
    const genLink = page.locator("text=Leonardo da Vinci").first();
    if (await genLink.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await genLink.click();
    }
  }

  await page.waitForTimeout(2_000);

  // Verify we're on audit detail
  const onAuditPage = await page.locator("text=Audit Detail").isVisible().catch(() => false);
  if (!onAuditPage) {
    console.log("Warning: Could not navigate to audit detail page. Taking screenshot anyway.");
  }

  // 5. Screenshot 1 — Portrait (Generated Images section with context)
  console.log("Capturing portrait screenshot…");

  // Scroll to Generated Images section
  const imagesHeading = page.locator("text=Generated Images").first();
  if (await imagesHeading.isVisible({ timeout: 5_000 }).catch(() => false)) {
    await imagesHeading.scrollIntoViewIfNeeded();
    await page.waitForTimeout(2_000); // let images load

    // Scroll up a bit to include the Validation section above for context
    await page.evaluate(() => window.scrollBy(0, -200));
    await page.waitForTimeout(500);
  } else {
    console.log("Warning: Generated Images section not found, capturing top of page.");
  }

  const portraitPath = resolve(OUTPUT_DIR, "generated-portrait.png");
  await page.screenshot({
    path: portraitPath,
    fullPage: false,
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
