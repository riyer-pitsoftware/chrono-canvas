#!/usr/bin/env node
/**
 * Record a pipeline run GIF for the README.
 *
 * Prerequisites:
 *   - Local stack running (make dev + make frontend)
 *   - npx playwright install chromium
 *   - ffmpeg installed
 *
 * Usage:
 *   node scripts/record-pipeline-gif.mjs
 *
 * Output:
 *   docs/images/pipeline-run.gif
 */
import { chromium } from "../frontend/node_modules/playwright/index.mjs";
import { execSync } from "child_process";
import { mkdirSync, existsSync } from "fs";
import path from "path";

const FRONTEND_URL = process.env.FRONTEND_URL || "http://localhost:3000";
const OUTPUT_DIR = "docs/images";
const VIDEO_PATH = "/tmp/chronocanvas-recording";
const GIF_PATH = path.join(OUTPUT_DIR, "pipeline-run.gif");
const VIEWPORT = { width: 1280, height: 800 };

async function main() {
  mkdirSync(OUTPUT_DIR, { recursive: true });

  console.log("Launching browser...");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: VIEWPORT,
    recordVideo: {
      dir: VIDEO_PATH,
      size: VIEWPORT,
    },
  });
  const page = await context.newPage();

  // Navigate to home / generate page
  console.log("Navigating to app...");
  await page.goto(FRONTEND_URL, { waitUntil: "networkidle" });
  await page.waitForTimeout(1000);

  // Navigate to Generate page
  console.log("Navigating to Generate page...");
  const genLink = page.locator('a:has-text("Generate"), button:has-text("Generate"), [href="/generate"]').first();
  await genLink.click().catch(() => {
    // If no nav link, try direct URL
    return page.goto(`${FRONTEND_URL}/generate`, { waitUntil: "networkidle" });
  });
  await page.waitForTimeout(1000);

  // Look for the input and submit a prompt
  console.log("Starting generation...");
  const input = page.locator('input[placeholder*="Describe"], input[placeholder*="historical"]').first();
  await input.waitFor({ state: "visible", timeout: 10000 });
  await input.fill("Cleopatra VII, Last Pharaoh of Ptolemaic Egypt");
  await page.waitForTimeout(500);

  // Click generate button
  const generateBtn = page.locator('button:has-text("Generate")').first();
  await generateBtn.click();

  // Wait for pipeline to start streaming — look for pipeline stepper or progress
  console.log("Waiting for pipeline progress...");
  await page.waitForTimeout(2000);

  // Wait for completion or a reasonable amount of time to capture the streaming UI
  // Poll for status changes — the pipeline typically runs 30-90 seconds
  const maxWait = 120_000;
  const start = Date.now();
  let completed = false;

  while (Date.now() - start < maxWait) {
    // Check if we see a "completed" or "failed" badge
    const status = await page.locator('text=/completed|failed/i').first().isVisible().catch(() => false);
    if (status) {
      completed = true;
      console.log("Generation completed!");
      await page.waitForTimeout(2000); // Capture final state
      break;
    }
    await page.waitForTimeout(1000);
  }

  if (!completed) {
    console.log("Timed out waiting for completion — using what we captured.");
  }

  // Close to finalize the video
  const videoPath = await page.video().path();
  await context.close();
  await browser.close();

  console.log(`Video saved: ${videoPath}`);

  // Convert to GIF with ffmpeg
  // Scale to 720px wide, 12fps, good quality palette
  console.log("Converting to GIF...");
  const palettePath = "/tmp/chronocanvas-palette.png";
  execSync(
    `ffmpeg -y -i "${videoPath}" -vf "fps=12,scale=720:-1:flags=lanczos,palettegen=stats_mode=diff" "${palettePath}"`,
    { stdio: "inherit" }
  );
  execSync(
    `ffmpeg -y -i "${videoPath}" -i "${palettePath}" -lavfi "fps=12,scale=720:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3" "${GIF_PATH}"`,
    { stdio: "inherit" }
  );

  // Check file size — if over 10MB, reduce fps
  const { statSync } = await import("fs");
  const stats = statSync(GIF_PATH);
  const sizeMB = stats.size / (1024 * 1024);
  console.log(`GIF size: ${sizeMB.toFixed(1)} MB`);

  if (sizeMB > 10) {
    console.log("GIF too large, re-encoding at 8fps with speed-up...");
    execSync(
      `ffmpeg -y -i "${videoPath}" -vf "fps=8,scale=720:-1:flags=lanczos,setpts=0.5*PTS,palettegen=stats_mode=diff" "${palettePath}"`,
      { stdio: "inherit" }
    );
    execSync(
      `ffmpeg -y -i "${videoPath}" -i "${palettePath}" -lavfi "fps=8,scale=720:-1:flags=lanczos,setpts=0.5*PTS[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3" "${GIF_PATH}"`,
      { stdio: "inherit" }
    );
    const newStats = statSync(GIF_PATH);
    console.log(`Re-encoded GIF size: ${(newStats.size / (1024 * 1024)).toFixed(1)} MB`);
  }

  console.log(`\nDone! GIF saved to: ${GIF_PATH}`);
  console.log("Uncomment the GIF section in README.md to display it.");
}

main().catch((err) => {
  console.error("Recording failed:", err.message);
  process.exit(1);
});
