import { useState, useRef, useEffect, useCallback } from 'react';

/* ── Types ─────────────────────────────────────────────────────── */

type StoryPart =
  | { type: 'text'; content: string }
  | { type: 'image'; content: string; mime_type: string }
  | { type: 'casting'; content: string }
  | { type: 'casting_image'; content: string; mime_type: string };

type DoneEvent = {
  type: 'done';
  model?: string;
  elapsed_s?: number;
  text_parts?: number;
  image_parts?: number;
};

type Scene = {
  text: string;
  imageBase64?: string;
  mimeType?: string;
};

/* ── Suggested prompts ─────────────────────────────────────────── */

const SUGGESTED_PROMPTS = [
  'A jazz singer discovers a coded message hidden in a vinyl record, 1940s Harlem',
  "Hatshepsut's tomb guard witnesses something impossible at midnight",
  "A private eye in rain-soaked Tokyo, 1952, follows a woman who shouldn't exist",
  'Two astronomers in 1920s Berlin decode a signal that changes everything',
];

/* ── Pair SSE parts into scenes ────────────────────────────────── */

function pairParts(parts: StoryPart[]): Scene[] {
  // Filter out casting parts — they're for visual anchoring, not story display
  const storyParts = parts.filter(
    (p) => p.type === 'text' || p.type === 'image',
  );
  const scenes: Scene[] = [];
  let i = 0;
  while (i < storyParts.length) {
    const p = storyParts[i];
    if (p.type === 'text') {
      const scene: Scene = { text: p.content };
      if (i + 1 < storyParts.length && storyParts[i + 1].type === 'image') {
        const img = storyParts[i + 1] as { type: 'image'; content: string; mime_type: string };
        scene.imageBase64 = img.content;
        scene.mimeType = img.mime_type;
        i += 2;
      } else {
        i += 1;
      }
      scenes.push(scene);
    } else {
      const img = p as { type: 'image'; content: string; mime_type: string };
      scenes.push({ text: '', imageBase64: img.content, mimeType: img.mime_type });
      i += 1;
    }
  }
  return scenes;
}

/** Extract casting data (character descriptions + reference photo) from parts */
function extractCasting(parts: StoryPart[]): { text: string; imageBase64?: string; mimeType?: string } | null {
  const castingTexts = parts.filter((p) => p.type === 'casting').map((p) => p.content);
  const castingImg = parts.find((p) => p.type === 'casting_image') as
    | { type: 'casting_image'; content: string; mime_type: string }
    | undefined;
  if (castingTexts.length === 0 && !castingImg) return null;
  return {
    text: castingTexts.join('\n'),
    imageBase64: castingImg?.content,
    mimeType: castingImg?.mime_type,
  };
}

/* ── Typewriter hook ───────────────────────────────────────────── */

function useTypewriter(text: string, active: boolean, speed = 25) {
  const [displayed, setDisplayed] = useState('');
  const [done, setDone] = useState(false);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    if (!active) {
      setDisplayed('');
      setDone(false);
      setProgress(0);
      return;
    }
    setDisplayed('');
    setDone(false);
    setProgress(0);
    let idx = 0;
    const len = text.length || 1;
    const iv = setInterval(() => {
      idx++;
      setDisplayed(text.slice(0, idx));
      setProgress(idx / len);
      if (idx >= text.length) {
        clearInterval(iv);
        setDone(true);
        setProgress(1);
      }
    }, speed);
    return () => clearInterval(iv);
  }, [text, active, speed]);

  return { displayed, done, progress };
}

/* ── Narration hook — speaks text via Gemini Live API ───────── */

