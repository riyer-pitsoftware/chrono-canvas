#!/usr/bin/env node
/**
 * Record a single portrait generation and convert to GIF for README.
 *
 * Prerequisites:
 *   - Local stack running (make quickstart)
 *   - cd frontend && npx playwright install chromium
 *   - ffmpeg installed
 *
 * Usage:
 *   node scripts/record-pipeline-gif.mjs
 *   HEADLESS=false node scripts/record-pipeline-gif.mjs  # watch live
 *
 * Output:
 *   docs/images/pipeline-run.gif (3x speed, 720px wide, dark mode)
 */
import { chromium } from "../frontend/node_modules/playwright/index.mjs";
import { execSync } from "child_process";
import { mkdirSync, statSync, unlinkSync } from "fs";
import path from "path";

const FRONTEND_URL = process.env.FRONTEND_URL || "http://localhost:3000";
const OUTPUT_DIR = "docs/images";
const VIDEO_TMP = "/tmp/chronocanvas-gif";
const VIEWPORT = { width: 1280, height: 720 };
const GEN_WAIT = parseInt(process.env.GEN_WAIT || "90", 10);
const OUTPUT_GIF = path.join(OUTPUT_DIR, "pipeline-run.gif");

async function clickNav(page, label) {
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

async function slowType(locator, text, delayMs = 40) {
  await locator.click();
  await locator.fill("");
  for (const char of text) {
    await locator.pressSequentially(char, { delay: delayMs });
  }
}

async function main() {
  mkdirSync(OUTPUT_DIR, { recursive: true });
  mkdirSync(VIDEO_TMP, { recursive: true });

  console.log("=== ChronoCanvas Pipeline GIF Recording ===\n");

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

  // Load SPA
  console.log("Loading app...");
  await page.goto(FRONTEND_URL, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);

  // Navigate to Generate → Historical Lens
  console.log("Navigating to Generate...");
  if (!(await clickNav(page, "Generate"))) {
    throw new Error("Could not find Generate nav button");
  }

  // Pick Historical Lens if mode selector shows
  const portraitCard = page.locator("text=Historical Lens").first();
  if (await portraitCard.isVisible().catch(() => false)) {
    await portraitCard.click();
    await page.waitForTimeout(1500);
  }

  // Type the prompt
  const input = page.locator('input[placeholder*="Describe a historical figure"]');
  await input.waitFor({ state: "visible", timeout: 5000 });
  await slowType(input, "Hypatia of Alexandria, mathematician and philosopher, 4th century CE");
  await page.waitForTimeout(500);

  // Click Generate
  console.log("Starting generation...");
  const genBtn = page.locator('button:has-text("Generate Portrait"), button:has-text("Generate")').last();
  await genBtn.click();

  // Wait for pipeline to complete
  console.log(`Waiting up to ${GEN_WAIT}s for pipeline...`);
  const start = Date.now();
  let completed = false;

  while ((Date.now() - start) / 1000 < GEN_WAIT) {
    const done = page.locator('.inline-flex:has-text("completed"), .inline-flex:has-text("failed")');
    if (await done.first().isVisible().catch(() => false)) {
      const status = await done.first().textContent().catch(() => "done");
      console.log(`  Pipeline ${status}!`);
      completed = true;
      await page.waitForTimeout(4000);
      await page.evaluate(() => window.scrollTo(0, 600));
      await page.waitForTimeout(3000);
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.waitForTimeout(1000);
      break;
    }
    await page.waitForTimeout(1000);
  }

  if (!completed) {
    console.log("  Generation did not complete in time, using what we have");
    await page.waitForTimeout(2000);
  }

  // Stop recording
  const videoPath = await page.video().path();
  await context.close();
  await browser.close();

  console.log(`\nRaw video: ${videoPath}`);

  // Convert webm → GIF at 3x speed, 720px wide (two-pass for quality)
  const palette = "/tmp/chronocanvas-palette.png";

  console.log("Generating palette...");
  execSync(
    `ffmpeg -y -i "${videoPath}" -vf "setpts=0.333*PTS,fps=12,scale=720:-1:flags=lanczos,palettegen=stats_mode=diff" "${palette}"`,
    { stdio: "inherit" }
  );

  console.log("Converting to GIF...");
  execSync(
    `ffmpeg -y -i "${videoPath}" -i "${palette}" -lavfi "setpts=0.333*PTS,fps=12,scale=720:-1:flags=lanczos [x]; [x][1:v] paletteuse=dither=bayer:bayer_scale=5" "${OUTPUT_GIF}"`,
    { stdio: "inherit" }
  );

  // Check size — re-encode at lower fps if > 5MB
  let gifSize = statSync(OUTPUT_GIF).size / (1024 * 1024);
  if (gifSize > 5) {
    console.log(`GIF is ${gifSize.toFixed(1)}MB (>5MB), re-encoding at 8fps...`);
    execSync(
      `ffmpeg -y -i "${videoPath}" -i "${palette}" -lavfi "setpts=0.333*PTS,fps=8,scale=720:-1:flags=lanczos [x]; [x][1:v] paletteuse=dither=bayer:bayer_scale=5" "${OUTPUT_GIF}"`,
      { stdio: "inherit" }
    );
    gifSize = statSync(OUTPUT_GIF).size / (1024 * 1024);
  }

  // Clean up
  try { unlinkSync(palette); } catch {}

  console.log(`\n=== Done ===`);
  console.log(`GIF: ${OUTPUT_GIF} (${gifSize.toFixed(1)} MB)`);
}

main().catch((err) => {
  console.error("Recording failed:", err.message);
  process.exit(1);
});
