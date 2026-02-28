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
  const headless = process.env.HEADLESS !== "false";
  console.log(`Headless mode: ${headless}`);
  const browser = await chromium.launch({ headless });
  const context = await browser.newContext({
    viewport: VIEWPORT,
    colorScheme: "dark",
    recordVideo: {
      dir: VIDEO_PATH,
      size: VIEWPORT,
    },
  });
  const page = await context.newPage();

  // Load the SPA at root (custom Zustand router, no URL-based routing)
  console.log("Loading app...");
  await page.goto(FRONTEND_URL, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);

  // Click the "Generate" nav button in the sidebar
  console.log("Navigating to Generate page...");
  const navBtn = page.locator('nav button:has-text("Generate")');
  await navBtn.waitFor({ state: "visible", timeout: 10000 });
  await navBtn.click();
  await page.waitForTimeout(1000);

  // Look for the input and submit a prompt
  console.log("Starting generation...");
  const input = page.locator('input[placeholder*="Describe"]');
  await input.waitFor({ state: "visible", timeout: 10000 });
  await input.fill("Cleopatra VII, Last Pharaoh of Ptolemaic Egypt");
  await page.waitForTimeout(500);

  // Click the Generate button inside the Card (not the nav link)
  const generateBtn = page.locator('button:has-text("Generate")').last();
  await generateBtn.click();
  console.log("Clicked Generate button.");

  // Wait for pipeline to start — look for "Generation Progress" card
  console.log("Waiting for pipeline progress...");
  try {
    await page.locator('text=Generation Progress').waitFor({ state: "visible", timeout: 15000 });
    console.log("  Pipeline started!");
  } catch {
    console.log("  Warning: Generation Progress card not found, continuing...");
  }

  // Poll for status changes — the pipeline typically runs 30-90 seconds
  const maxWait = 150_000;
  const start = Date.now();
  let completed = false;

  while (Date.now() - start < maxWait) {
    // Check for completed/failed badges within the Generation Progress card
    const badge = page.locator('.inline-flex:has-text("completed"), .inline-flex:has-text("failed")');
    const isVisible = await badge.first().isVisible().catch(() => false);
    if (isVisible) {
      const text = await badge.first().textContent().catch(() => "");
      completed = true;
      console.log(`Generation ${text}!`);
      await page.waitForTimeout(3000); // Capture final state
      break;
    }
    const elapsed = Math.round((Date.now() - start) / 1000);
    if (elapsed % 10 === 0) {
      console.log(`  Waiting... ${elapsed}s elapsed`);
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
  // Scale to 720px wide, 10fps, 3x speed-up (pipeline runs 60-90s, GIF should be ~20-30s)
  console.log("Converting to GIF (3x speed-up)...");
  const palettePath = "/tmp/chronocanvas-palette.png";
  execSync(
    `ffmpeg -y -i "${videoPath}" -vf "setpts=0.33*PTS,fps=10,scale=720:-1:flags=lanczos,palettegen=stats_mode=diff" "${palettePath}"`,
    { stdio: "inherit" }
  );
  execSync(
    `ffmpeg -y -i "${videoPath}" -i "${palettePath}" -lavfi "setpts=0.33*PTS,fps=10,scale=720:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3" "${GIF_PATH}"`,
    { stdio: "inherit" }
  );

  // Check file size — if over 10MB, reduce fps
  const { statSync } = await import("fs");
  const stats = statSync(GIF_PATH);
  const sizeMB = stats.size / (1024 * 1024);
  console.log(`GIF size: ${sizeMB.toFixed(1)} MB`);

  if (sizeMB > 5) {
    console.log("GIF too large, re-encoding at 6fps with more speed-up...");
    execSync(
      `ffmpeg -y -i "${videoPath}" -vf "setpts=0.2*PTS,fps=6,scale=640:-1:flags=lanczos,palettegen=stats_mode=diff" "${palettePath}"`,
      { stdio: "inherit" }
    );
    execSync(
      `ffmpeg -y -i "${videoPath}" -i "${palettePath}" -lavfi "setpts=0.2*PTS,fps=6,scale=640:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3" "${GIF_PATH}"`,
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