function useNarration(text: string, active: boolean) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!active || !text) {
      setReady(false);
      return;
    }

    // Stop any in-flight audio
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    abortRef.current?.abort();
    setReady(false);

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    // Fetch narration from Gemini Live API
    fetch('/api/live-voice/narrate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
      signal: ctrl.signal,
    })
      .then((res) => {
        if (!res.ok) throw new Error(`Narration failed: ${res.status}`);
        return res.blob();
      })
      .then((blob) => {
        if (ctrl.signal.aborted) return;
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        audio.onended = () => URL.revokeObjectURL(url);
        audioRef.current = audio;
        setReady(true);
        audio.play().catch(() => {});
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          console.warn('Narration failed, continuing silently:', err);
        }
        // On failure, unblock the cinema so it proceeds without audio
        if (!ctrl.signal.aborted) setReady(true);
      });

    return () => {
      ctrl.abort();
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    };
  }, [text, active]);

  return { ready };
}

/* ── Pipeline Proof — shows judges why multi-stage > one-shot ── */

const PIPELINE_STAGES = [
  { id: 'concept',    label: 'Concept',      detail: 'Extract characters, era, tone from prompt' },
  { id: 'structure',  label: 'Decompose',    detail: 'Break narrative into scenes with arcs' },
  { id: 'research',   label: 'Research',     detail: 'Ground details in real history via search' },
  { id: 'prompts',    label: 'Prompt Craft', detail: 'Per-scene image prompts with validation' },
  { id: 'generation', label: 'Generate',     detail: 'Interleaved text + photorealistic images' },
  { id: 'coherence',  label: 'Coherence',    detail: 'Cross-scene consistency, auto-regen' },
];

function statusToStage(status: string | null): string | null {
  if (!status) return null;
  const s = status.toLowerCase();
  if (s.includes('setting the scene') || s.includes('picks up')) return 'concept';
  if (s.includes('decompos')) return 'structure';
  if (s.includes('research') || s.includes('history')) return 'research';
  if (s.includes('prompt') || s.includes('craft')) return 'prompts';
  if (s.includes('unfolds') || s.includes('generat')) return 'generation';
  if (s.includes('coherence') || s.includes('check')) return 'coherence';
  return 'concept';
}

