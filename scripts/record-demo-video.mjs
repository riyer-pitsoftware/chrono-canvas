#!/usr/bin/env node
/**
 * Record a <4 min demo video showing both ChronoCanvas modes end-to-end.
 *
 * Prerequisites:
 *   - Local stack running (make quickstart)
 *   - npx playwright install chromium
 *   - ffmpeg installed
 *
 * Usage:
 *   node scripts/record-demo-video.mjs
 *   HEADLESS=false node scripts/record-demo-video.mjs  # watch live
 *
 * Output:
 *   docs/videos/demo.mp4  (raw recording)
 *   docs/videos/demo-2x.mp4  (2x speed, <4 min target)
 */
import { chromium } from "../frontend/node_modules/playwright/index.mjs";
import { execSync } from "child_process";
import { mkdirSync } from "fs";
import path from "path";

const FRONTEND_URL = process.env.FRONTEND_URL || "http://localhost:3000";
const OUTPUT_DIR = "docs/videos";
const VIDEO_TMP = "/tmp/chronocanvas-demo";
const VIEWPORT = { width: 1440, height: 900 };

// Slow-type text for demo effect
async function slowType(page, selector, text, delayMs = 40) {
  const el = page.locator(selector);
  await el.click();
  for (const char of text) {
    await el.pressSequentially(char, { delay: delayMs });
  }
}

async function waitForGeneration(page, timeoutMs = 180_000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const badge = page.locator(
      '.inline-flex:has-text("completed"), .inline-flex:has-text("failed")'
    );
    const isVisible = await badge.first().isVisible().catch(() => false);
    if (isVisible) {
      const text = await badge.first().textContent().catch(() => "unknown");
      console.log(`  Generation ${text}`);
      await page.waitForTimeout(3000);
      return text;
    }
    await page.waitForTimeout(1000);
  }
  console.log("  Generation timed out");
  return "timeout";
}

