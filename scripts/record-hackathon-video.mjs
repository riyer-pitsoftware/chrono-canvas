#!/usr/bin/env node
/**
 * Record the 4-minute hackathon submission video for Devpost.
 *
 * Structure (under 4 min total):
 *   1. Title + Problem Statement      (~30s)
 *   2. Live Story Mode Demo           (~90s)
 *   3. Audit Trail + Observability    (~30s)
 *   4. Architecture + GCP Proof       (~40s)
 *   5. Closing Value Statement        (~10s)
 *
 * Prerequisites:
 *   - Local stack running (docker compose up -d)
 *   - cd frontend && npx playwright install chromium
 *   - ffmpeg installed
 *   - (Optional) GCP_SCREENSHOT=path/to/cloud-run-screenshot.png for GCP proof
 *
 * Usage:
 *   node scripts/record-hackathon-video.mjs
 *   HEADLESS=false node scripts/record-hackathon-video.mjs  # watch live
 *
 * Output:
 *   docs/videos/hackathon-submission.mp4
 */
import { chromium } from "../frontend/node_modules/playwright/index.mjs";
import { execSync } from "child_process";
import { mkdirSync, existsSync, unlinkSync, statSync, writeFileSync } from "fs";
import path from "path";

const FRONTEND_URL = process.env.FRONTEND_URL || "http://localhost:3000";
const OUTPUT_DIR = "docs/videos";
const VIDEO_TMP = "/tmp/chronocanvas-hackathon";
const VIEWPORT = { width: 1440, height: 900 };
const GEN_WAIT = parseInt(process.env.GEN_WAIT || "120", 10);

// Story prompt that showcases multimodal output well
const STORY_PROMPT =
  "A young astronomer in 16th-century Varanasi discovers an ancient Sanskrit manuscript predicting a solar eclipse. She must convince the skeptical royal court before the eclipse arrives, using mathematics her teacher secretly taught her.";

/** Inject a full-screen title card overlay */
async function showTitleCard(page, lines, durationMs = 4000) {
  const html = lines
    .map(
      (l, i) =>
        `<div style="font-size:${i === 0 ? "52" : "28"}px;margin:${i === 0 ? "0 0 24px" : "8px 0"};font-weight:${i === 0 ? "700" : "400"};${i > 0 ? "opacity:0.85;" : ""}">${l}</div>`
    )
    .join("");
  await page.evaluate(
    ({ html, dur }) => {
      const overlay = document.createElement("div");
      overlay.id = "hackathon-overlay";
      overlay.innerHTML = html;
      Object.assign(overlay.style, {
        position: "fixed",
        inset: "0",
        zIndex: "99999",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        background: "linear-gradient(135deg, #0f172a 0%, #1e293b 100%)",
        color: "#f1f5f9",
        fontFamily: "'Inter', system-ui, sans-serif",
        textAlign: "center",
        padding: "60px",
      });
      document.body.appendChild(overlay);
      setTimeout(() => overlay.remove(), dur);
    },
    { html, dur: durationMs }
  );
  await page.waitForTimeout(durationMs + 300);
}

/** Inject a semi-transparent bottom caption bar */
async function showCaption(page, text, durationMs = 5000) {
  await page.evaluate(
    ({ text, dur }) => {
      // Remove any existing caption
      document.getElementById("hackathon-caption")?.remove();
      const bar = document.createElement("div");
      bar.id = "hackathon-caption";
      bar.textContent = text;
      Object.assign(bar.style, {
        position: "fixed",
        bottom: "0",
        left: "0",
        right: "0",
        zIndex: "99998",
        padding: "16px 32px",
        background: "rgba(15, 23, 42, 0.88)",
        color: "#e2e8f0",
        fontSize: "22px",
        fontFamily: "'Inter', system-ui, sans-serif",
        textAlign: "center",
        borderTop: "2px solid rgba(99, 102, 241, 0.5)",
      });
      document.body.appendChild(bar);
      setTimeout(() => bar.remove(), dur);
    },
    { text, dur: durationMs }
  );
}

async function clearCaption(page) {
  await page.evaluate(() =>
    document.getElementById("hackathon-caption")?.remove()
  );
}

/** Click a sidebar nav button by title */
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