function PipelineProof({
  activeStage,
  isGenerating,
}: {
  activeStage: string | null;
  isGenerating: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const activeIdx = activeStage
    ? PIPELINE_STAGES.findIndex((s) => s.id === activeStage)
    : -1;

  return (
    <div
      className="rounded-lg border overflow-hidden transition-all duration-300"
      style={{
        borderColor: 'oklch(0.3 0.02 60)',
        backgroundColor: 'oklch(0.12 0.015 60)',
      }}
    >
      {/* Header — always visible */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-2.5 text-left group"
      >
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-[10px] font-mono uppercase tracking-[0.15em] font-semibold shrink-0"
            style={{ color: 'oklch(0.65 0.12 60)' }}>Pipeline</span>
          <span className="text-[10px] tracking-wide truncate"
            style={{ color: 'oklch(0.5 0.02 60)' }}>
            Why multi-stage beats one-shot prompting
          </span>
        </div>
        <span className="text-xs transition-transform duration-200 shrink-0 ml-2"
          style={{ color: 'oklch(0.5 0.02 60)', transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)' }}>
          &#x25BC;
        </span>
      </button>

      {/* Compact inline stage flow — always visible when collapsed */}
      {!expanded && (
        <div className="px-4 pb-3 flex items-center gap-0.5 flex-wrap">
          {PIPELINE_STAGES.map((stage, i) => {
            const isActive = isGenerating && i === activeIdx;
            const isPast = isGenerating && i < activeIdx;
            const isDone = !isGenerating && activeIdx >= 0 && i <= activeIdx;
            return (
              <div key={stage.id} className="flex items-center">
                <div className="px-2 py-0.5 rounded text-[10px] font-medium transition-all duration-300"
                  style={{
                    backgroundColor: isActive ? 'oklch(0.25 0.06 60)' : isPast || isDone ? 'oklch(0.18 0.03 60)' : 'oklch(0.15 0.01 60)',
                    color: isActive ? 'oklch(0.85 0.12 60)' : isPast || isDone ? 'oklch(0.6 0.06 60)' : 'oklch(0.38 0.02 60)',
                    border: isActive ? '1px solid oklch(0.4 0.1 60)' : '1px solid oklch(0.22 0.015 60)',
                    animation: isActive ? 'pipelinePulse 2s ease-in-out infinite' : 'none',
                  }}>
                  {stage.label}
                </div>
                {i < PIPELINE_STAGES.length - 1 && (
                  <span className="mx-0.5 text-[8px]"
                    style={{ color: isPast || isDone || isActive ? 'oklch(0.5 0.08 60)' : 'oklch(0.25 0.02 60)' }}>
                    &#x25B8;
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Expanded detail view */}
      {expanded && (
        <div className="px-4 pb-4 space-y-4" style={{ animation: 'fadeIn 200ms ease-out' }}>
          {/* One-shot vs pipeline comparison */}
          <div className="grid grid-cols-2 gap-3 text-xs" style={{ color: 'oklch(0.7 0.02 60)' }}>
            <div className="rounded-md p-3"
              style={{ backgroundColor: 'oklch(0.1 0.01 0)', borderLeft: '2px solid oklch(0.35 0.04 0)' }}>
              <div className="font-semibold mb-1.5 uppercase tracking-wider text-[10px]"
                style={{ color: 'oklch(0.45 0.04 0)' }}>One-shot prompting</div>
              <ul className="space-y-1 text-[11px]" style={{ color: 'oklch(0.45 0.02 60)' }}>
                <li>&bull; Single prompt, single response</li>
                <li>&bull; No character consistency</li>
                <li>&bull; No historical grounding</li>
                <li>&bull; No coherence validation</li>
                <li>&bull; Hope for the best</li>
              </ul>
            </div>
            <div className="rounded-md p-3"
              style={{ backgroundColor: 'oklch(0.14 0.025 60)', borderLeft: '2px solid oklch(0.55 0.12 60)' }}>
              <div className="font-semibold mb-1.5 uppercase tracking-wider text-[10px]"
                style={{ color: 'oklch(0.7 0.12 60)' }}>ChronoNoir pipeline</div>
              <ul className="space-y-1 text-[11px]" style={{ color: 'oklch(0.6 0.04 60)' }}>
                <li>&bull; 6-stage agentic pipeline</li>
                <li>&bull; Character extraction &amp; tracking</li>
                <li>&bull; Google Search for real history</li>
                <li>&bull; Per-scene prompt validation</li>
                <li>&bull; Coherence check + auto-regen</li>
              </ul>
            </div>
          </div>

          {/* Stages detail list */}
          <div className="space-y-0.5">
            {PIPELINE_STAGES.map((stage, i) => {
              const isActive = isGenerating && i === activeIdx;
              const isPast = isGenerating && i < activeIdx;
              const isDone = !isGenerating && activeIdx >= 0 && i <= activeIdx;
              return (
                <div key={stage.id}
                  className="flex items-center gap-3 rounded px-3 py-1.5 transition-all duration-300"
                  style={{ backgroundColor: isActive ? 'oklch(0.18 0.035 60)' : 'transparent' }}>
                  <span className="text-[10px] font-mono w-4 text-right shrink-0"
                    style={{ color: isActive ? 'oklch(0.7 0.12 60)' : isPast || isDone ? 'oklch(0.5 0.06 60)' : 'oklch(0.3 0.02 60)' }}>
                    {isPast || isDone ? '\u2713' : `${i + 1}`}
                  </span>
                  <div className="flex-1 min-w-0">
                    <span className="text-xs font-medium"
                      style={{ color: isActive ? 'oklch(0.85 0.1 60)' : isPast || isDone ? 'oklch(0.6 0.06 60)' : 'oklch(0.45 0.02 60)' }}>
                      {stage.label}
                    </span>
                    <span className="text-[10px] ml-2" style={{ color: 'oklch(0.38 0.02 60)' }}>
                      {stage.detail}
                    </span>
                  </div>
                  {isActive && (
                    <span className="inline-block w-1.5 h-1.5 rounded-full animate-ping shrink-0"
                      style={{ backgroundColor: 'oklch(0.7 0.12 60)' }} />
                  )}
                </div>
              );
            })}
          </div>

          <div className="text-[10px] text-center pt-1"
            style={{ color: 'oklch(0.38 0.02 60)', fontFamily: "'Georgia', 'Times New Roman', serif", fontStyle: 'italic' }}>
            Each stage is a LangGraph node &mdash; debuggable, retryable, independently testable
          </div>
        </div>
      )}

      <style>{`
        @keyframes pipelinePulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.7; }
        }
      `}</style>
    </div>
  );
}

/* ── Wait SFX hook — vinyl crackle + projector tick during narration fetch ── */

function useWaitSFX(active: boolean) {
  useEffect(() => {
    if (!active) return;

    let ctx: AudioContext;
    try {
      ctx = new AudioContext();
    } catch {
      return; // Browser blocked AudioContext — skip silently
    }

    const gainNode = ctx.createGain();
    gainNode.gain.value = 0.08; // Very quiet — atmospheric, not distracting
    gainNode.connect(ctx.destination);

    // Brownian noise buffer — warm vinyl crackle character
    const bufferSize = 2 * ctx.sampleRate;
    const noiseBuffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
    const output = noiseBuffer.getChannelData(0);
    let lastOut = 0;
    for (let i = 0; i < bufferSize; i++) {
      const white = Math.random() * 2 - 1;
      output[i] = (lastOut + 0.02 * white) / 1.02;
      lastOut = output[i];
      output[i] *= 3.5;
    }
    const noise = ctx.createBufferSource();
    noise.buffer = noiseBuffer;
    noise.loop = true;

    // Bandpass filter for warm vinyl character
    const filter = ctx.createBiquadFilter();
    filter.type = 'bandpass';
    filter.frequency.value = 800;
    filter.Q.value = 0.5;

    noise.connect(filter);
    filter.connect(gainNode);
    noise.start();

    // Projector tick — periodic quiet clicks at ~8Hz
    const tickInterval = setInterval(() => {
      try {
        const osc = ctx.createOscillator();
        const tickGain = ctx.createGain();
        osc.frequency.value = 2000 + Math.random() * 500;
        tickGain.gain.value = 0.03;
        tickGain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.03);
        osc.connect(tickGain);
        tickGain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.03);
      } catch {
        // AudioContext may have been closed during cleanup race
      }
    }, 125);

    return () => {
      clearInterval(tickInterval);
      try {
        gainNode.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.2);
      } catch {
        // Ignore if context already closed
      }
      setTimeout(() => {
        try {
          noise.stop();
          ctx.close();
        } catch {
          // Already stopped/closed
        }
      }, 250);
    };
  }, [active]);
}

/* ── SceneViewer (full-screen overlay) ─────────────────────────── */

type CastingData = { text: string; imageBase64?: string; mimeType?: string };

function SceneViewer({
  scenes,
  stats,
  continuing,
  onClose,
  onContinue,
  onRashomon,
  casting,
}: {
  scenes: Scene[];
  stats: DoneEvent | null;
  continuing: boolean;
  onClose: () => void;
  onContinue: (direction: string) => void;
  onRashomon: () => void;
  casting?: CastingData | null;
}) {
  const [current, setCurrent] = useState(0);
  const [fadeKey, setFadeKey] = useState(0);
  const [transitioning, setTransitioning] = useState(false);
  const [continueInput, setContinueInput] = useState('');
  const [showCasting, setShowCasting] = useState(false);
  const touchStart = useRef<number | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scene = scenes[current];
  const isLastScene = current === scenes.length - 1;

  // Narrate current scene aloud — cinema waits for audio to arrive
  const { ready: narrationReady } = useNarration(scene?.text || '', !transitioning);

  // Vinyl crackle + projector tick while waiting for narration audio
  const waitingForNarration = !narrationReady && !transitioning && !!scene?.text;
  useWaitSFX(waitingForNarration);

  const { displayed, done: textDone, progress } = useTypewriter(
    transitioning ? '' : scene?.text || '',
    !transitioning && narrationReady,
  );

  // Iris opens from 0% to 75% as text is typed
  const irisRadius = scene?.text ? Math.round(progress * 75) : 75;

  // Jump to last scene when new scenes arrive (continuation)
  const prevSceneCount = useRef(scenes.length);
  useEffect(() => {
    if (scenes.length > prevSceneCount.current) {
      setCurrent(scenes.length - (scenes.length - prevSceneCount.current));
      setFadeKey((k) => k + 1);
    }
    prevSceneCount.current = scenes.length;
  }, [scenes.length]);

  // Film dissolve: fade to black → switch scene → fade in
  const changeTo = useCallback(
    (next: number) => {
      if (next < 0 || next >= scenes.length || transitioning) return;
      setTransitioning(true);
      // Fade out (500ms), then switch scene, then fade in
      setTimeout(() => {
        setCurrent(next);
        setFadeKey((k) => k + 1);
        // Small delay before removing transition flag so fade-in animation plays
        setTimeout(() => setTransitioning(false), 50);
      }, 500);
    },
    [scenes.length, transitioning],
  );

  const go = useCallback(
    (dir: 1 | -1) => changeTo(current + dir),
    [current, changeTo],
  );

  // Keyboard navigation
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      // Don't capture arrows when input is focused
      if (document.activeElement === inputRef.current) return;
      if (e.key === 'ArrowRight') go(1);
      else if (e.key === 'ArrowLeft') go(-1);
      else if (e.key === 'Escape') onClose();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [go, onClose]);

  function onTouchStart(e: React.TouchEvent) {
    touchStart.current = e.touches[0].clientX;
  }
  function onTouchEnd(e: React.TouchEvent) {
    if (touchStart.current === null) return;
    const dx = e.changedTouches[0].clientX - touchStart.current;
    if (Math.abs(dx) > 60) go(dx < 0 ? 1 : -1);
    touchStart.current = null;
  }

  function handleContinue() {
    if (!continueInput.trim() || continuing) return;
    onContinue(continueInput.trim());
    setContinueInput('');
  }

  if (!scene) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col"
      style={{ backgroundColor: 'oklch(0.08 0.01 60)' }}
      onTouchStart={onTouchStart}
      onTouchEnd={onTouchEnd}
    >
      {/* Top bar */}
      <div className="flex items-center justify-between px-6 py-4 shrink-0">
        <button
          onClick={onClose}
          className="text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
        >
          &larr; Back
        </button>
        <div className="flex items-center gap-4">
          {casting && (
            <button
              onClick={() => setShowCasting(!showCasting)}
              className="text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
            >
              {showCasting ? 'Hide Cast' : 'Show Cast'}
            </button>
          )}
          <span className="text-xs text-[var(--muted-foreground)] tabular-nums">
            {current + 1} / {scenes.length}
          </span>
        </div>
      </div>

      {/* Casting card — collapsible character reference */}
      {showCasting && casting && (
        <div className="mx-6 mb-4 p-4 rounded-lg shrink-0 overflow-auto max-h-[30vh]"
          style={{ backgroundColor: 'oklch(0.12 0.01 60)', border: '1px solid oklch(0.2 0.01 60)' }}>
          <p className="text-xs font-semibold text-[var(--muted-foreground)] mb-2 uppercase tracking-wider">
            Casting Reference
          </p>
          {casting.imageBase64 && (
            <img
              src={`data:${casting.mimeType || 'image/png'};base64,${casting.imageBase64}`}
              alt="Character casting reference"
              className="max-h-32 rounded mb-2 object-contain"
            />
          )}
          <p className="text-xs text-[var(--muted-foreground)] whitespace-pre-wrap leading-relaxed">
            {casting.text}
          </p>
        </div>
      )}

      {/* Scene content — centered, with film dissolve */}
      <div
        key={fadeKey}
        className="flex-1 flex flex-col items-center justify-center px-8 gap-6 min-h-0"
        style={{
          animation: transitioning ? 'none' : 'dissolveIn 800ms ease-out',
          opacity: transitioning ? 0 : 1,
          transition: 'opacity 500ms ease-in-out',
        }}
      >
        {/* Image with camera iris — opens as text is read */}
        {scene.imageBase64 && (
          <div
            className="overflow-hidden rounded-lg max-h-[50vh] max-w-full"
            style={{
              clipPath: `circle(${irisRadius}% at 50% 50%)`,
              transition: 'clip-path 300ms ease-out',
            }}
          >
            <img
              src={`data:${scene.mimeType || 'image/png'};base64,${scene.imageBase64}`}
              alt={`Scene ${current + 1}`}
              className="max-h-[50vh] max-w-full object-contain"
              style={{
                boxShadow: '0 0 80px rgba(180, 140, 60, 0.12), 0 8px 40px rgba(0,0,0,0.7)',
              }}
            />
          </div>
        )}

        {/* Text */}
        {scene.text && (
          <p
            className="max-w-2xl text-center leading-relaxed text-lg"
            style={{
              fontFamily: "'Georgia', 'Times New Roman', serif",
              color: 'oklch(0.9 0.02 80)',
              textShadow: '0 1px 8px rgba(0,0,0,0.5)',
            }}
          >
            {displayed}
            {!textDone && (
              <span
                className="inline-block w-[2px] h-[1em] ml-0.5 align-text-bottom"
                style={{
                  backgroundColor: 'var(--primary)',
                  animation: 'blink 800ms step-end infinite',
                }}
              />
            )}
          </p>
        )}

        {/* "What happens next?" + Rashomon on last scene */}
        {isLastScene && textDone && !continuing && (
          <div
            className="flex flex-col items-center gap-3 max-w-lg w-full mt-2"
            style={{ animation: 'fadeIn 600ms ease-out' }}
          >
            <div className="flex items-center gap-2 w-full">
              <input
                ref={inputRef}
                type="text"
                value={continueInput}
                onChange={(e) => setContinueInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleContinue();
                }}
                placeholder="What happens next?"
                className="flex-1 rounded-md border border-[var(--border)] bg-[var(--background)]/50 px-3 py-2 text-sm focus:ring-1 focus:ring-[var(--primary)] focus:border-[var(--primary)] transition-colors"
                style={{ fontFamily: "'Georgia', 'Times New Roman', serif" }}
              />
              <button
                onClick={handleContinue}
                disabled={!continueInput.trim()}
                className="px-4 py-2 rounded-md bg-[var(--primary)] text-[var(--primary-foreground)] text-sm font-medium disabled:opacity-50 transition-opacity shrink-0"
              >
                Continue
              </button>
            </div>
            <button
              onClick={onRashomon}
              className="text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors border border-[var(--border)] rounded-md px-3 py-1.5 hover:border-[var(--primary)]"
              style={{ fontFamily: "'Georgia', 'Times New Roman', serif" }}
            >
              Tell it from the other side &hellip;
            </button>
          </div>
        )}

        {/* Continuation loading */}
        {continuing && (
          <div className="flex items-center gap-2 text-sm text-[var(--muted-foreground)] italic animate-pulse">
            <span className="inline-block w-2 h-2 rounded-full bg-[var(--primary)] animate-ping" />
            Dash picks up the thread...
          </div>
        )}
      </div>

      {/* Navigation arrows */}
      {current > 0 && (
        <button
          onClick={() => go(-1)}
          className="absolute left-4 top-1/2 -translate-y-1/2 text-3xl text-[var(--muted-foreground)] hover:text-[var(--foreground)] opacity-0 hover:opacity-100 transition-opacity p-4"
          aria-label="Previous scene"
        >
          &lsaquo;
        </button>
      )}
      {current < scenes.length - 1 && (
        <button
          onClick={() => go(1)}
          className="absolute right-4 top-1/2 -translate-y-1/2 text-3xl text-[var(--muted-foreground)] hover:text-[var(--foreground)] opacity-0 hover:opacity-100 transition-opacity p-4"
          aria-label="Next scene"
        >
          &rsaquo;
        </button>
      )}

      {/* Dot nav + stats */}
      <div className="shrink-0 px-6 py-4 flex flex-col items-center gap-2">
        <div className="flex gap-2 flex-wrap justify-center">
          {scenes.map((_, i) => (
            <button
              key={i}
              onClick={() => changeTo(i)}
              className="w-2 h-2 rounded-full transition-colors"
              style={{
                backgroundColor:
                  i === current ? 'var(--primary)' : 'var(--muted-foreground)',
                opacity: i === current ? 1 : 0.4,
              }}
              aria-label={`Go to scene ${i + 1}`}
            />
          ))}
        </div>

        {stats && (
          <div className="flex items-center gap-4 text-xs text-[var(--muted-foreground)]">
            <span>
              {stats.text_parts} text + {stats.image_parts} images
            </span>
            <span>{stats.elapsed_s}s</span>
            {stats.model && <span className="opacity-60">{stats.model}</span>}
          </div>
        )}

        <span className="text-xs text-amber-200/60">
          AI-generated &middot; Powered by Gemini
        </span>
      </div>

      <style>{`
        @keyframes dissolveIn {
          0% { opacity: 0; }
          30% { opacity: 0; }
          100% { opacity: 1; }
        }
@keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes blink {
          50% { opacity: 0; }
        }
      `}</style>
    </div>
  );
}

/* ── Main LiveStory page ───────────────────────────────────────── */

export function LiveStory() {
  const [prompt, setPrompt] = useState('');
  const [originalPrompt, setOriginalPrompt] = useState('');
  const [parts, setParts] = useState<StoryPart[]>([]);
  const [loading, setLoading] = useState(false);
  const [continuing, setContinuing] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<DoneEvent | null>(null);
  const [viewerOpen, setViewerOpen] = useState(false);

  const scenes = pairParts(parts);
  const pipelineStage = loading || continuing ? statusToStage(status) : (stats ? 'coherence' : null);

  // Auto-open viewer when generation completes
  useEffect(() => {
    if (stats && scenes.length > 0 && !viewerOpen && !continuing) {
      setViewerOpen(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stats]);

  /** Shared SSE fetch logic */
  async function fetchSSE(
    body: Record<string, unknown>,
    opts: { append?: boolean } = {},
  ) {
    setError(null);
    setStats(null);
    setStatus(null);

    if (!opts.append) {
      setParts([]);
      setViewerOpen(false);
    }

    try {
      const res = await fetch('/api/live-story', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const data = JSON.parse(line.slice(6));
          if (data.type === 'done') {
            setStats(data);
            setStatus(null);
          } else if (data.type === 'error') {
            setError(data.content);
          } else if (data.type === 'status') {
            setStatus(data.content);
          } else if (
            data.type === 'text' ||
            data.type === 'image' ||
            data.type === 'casting' ||
            data.type === 'casting_image'
          ) {
            setParts((prev) => [...prev, data as StoryPart]);
          }
        }
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  /** Initial generation */
  async function generate() {
    if (!prompt.trim()) return;
    setOriginalPrompt(prompt.trim());
    setLoading(true);
    try {
      await fetchSSE({ prompt: prompt.trim(),  });
    } finally {
      setLoading(false);
    }
  }

  /** Continue the story with user direction */
  async function continueStory(direction: string) {
    setContinuing(true);
    // Only send last 2 images to stay under body size limits — backend only uses last 2 anyway
    const imageParts = parts.filter((p) => p.type === 'image' || p.type === 'casting_image');
    const recentImages = new Set(imageParts.slice(-2));
    const history = parts
      .filter((p) => p.type === 'text' || p.type === 'casting' || recentImages.has(p))
      .map((p) => {
        if (p.type === 'text' || p.type === 'casting') {
          return { type: 'text', content: p.content };
        }
        return { type: 'image', content: p.content, mime_type: (p as { mime_type: string }).mime_type };
      });

    try {
      await fetchSSE(
        {
          prompt: direction,
          original_prompt: originalPrompt,
          history,
        },
        { append: true },
      );
    } finally {
      setContinuing(false);
    }
  }

  /** Rashomon — retell from the other perspective */
  async function rashomonRetell() {
    setLoading(true);
    // Extract just the text parts to summarize the story for the retelling prompt
    const storyTexts = parts
      .filter((p) => p.type === 'text')
      .map((p) => p.content)
      .join('\n\n');

    const rashomonPrompt =
      `Retell this story from the opposite perspective. ` +
      `If the original was told from the protagonist's view, tell it from the antagonist's. ` +
      `If it was second person, switch to third. Same events, different truth. ` +
      `This is the Rashomon — every narrator lies differently.\n\n` +
      `Original story:\n${storyTexts}`;

    try {
      await fetchSSE({ prompt: rashomonPrompt,  });
    } finally {
      setLoading(false);
    }
  }

  /* ── Viewer overlay ──────────────────────────────────────────── */
  if (viewerOpen && scenes.length > 0) {
    return (
      <SceneViewer
        scenes={scenes}
        stats={stats}
        continuing={continuing}
        onClose={() => setViewerOpen(false)}
        onContinue={continueStory}
        onRashomon={rashomonRetell}
        casting={extractCasting(parts)}
      />
    );
  }

  /* ── Prompt input view ───────────────────────────────────────── */
  return (
    <div className="max-w-3xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold mb-1 tracking-tight">Live Story</h1>
        <p className="text-sm text-[var(--muted-foreground)]">
          Gemini generates interleaved text and images &mdash; the story and its visuals arrive
          together.
        </p>
      </div>

      {/* Pipeline Proof — collapsible section for judges */}
      <PipelineProof
        activeStage={pipelineStage}
        isGenerating={loading || continuing}
      />

      {/* Prompt input */}
      <div className="space-y-3">
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) generate();
          }}
          placeholder="A noir detective story set in ancient Egypt with Hatshepsut..."
          className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] p-3 text-sm min-h-[80px] resize-y focus:ring-1 focus:ring-[var(--primary)] focus:border-[var(--primary)] transition-colors"
          disabled={loading}
        />

        <div className="flex items-center gap-3">
          <div className="flex-1" />
          <button
            onClick={generate}
            disabled={loading || !prompt.trim()}
            className="px-5 py-2 rounded-md bg-[var(--primary)] text-[var(--primary-foreground)] text-sm font-medium disabled:opacity-50 transition-opacity"
          >
            {loading ? 'Rolling...' : 'Action'}
          </button>
        </div>
      </div>

      {/* Suggested prompts */}
      {parts.length === 0 && !loading && (
        <div className="space-y-2">
          <p className="text-xs text-[var(--muted-foreground)] uppercase tracking-wider">
            Try a prompt
          </p>
          <div className="grid gap-2">
            {SUGGESTED_PROMPTS.map((sp, i) => (
              <button
                key={i}
                onClick={() => setPrompt(sp)}
                className="text-left text-sm px-3 py-2 rounded-md border border-[var(--border)] hover:bg-[var(--muted)]/50 transition-colors text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
              >
                {sp}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Status indicator */}
      {status && (
        <div className="flex items-center gap-2 text-sm text-[var(--muted-foreground)] italic animate-pulse">
          <span className="inline-block w-2 h-2 rounded-full bg-[var(--primary)] animate-ping" />
          {status}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="rounded-md border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Re-enter viewer button */}
      {scenes.length > 0 && !loading && (
        <button
          onClick={() => setViewerOpen(true)}
          className="w-full py-3 rounded-md border border-[var(--border)] text-sm text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:border-[var(--primary)] transition-colors"
        >
          View story ({scenes.length} scenes)
        </button>
      )}

      {/* Stats */}
      {stats && scenes.length > 0 && (
        <div className="flex items-center gap-4 text-xs text-[var(--muted-foreground)]">
          <span>
            {stats.text_parts} text + {stats.image_parts} images
          </span>
          <span>{stats.elapsed_s}s</span>
          {stats.model && <span className="opacity-60">{stats.model}</span>}
        </div>
      )}
    </div>
  );
}
