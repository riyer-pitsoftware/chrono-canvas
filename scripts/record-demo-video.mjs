#!/usr/bin/env node
/**
 * Record a <4 min demo video showing ChronoCanvas UI end-to-end.
 *
 * Prerequisites:
 *   - Local stack running (make quickstart)
 *   - cd frontend && npx playwright install chromium
 *   - ffmpeg installed
 *
 * Usage:
 *   node scripts/record-demo-video.mjs
 *   HEADLESS=false node scripts/record-demo-video.mjs  # watch live
 *
 * Output:
 *   docs/videos/demo.webm   (raw Playwright recording)
 *   docs/videos/demo.mp4    (re-encoded H.264, playable everywhere)
 *   docs/videos/demo-2x.mp4 (2x speed for quick viewing)
 */
import { chromium } from "../frontend/node_modules/playwright/index.mjs";
import { execSync } from "child_process";
import { mkdirSync, existsSync, renameSync, unlinkSync } from "fs";
import path from "path";

const FRONTEND_URL = process.env.FRONTEND_URL || "http://localhost:3000";
const OUTPUT_DIR = "docs/videos";
const VIDEO_TMP = "/tmp/chronocanvas-demo";
const VIEWPORT = { width: 1440, height: 900 };
// How long to wait for generation progress before moving on (seconds)
const GEN_WAIT = parseInt(process.env.GEN_WAIT || "120", 10);

/** Click a sidebar nav button by its label text */
async function clickNav(page, label) {
  // Sidebar buttons contain a <span>{label}</span>
  const btn = page.locator(`nav button[title="${label}"]`);
  await btn.waitFor({ state: "visible", timeout: 5000 }).catch(() => {});
  if (await btn.isVisible().catch(() => false)) {
    await btn.click();
    await page.waitForTimeout(1500);
    return true;
  }
  console.log(`  ⚠ Nav button "${label}" not found, skipping`);
  return false;
}

/** Slow-type into a currently-focused input */
async function slowType(locator, text, delayMs = 30) {
  await locator.click();
  await locator.fill(""); // clear first
  for (const char of text) {
    await locator.pressSequentially(char, { delay: delayMs });
  }
}

/** Wait for generation to show progress, then wait a bit to capture it */
async function waitForProgress(page, maxSeconds) {
  console.log(`  Waiting up to ${maxSeconds}s for pipeline progress...`);
  const start = Date.now();
  let sawProgress = false;

  // First wait for the "Generation Progress" card to appear (proves request was created)
  try {
    await page.getByText("Generation Progress").waitFor({ state: "visible", timeout: 15000 });
    console.log("  Generation Progress card appeared");
    sawProgress = true;
  } catch {
    console.log("  Warning: Generation Progress card not found after 15s");
  }

  while ((Date.now() - start) / 1000 < maxSeconds) {
    // Check for running state indicators
    if (!sawProgress) {
      const progressCard = page.getByText("Generation Progress");
      if (await progressCard.isVisible().catch(() => false)) {
        console.log("  Pipeline progress visible!");
        sawProgress = true;
      }
    }

    // If completed or failed, capture and move on
    const done = page.locator('.inline-flex:has-text("completed"), .inline-flex:has-text("failed")');
    if (await done.first().isVisible().catch(() => false)) {
      const text = await done.first().textContent().catch(() => "done");
      console.log(`  Generation ${text}`);
      // Scroll down to show generated image if present
      await page.evaluate(() => window.scrollTo(0, 400));
      await page.waitForTimeout(3000);
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.waitForTimeout(1000);
      return;
    }

    const elapsed = Math.round((Date.now() - start) / 1000);
    if (elapsed % 15 === 0) console.log(`  Still waiting... ${elapsed}s`);
    await page.waitForTimeout(1000);
  }

  if (sawProgress) {
    console.log("  Captured some progress, moving on (timed out)");
    await page.waitForTimeout(2000);
  } else {
    console.log("  No progress seen, moving on");
  }
}