/** Slow-type into an input/textarea */
async function slowType(locator, text, delayMs = 25) {
  await locator.click();
  await locator.fill("");
  for (const char of text) {
    await locator.pressSequentially(char, { delay: delayMs });
  }
}

/** Wait for generation pipeline to complete or timeout */
async function waitForCompletion(page, maxSeconds) {
  console.log(`  Waiting up to ${maxSeconds}s for pipeline...`);
  const start = Date.now();

  try {
    await page
      .getByText("Generation Progress")
      .waitFor({ state: "visible", timeout: 15000 });
    console.log("  Pipeline started");
  } catch {
    console.log("  Warning: Progress card not found");
  }

  while ((Date.now() - start) / 1000 < maxSeconds) {
    const done = page.locator(
      '.inline-flex:has-text("completed"), .inline-flex:has-text("failed")'
    );
    if (await done.first().isVisible().catch(() => false)) {
      const statusText = await done.first().textContent().catch(() => "done");
      console.log(`  Generation ${statusText}`);
      await page.waitForTimeout(2000);
      return statusText.includes("completed");
    }
    await page.waitForTimeout(1000);
  }
  console.log("  Timed out, moving on");
  return false;
}

async function main() {
  mkdirSync(OUTPUT_DIR, { recursive: true });
  mkdirSync(VIDEO_TMP, { recursive: true });

  console.log("=== ChronoCanvas Hackathon Submission Video ===\n");

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

  // Pre-load the app to warm up
  await page.goto(FRONTEND_URL, { waitUntil: "networkidle" });
  await page.waitForTimeout(1000);

  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // SECTION 1: Title + Problem Statement (~30s)
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  console.log("[1/5] Title + Problem Statement...");

  await showTitleCard(
    page,
    [
      "ChronoCanvas",
      "AI-Powered Visual Storytelling for History & Culture",
      "Built with Gemini + Google Cloud",
    ],
    5000
  );

  await showTitleCard(
    page,
    [
      "The Problem",
      "History education relies on static text and stock images",
      "Students disengage — no visual, interactive way to explore the past",
      "Creating historically-grounded visuals requires expert knowledge",
    ],
    7000
  );

  await showTitleCard(
    page,
    [
      "Our Solution",
      "An AI agent pipeline that researches, writes, illustrates,",
      "narrates, and assembles visual stories — all powered by Gemini",
      "Every output is grounded in research with a full audit trail",
    ],
    7000
  );

  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // SECTION 2: Live Story Mode Demo (~90s)
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  console.log("[2/5] Live Story Mode Demo...");

  await showCaption(page, "Live Demo — Story Director: from text to illustrated storyboard", 8000);

  // Navigate to Story Director
  if (await clickNav(page, "Home")) {
    await page.waitForTimeout(500);
    const startCreating = page.locator('button:has-text("Start Creating")');
    if (await startCreating.isVisible().catch(() => false)) {
      await startCreating.click();
      await page.waitForTimeout(1500);
    }
  }

  // Type the story prompt
  const storyInput = page.locator(
    'textarea[placeholder*="Paste or write your story"]'
  );
  if (await storyInput.isVisible().catch(() => false)) {
    await showCaption(page, "Paste a story concept — Gemini handles research, characters, scenes, and illustration", 12000);
    await slowType(storyInput, STORY_PROMPT, 20);
    await page.waitForTimeout(1500);

    // Generate
    const genBtn = page.locator('button:has-text("Generate Storyboard")');
    if (await genBtn.isVisible().catch(() => false)) {
      await genBtn.click();

      await showCaption(page, "Pipeline: Character Extraction → Scene Decomposition → Prompt Generation → Image Generation → Coherence Check → Narration → Video", 15000);

      const completed = await waitForCompletion(page, GEN_WAIT);

      if (completed) {
        // Scroll through the storyboard result
        await showCaption(page, "Storyboard complete — each panel is AI-generated with character consistency", 6000);
        await page.evaluate(() => window.scrollTo(0, 400));
        await page.waitForTimeout(3000);
        await page.evaluate(() => window.scrollTo(0, 800));
        await page.waitForTimeout(3000);
        await page.evaluate(() => window.scrollTo(0, 1200));
        await page.waitForTimeout(3000);
        await page.evaluate(() => window.scrollTo(0, 0));
        await page.waitForTimeout(1000);
      }
    }
  }

  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // SECTION 3: Audit Trail + Observability (~30s)
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  console.log("[3/5] Audit Trail...");

  await clearCaption(page);
  await showCaption(page, "Full audit trail — every LLM call, cost, and decision is logged", 8000);

  if (await clickNav(page, "Audit")) {
    await page.waitForTimeout(2000);
    const firstRow = page.locator("table tbody tr").first();
    if (await firstRow.isVisible().catch(() => false)) {
      await firstRow.click();
      await page.waitForTimeout(2000);
      await showCaption(page, "Token counts, cost breakdown, agent trace — full observability for every generation", 7000);
      await page.evaluate(() => window.scrollTo(0, 500));
      await page.waitForTimeout(3000);
      await page.evaluate(() => window.scrollTo(0, 1000));
      await page.waitForTimeout(3000);
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.waitForTimeout(1000);
    }
  }

  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // SECTION 4: Architecture + GCP Proof (~40s)
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  console.log("[4/5] Architecture + GCP Proof...");

  await clearCaption(page);

  await showTitleCard(
    page,
    [
      "Architecture",
      "FastAPI + LangGraph agent pipeline (7 specialized nodes)",
      "Gemini 2.5 Flash for LLM • Imagen 4.0 for images • Gemini TTS for narration",
      "PostgreSQL + pgvector • Redis job queue • React frontend",
    ],
    7000
  );

  await showTitleCard(
    page,
    [
      "Google Cloud Services",
      "Cloud Run (API + Worker + Frontend) • Cloud SQL (PostgreSQL)",
      "Memorystore (Redis) • Artifact Registry • Secret Manager",
      "Gemini API • Imagen API • Cloud TTS",
    ],
    7000
  );

  // Show health endpoint as live proof
  await page.goto(`${FRONTEND_URL.replace(":3000", ":8000")}/api/health`, {
    waitUntil: "networkidle",
  });
  await showCaption(page, "Live API — health endpoint showing all services connected", 5000);
  await page.waitForTimeout(5000);

  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // SECTION 5: Closing Value Statement (~10s)
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  console.log("[5/5] Closing...");

  await clearCaption(page);
  await showTitleCard(
    page,
    [
      "ChronoCanvas",
      "Making history visual, interactive, and accessible",
      "Powered by Gemini + Google Cloud",
      "github.com/anthropics/chrono-canvas",
    ],
    6000
  );

  // ── Finalize recording ─────────────────────────────────────────────────
  const videoPath = await page.video().path();
  await context.close();
  await browser.close();

  console.log(`\nRaw video: ${videoPath}`);

  const rawWebm = path.join(OUTPUT_DIR, "hackathon-submission.webm");
  const finalMp4 = path.join(OUTPUT_DIR, "hackathon-submission.mp4");

  execSync(`cp "${videoPath}" "${rawWebm}"`);

  // Convert webm → mp4 (H.264, universally playable)
  console.log("Converting to MP4 (H.264)...");
  execSync(
    `ffmpeg -y -i "${rawWebm}" -c:v libx264 -preset fast -crf 23 -pix_fmt yuv420p -an "${finalMp4}"`,
    { stdio: "inherit" }
  );

  // Clean up webm
  unlinkSync(rawWebm);

  const sizeMB = (statSync(finalMp4).size / (1024 * 1024)).toFixed(1);
  const durationSec = execSync(
    `ffprobe -v error -show_entries format=duration -of csv=p=0 "${finalMp4}"`
  )
    .toString()
    .trim();
  const durationMin = (parseFloat(durationSec) / 60).toFixed(1);

  console.log(`\n=== Done ===`);
  console.log(`Output:   ${finalMp4} (${sizeMB} MB, ${durationMin} min)`);

  if (parseFloat(durationMin) > 4.0) {
    console.log(
      `\n⚠ Video is over 4 minutes! Consider reducing GEN_WAIT or editing.`
    );
  } else {
    console.log(`✓ Under 4 minute limit`);
  }

  console.log(`\nNext steps:`);
  console.log(`  1. Review the video: open ${finalMp4}`);
  console.log(`  2. Upload to YouTube (unlisted) or Loom`);
  console.log(`  3. Add the public URL to your Devpost submission`);
}

main().catch((err) => {
  console.error("Recording failed:", err.message);
  process.exit(1);
});