async function main() {
  mkdirSync(OUTPUT_DIR, { recursive: true });
  mkdirSync(VIDEO_TMP, { recursive: true });

  console.log("=== ChronoCanvas Demo Video Recording ===\n");

  const headless = process.env.HEADLESS !== "false";
  console.log(`Headless: ${headless}`);
  console.log(`Frontend: ${FRONTEND_URL}\n`);

  const browser = await chromium.launch({ headless });
  const context = await browser.newContext({
    viewport: VIEWPORT,
    colorScheme: "dark",
    recordVideo: { dir: VIDEO_TMP, size: VIEWPORT },
  });
  const page = await context.newPage();

  // ── Part 1: Landing page & mode selector ─────────────────────────
  console.log("[1/7] Loading app...");
  await page.goto(FRONTEND_URL, { waitUntil: "networkidle" });
  await page.waitForTimeout(3000);

  // ── Part 2: Timeline explorer ────────────────────────────────────
  console.log("[2/7] Timeline explorer...");
  const timelineBtn = page.locator('nav button:has-text("Timeline"), nav a:has-text("Timeline")');
  if (await timelineBtn.isVisible().catch(() => false)) {
    await timelineBtn.click();
    await page.waitForTimeout(3000);
    // Interact with the timeline slider if visible
    const slider = page.locator('input[type="range"]');
    if (await slider.isVisible().catch(() => false)) {
      await slider.fill("1400");
      await page.waitForTimeout(2000);
      await slider.fill("500");
      await page.waitForTimeout(2000);
    }
  }

  // ── Part 3: Portrait mode generation ─────────────────────────────
  console.log("[3/7] Portrait mode — navigating to Generate...");
  const genBtn = page.locator('nav button:has-text("Generate"), nav a:has-text("Generate")');
  await genBtn.waitFor({ state: "visible", timeout: 10000 });
  await genBtn.click();
  await page.waitForTimeout(2000);

  // Select portrait mode if mode selector is visible
  const portraitCard = page.locator('text=Historical Lens').first();
  if (await portraitCard.isVisible().catch(() => false)) {
    await portraitCard.click();
    await page.waitForTimeout(1000);
  }

  console.log("[3/7] Portrait mode — submitting prompt...");
  const input = page.locator('input[placeholder*="Describe"], textarea[placeholder*="Describe"]');
  await input.waitFor({ state: "visible", timeout: 10000 });
  await slowType(page, 'input[placeholder*="Describe"], textarea[placeholder*="Describe"]',
    "Aryabhata, Indian mathematician and astronomer, Gupta period, 5th century CE");
  await page.waitForTimeout(500);

  const submitBtn = page.locator('button:has-text("Generate")').last();
  await submitBtn.click();
  console.log("[3/7] Portrait mode — waiting for pipeline...");
  await waitForGeneration(page);

  // ── Part 4: Audit trail ──────────────────────────────────────────
  console.log("[4/7] Viewing audit trail...");
  const auditBtn = page.locator('nav button:has-text("Audit"), nav a:has-text("Audit")');
  if (await auditBtn.first().isVisible().catch(() => false)) {
    await auditBtn.first().click();
    await page.waitForTimeout(2000);
    // Click the first audit entry
    const firstRow = page.locator("table tbody tr, [class*='card']").first();
    if (await firstRow.isVisible().catch(() => false)) {
      await firstRow.click();
      await page.waitForTimeout(3000);
      // Scroll down to show LLM calls
      await page.evaluate(() => window.scrollTo(0, 600));
      await page.waitForTimeout(2000);
      await page.evaluate(() => window.scrollTo(0, 0));
    }
  }

  // ── Part 5: Admin dashboard ──────────────────────────────────────
  console.log("[5/7] Admin dashboard...");
  const adminBtn = page.locator('nav button:has-text("Admin"), nav a:has-text("Admin")');
  if (await adminBtn.isVisible().catch(() => false)) {
    await adminBtn.click();
    await page.waitForTimeout(2000);
    // Click validation rules tab if available
    const rulesTab = page.locator('button:has-text("Validation Rules")');
    if (await rulesTab.isVisible().catch(() => false)) {
      await rulesTab.click();
      await page.waitForTimeout(2000);
    }
  }

  // ── Part 6: Story mode generation ────────────────────────────────
  console.log("[6/7] Story mode — navigating...");
  await genBtn.click();
  await page.waitForTimeout(1000);

  // Select story mode if mode selector appears
  const storyCard = page.locator('text=Story Director').first();
  if (await storyCard.isVisible().catch(() => false)) {
    await storyCard.click();
    await page.waitForTimeout(1000);
  }

  const storyInput = page.locator('input[placeholder*="Describe"], textarea[placeholder*="Describe"]');
  if (await storyInput.isVisible().catch(() => false)) {
    await slowType(
      page,
      'input[placeholder*="Describe"], textarea[placeholder*="Describe"]',
      "The night market of 1920s Mumbai comes alive as a street vendor discovers a mysterious compass"
    );
    await page.waitForTimeout(500);
    const storySubmit = page.locator('button:has-text("Generate")').last();
    await storySubmit.click();
    console.log("[6/7] Story mode — waiting for pipeline...");
    await waitForGeneration(page);
  }

  // ── Part 7: Final overview ───────────────────────────────────────
  console.log("[7/7] Final overview — Dashboard...");
  const dashBtn = page.locator('nav button:has-text("Dashboard"), nav a:has-text("Dashboard")');
  if (await dashBtn.isVisible().catch(() => false)) {
    await dashBtn.click();
    await page.waitForTimeout(3000);
  }

  // Finalize
  const videoPath = await page.video().path();
  await context.close();
  await browser.close();

  console.log(`\nRaw video: ${videoPath}`);

  // Speed up 2x and output final MP4
  const rawOut = path.join(OUTPUT_DIR, "demo.mp4");
  const speedOut = path.join(OUTPUT_DIR, "demo-2x.mp4");

  console.log("Copying raw video...");
  execSync(`cp "${videoPath}" "${rawOut}"`);

  console.log("Creating 2x speed version...");
  execSync(
    `ffmpeg -y -i "${rawOut}" -filter:v "setpts=0.5*PTS" -filter:a "atempo=2.0" -an "${speedOut}"`,
    { stdio: "inherit" }
  );

  const { statSync } = await import("fs");
  const rawSize = (statSync(rawOut).size / (1024 * 1024)).toFixed(1);
  const speedSize = (statSync(speedOut).size / (1024 * 1024)).toFixed(1);

  console.log(`\n=== Done ===`);
  console.log(`Raw:   ${rawOut} (${rawSize} MB)`);
  console.log(`2x:    ${speedOut} (${speedSize} MB)`);
  console.log(`\nUpload the 2x version to YouTube/Loom and link from README.`);
}

main().catch((err) => {
  console.error("Recording failed:", err.message);
  process.exit(1);
});