async function main() {
  mkdirSync(OUTPUT_DIR, { recursive: true });
  mkdirSync(VIDEO_TMP, { recursive: true });

  console.log("=== ChronoCanvas Demo Video Recording ===\n");

  const headless = process.env.HEADLESS !== "false";
  console.log(`Headless: ${headless}`);
  console.log(`Frontend: ${FRONTEND_URL}`);
  console.log(`Gen wait: ${GEN_WAIT}s\n`);

  const browser = await chromium.launch({ headless });
  const context = await browser.newContext({
    viewport: VIEWPORT,
    colorScheme: "dark",
    recordVideo: { dir: VIDEO_TMP, size: VIEWPORT },
  });
  const page = await context.newPage();

  // ── Scene 1: Home / Mode Selector ────────────────────────────────
  console.log("[1/8] Home — Mode Selector...");
  await page.goto(FRONTEND_URL, { waitUntil: "networkidle" });
  await page.waitForTimeout(3000);

  // ── Scene 2: Timeline explorer ───────────────────────────────────
  console.log("[2/8] Timeline explorer...");
  if (await clickNav(page, "Timeline")) {
    await page.waitForTimeout(1500);
    // Interact with slider if present
    const slider = page.locator('input[type="range"]');
    if (await slider.isVisible().catch(() => false)) {
      await slider.fill("1400");
      await page.waitForTimeout(1500);
      await slider.fill("800");
      await page.waitForTimeout(1500);
      await slider.fill("200");
      await page.waitForTimeout(1500);
    }
  }

  // ── Scene 3: Figure Library ──────────────────────────────────────
  console.log("[3/8] Figure Library...");
  if (await clickNav(page, "Figures")) {
    await page.waitForTimeout(2000);
    // Scroll to show more figures
    await page.evaluate(() => window.scrollTo(0, 400));
    await page.waitForTimeout(1500);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(1000);
  }

  // ── Scene 4: Portrait mode generation ────────────────────────────
  console.log("[4/8] Portrait mode — Generate...");
  // Use Home mode selector to get clean portrait mode entry
  if (await clickNav(page, "Home")) {
    await page.waitForTimeout(1000);
    const startGen = page.locator('button:has-text("Start Generating")');
    if (await startGen.isVisible().catch(() => false)) {
      await startGen.click();
      await page.waitForTimeout(1500);
    }
  }

  // Now on /generate with portrait mode — type and generate
  const portraitInput = page.locator('input[placeholder*="Describe a historical figure"]');
  if (await portraitInput.isVisible().catch(() => false)) {
    await slowType(portraitInput, "Aryabhata, Indian mathematician, Gupta period, 5th century CE");
    await page.waitForTimeout(500);

    // Click Generate button (inside CardContent, not the sidebar nav)
    const genBtn = page.locator('button:has-text("Generate"):not(nav button)').last();
    if (await genBtn.isVisible().catch(() => false)) {
      await genBtn.click();
      await waitForProgress(page, GEN_WAIT);
    }
  }

  // ── Scene 5: Audit trail ─────────────────────────────────────────
  console.log("[5/8] Audit list + detail...");
  if (await clickNav(page, "Audit")) {
    await page.waitForTimeout(2000);
    // Click first audit entry if table exists
    const firstRow = page.locator("table tbody tr").first();
    if (await firstRow.isVisible().catch(() => false)) {
      await firstRow.click();
      await page.waitForTimeout(2000);
      // Scroll to show LLM calls section
      await page.evaluate(() => window.scrollTo(0, 500));
      await page.waitForTimeout(2000);
      await page.evaluate(() => window.scrollTo(0, 1000));
      await page.waitForTimeout(2000);
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.waitForTimeout(1000);
    }
  }

  // ── Scene 6: Admin dashboard ─────────────────────────────────────
  console.log("[6/8] Admin dashboard...");
  if (await clickNav(page, "Admin")) {
    await page.waitForTimeout(2000);
    // Click through tabs
    for (const tab of ["Validation Rules", "Review Queue"]) {
      const tabBtn = page.locator(`button:has-text("${tab}")`);
      if (await tabBtn.isVisible().catch(() => false)) {
        await tabBtn.click();
        await page.waitForTimeout(2000);
      }
    }
  }

  // ── Scene 7: Story mode generation ───────────────────────────────
  console.log("[7/8] Story mode — Generate...");
  // Navigate via Home mode selector to get story mode
  if (await clickNav(page, "Home")) {
    await page.waitForTimeout(1000);
    const startCreating = page.locator('button:has-text("Start Creating")');
    if (await startCreating.isVisible().catch(() => false)) {
      await startCreating.click();
      await page.waitForTimeout(1500);
    }
  }

  // Now on /generate?mode=creative_story — type and generate
  const storyInput = page.locator('textarea[placeholder*="Paste or write your story"]');
  if (await storyInput.isVisible().catch(() => false)) {
    await slowType(
      storyInput,
      "The night market of 1920s Mumbai comes alive as a street vendor discovers a mysterious compass that points not north, but toward forgotten moments in time."
    );
    await page.waitForTimeout(500);

    const storyBtn = page.locator('button:has-text("Generate Storyboard")');
    if (await storyBtn.isVisible().catch(() => false)) {
      await storyBtn.click();
      await waitForProgress(page, GEN_WAIT);
    }
  }

  // ── Scene 8: Dashboard overview ──────────────────────────────────
  console.log("[8/8] Dashboard overview...");
  if (await clickNav(page, "Dashboard")) {
    await page.waitForTimeout(3000);
  }

  // ── Finalize recording ───────────────────────────────────────────
  const videoPath = await page.video().path();
  await context.close();
  await browser.close();

  console.log(`\nRaw video: ${videoPath}`);

  // Playwright outputs .webm — save with correct extension
  const rawWebm = path.join(OUTPUT_DIR, "demo.webm");
  const rawMp4 = path.join(OUTPUT_DIR, "demo.mp4");
  const speedMp4 = path.join(OUTPUT_DIR, "demo-2x.mp4");

  execSync(`cp "${videoPath}" "${rawWebm}"`);
  console.log(`Saved raw: ${rawWebm}`);

  // Convert webm → mp4 (H.264, universally playable)
  console.log("Converting to MP4...");
  execSync(
    `ffmpeg -y -i "${rawWebm}" -c:v libx264 -preset fast -crf 23 -pix_fmt yuv420p -an "${rawMp4}"`,
    { stdio: "inherit" }
  );

  // Create 2x speed version
  console.log("Creating 2x speed version...");
  execSync(
    `ffmpeg -y -i "${rawMp4}" -filter:v "setpts=0.5*PTS" -an "${speedMp4}"`,
    { stdio: "inherit" }
  );

  const { statSync } = await import("fs");
  const rawSize = (statSync(rawMp4).size / (1024 * 1024)).toFixed(1);
  const speedSize = (statSync(speedMp4).size / (1024 * 1024)).toFixed(1);

  // Clean up webm
  unlinkSync(rawWebm);

  console.log(`\n=== Done ===`);
  console.log(`Raw MP4:  ${rawMp4} (${rawSize} MB)`);
  console.log(`2x MP4:   ${speedMp4} (${speedSize} MB)`);
  console.log(`\nUpload the 2x version to YouTube/Loom and link from README.`);
}

main().catch((err) => {
  console.error("Recording failed:", err.message);
  process.exit(1);
});
