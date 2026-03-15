import { useState, useRef, useEffect, useCallback } from 'react';
import { useNarrationPipeline } from '../hooks/useNarrationPipeline';

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

type StageEvent = {
  type: 'stage';
  stage: string;       // "init", "casting", "scene", "replay"
  status: string;       // "start", "complete", "error", "timeout"
  elapsed_s?: number;
  scene_idx?: number;
  detail?: string;
};

type StageState = {
  stage: string;
  label: string;
  status: 'pending' | 'running' | 'complete' | 'error' | 'timeout';
  elapsed_s?: number;
  detail?: string;
};

type Scene = {
  text: string;
  imageBase64?: string;
  mimeType?: string;
  videoBase64?: string;
  videoMimeType?: string;
  videoFailed?: boolean;
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

/* ── Pipeline Progress — real stage tracking from backend events ── */

function stageLabel(evt: StageEvent): string {
  if (evt.stage === 'init') return 'Initialize';
  if (evt.stage === 'casting') return 'Casting';
  if (evt.stage === 'replay') return 'Replay History';
  if (evt.stage === 'scene') return `Scene ${evt.scene_idx ?? '?'}`;
  return evt.stage;
}

function buildStageStates(events: StageEvent[]): StageState[] {
  const stages: StageState[] = [];
  const seen = new Map<string, number>(); // key → index in stages[]

  for (const evt of events) {
    const key = evt.stage === 'scene' ? `scene-${evt.scene_idx}` : evt.stage;
    const label = stageLabel(evt);

    if (evt.status === 'start') {
      const idx = stages.length;
      seen.set(key, idx);
      stages.push({ stage: key, label, status: 'running' });
    } else {
      // complete, error, timeout
      const idx = seen.get(key);
      if (idx !== undefined) {
        stages[idx].status = evt.status === 'complete' ? 'complete' : evt.status === 'timeout' ? 'timeout' : 'error';
        stages[idx].elapsed_s = evt.elapsed_s;
        stages[idx].detail = evt.detail;
      } else {
        // got a complete/error without a start — still show it
        stages.push({
          stage: key,
          label,
          status: evt.status === 'complete' ? 'complete' : evt.status === 'timeout' ? 'timeout' : 'error',
          elapsed_s: evt.elapsed_s,
          detail: evt.detail,
        });
      }
    }
  }
  return stages;
}

function PipelineProgress({
  stages,
  isGenerating,
}: {
  stages: StageState[];
  isGenerating: boolean;
}) {
  const [expanded, setExpanded] = useState(false);

  if (stages.length === 0 && !isGenerating) return null;

  return (
    <div
      className="rounded-lg border overflow-hidden transition-all duration-300"
      style={{
        borderColor: 'oklch(0.3 0.02 60)',
        backgroundColor: 'oklch(0.12 0.015 60)',
      }}
    >
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-2.5 text-left group"
      >
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-[10px] font-mono uppercase tracking-[0.15em] font-semibold shrink-0"
            style={{ color: 'oklch(0.65 0.12 60)' }}>Pipeline</span>
          {isGenerating && (
            <span className="text-[10px] tracking-wide truncate"
              style={{ color: 'oklch(0.5 0.02 60)' }}>
              {stages.filter((s) => s.status === 'complete').length} / {stages.length} stages
            </span>
          )}
        </div>
        <span className="text-xs transition-transform duration-200 shrink-0 ml-2"
          style={{ color: 'oklch(0.5 0.02 60)', transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)' }}>
          &#x25BC;
        </span>
      </button>

      {/* Compact inline stage flow */}
      {!expanded && stages.length > 0 && (
        <div className="px-4 pb-3 flex items-center gap-0.5 flex-wrap">
          {stages.map((stage, i) => {
            const isRunning = stage.status === 'running';
            const isDone = stage.status === 'complete';
            const isFailed = stage.status === 'error' || stage.status === 'timeout';
            return (
              <div key={stage.stage} className="flex items-center">
                <div className="px-2 py-0.5 rounded text-[10px] font-medium transition-all duration-300 flex items-center gap-1"
                  style={{
                    backgroundColor: isFailed ? 'oklch(0.2 0.06 25)' : isRunning ? 'oklch(0.25 0.06 60)' : isDone ? 'oklch(0.18 0.03 60)' : 'oklch(0.15 0.01 60)',
                    color: isFailed ? 'oklch(0.7 0.15 25)' : isRunning ? 'oklch(0.85 0.12 60)' : isDone ? 'oklch(0.6 0.06 60)' : 'oklch(0.38 0.02 60)',
                    border: isFailed ? '1px solid oklch(0.4 0.12 25)' : isRunning ? '1px solid oklch(0.4 0.1 60)' : '1px solid oklch(0.22 0.015 60)',
                    animation: isRunning ? 'pipelinePulse 2s ease-in-out infinite' : 'none',
                  }}>
                  {isDone && <span>&#x2713;</span>}
                  {isFailed && <span>&#x2717;</span>}
                  {stage.label}
                  {isDone && stage.elapsed_s != null && (
                    <span style={{ opacity: 0.6 }}>{stage.elapsed_s}s</span>
                  )}
                </div>
                {i < stages.length - 1 && (
                  <span className="mx-0.5 text-[8px]"
                    style={{ color: isDone ? 'oklch(0.5 0.08 60)' : 'oklch(0.25 0.02 60)' }}>
                    &#x25B8;
                  </span>
                )}
              </div>
            );
          })}
          {isGenerating && (
            <span className="inline-block w-1.5 h-1.5 rounded-full animate-ping ml-1"
              style={{ backgroundColor: 'oklch(0.7 0.12 60)' }} />
          )}
        </div>
      )}

      {/* Expanded detail view */}
      {expanded && (
        <div className="px-4 pb-4 space-y-1" style={{ animation: 'fadeIn 200ms ease-out' }}>
          {stages.length === 0 && (
            <div className="text-xs py-2" style={{ color: 'oklch(0.4 0.02 60)' }}>
              Waiting for pipeline to start...
            </div>
          )}
          {stages.map((stage) => {
            const isRunning = stage.status === 'running';
            const isDone = stage.status === 'complete';
            const isFailed = stage.status === 'error' || stage.status === 'timeout';
            return (
              <div key={stage.stage}
                className="flex items-center gap-3 rounded px-3 py-1.5 transition-all duration-300"
                style={{ backgroundColor: isRunning ? 'oklch(0.18 0.035 60)' : isFailed ? 'oklch(0.15 0.03 25)' : 'transparent' }}>
                <span className="text-[10px] font-mono w-4 text-right shrink-0"
                  style={{
                    color: isFailed ? 'oklch(0.6 0.15 25)' : isRunning ? 'oklch(0.7 0.12 60)' : isDone ? 'oklch(0.5 0.06 60)' : 'oklch(0.3 0.02 60)',
                  }}>
                  {isDone ? '\u2713' : isFailed ? '\u2717' : isRunning ? '\u25CF' : '\u25CB'}
                </span>
                <div className="flex-1 min-w-0">
                  <span className="text-xs font-medium"
                    style={{
                      color: isFailed ? 'oklch(0.7 0.12 25)' : isRunning ? 'oklch(0.85 0.1 60)' : isDone ? 'oklch(0.6 0.06 60)' : 'oklch(0.45 0.02 60)',
                    }}>
                    {stage.label}
                  </span>
                  {stage.elapsed_s != null && (
                    <span className="text-[10px] ml-2" style={{ color: 'oklch(0.4 0.02 60)' }}>
                      {stage.elapsed_s}s
                    </span>
                  )}
                  {stage.detail && isFailed && (
                    <span className="text-[10px] ml-2" style={{ color: 'oklch(0.55 0.1 25)' }}>
                      {stage.detail}
                    </span>
                  )}
                </div>
                {isRunning && (
                  <span className="inline-block w-1.5 h-1.5 rounded-full animate-ping shrink-0"
                    style={{ backgroundColor: 'oklch(0.7 0.12 60)' }} />
                )}
              </div>
            );
          })}
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

/* ── CastingInterstitial (full-screen title card while scenes generate) ── */

type CastingData = { text: string; imageBase64?: string; mimeType?: string };

function CastingInterstitial({
  casting,
  onClose,
}: {
  casting: CastingData;
  onClose: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex flex-col"
      style={{ backgroundColor: 'oklch(0.08 0.01 60)' }}
    >
      {/* Top bar */}
      <div className="flex items-center justify-between px-6 py-4 shrink-0">
        <button
          onClick={onClose}
          className="text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
        >
          &larr; Back
        </button>
        <span className="text-xs text-[var(--muted-foreground)] uppercase tracking-wider">
          Casting
        </span>
      </div>

      {/* Casting content — image left, description right */}
      <div
        className="flex-1 flex flex-col items-center justify-center px-8 min-h-0"
        style={{ animation: 'dissolveIn 800ms ease-out' }}
      >
        <div className="flex items-start justify-center gap-8 max-h-[80vh] min-h-0">
          {casting.imageBase64 && (
            <img
              src={`data:${casting.mimeType || 'image/png'};base64,${casting.imageBase64}`}
              alt="Character casting photo"
              className="max-h-[70vh] max-w-[45vw] rounded-lg object-contain shrink-0"
              style={{ animation: 'dissolveIn 1200ms ease-out' }}
            />
          )}
          {casting.text && (
            <div className="max-w-sm overflow-y-auto max-h-[70vh] shrink min-w-[200px]">
              <p
                className="text-sm leading-relaxed whitespace-pre-wrap"
                style={{ color: 'oklch(0.75 0.02 60)' }}
              >
                {casting.text}
              </p>
            </div>
          )}
        </div>
        {/* Loading indicator */}
        <div className="flex items-center gap-2 text-xs animate-pulse mt-6"
          style={{ color: 'oklch(0.5 0.02 60)' }}>
          <span
            className="inline-block w-1.5 h-1.5 rounded-full"
            style={{ backgroundColor: 'var(--primary)', animation: 'blink 1.2s infinite' }}
          />
          Scenes generating...
        </div>
      </div>

      <style>{`
        @keyframes dissolveIn {
          0% { opacity: 0; }
          30% { opacity: 0; }
          100% { opacity: 1; }
        }
        @keyframes blink {
          50% { opacity: 0; }
        }
      `}</style>
    </div>
  );
}

/* ── SceneViewer (full-screen overlay) ─────────────────────────── */

function SceneViewer({
  scenes,
  stats,
  continuing,
  generating,
  onClose,
  onContinue,
  onRashomon,
  onGenerateFilm,
  onDownloadFilm,
  casting,
  filmGenerating,
  filmProgress,
  filmComplete,
  veoEnabled,
  isDemoReel,
  pipeline,
  onSceneChange,
}: {
  scenes: Scene[];
  stats: DoneEvent | null;
  continuing: boolean;
  generating: boolean;
  onClose: () => void;
  onContinue: (direction: string) => void;
  onRashomon: () => void;
  onGenerateFilm: () => void;
  onDownloadFilm: () => void;
  casting?: CastingData | null;
  filmGenerating: boolean;
  filmProgress: string | null;
  filmComplete: boolean;
  veoEnabled: boolean;
  isDemoReel?: boolean;
  pipeline: ReturnType<typeof useNarrationPipeline>;
  onSceneChange: (idx: number) => void;
}) {
  const [current, setCurrent] = useState(0);
  const [fadeKey, setFadeKey] = useState(0);
  const [transitioning, setTransitioning] = useState(false);
  const [continueInput, setContinueInput] = useState('');
  const [showCasting, setShowCasting] = useState(false);
  const [autoPlay, setAutoPlay] = useState(true);
  const touchStart = useRef<number | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scene = scenes[current];
  const isLastScene = current === scenes.length - 1;

  // Narration pipeline is owned by parent — use it via props
  const narrationReady = pipeline.narrationReady;


  // Report scene changes to parent so pipeline tracks the right index
  useEffect(() => {
    onSceneChange(current);
  }, [current, onSceneChange]);

  // Vinyl crackle + projector tick while waiting for narration audio
  const waitingForNarration = !narrationReady && !transitioning && !!scene?.text;
  useWaitSFX(waitingForNarration);

  const { displayed, done: textDone, progress } = useTypewriter(
    transitioning ? '' : scene?.text || '',
    !transitioning && narrationReady,
  );

  // Play audio when scene is revealed and narration ready.
  // Only trigger on transitioning/narrationReady changes — NOT on pipeline
  // object identity (which changes every render when scenes.length updates).
  const playRef = useRef(pipeline.playCurrentNarration);
  playRef.current = pipeline.playCurrentNarration;
  useEffect(() => {
    if (!transitioning && narrationReady) {
      playRef.current();
    }
  }, [transitioning, narrationReady]);

  // Iris opens as text is typed; show at least 30% when image exists
  // so images are visible even if narration is slow/failing
  const baseIris = scene?.imageBase64 ? 30 : 0;
  const irisRadius = scene?.text ? Math.max(baseIris, Math.round(progress * 75)) : 75;


  // Jump to first new scene only during continuation (not initial generation).
  // `continuing` is true only when "What happens next?" appends new scenes.
  const prevSceneCount = useRef(scenes.length);
  useEffect(() => {
    if (continuing && scenes.length > prevSceneCount.current) {
      setCurrent(prevSceneCount.current); // first newly appended scene
      setFadeKey((k) => k + 1);
    }
    prevSceneCount.current = scenes.length;
  }, [scenes.length, continuing]);

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

  // Auto-advance: when typewriter finishes and next scene is ready
  useEffect(() => {
    if (!autoPlay || !textDone || isLastScene || generating || continuing) return;
    if (pipeline.getStatus(current + 1) !== 'ready') return;
    const timer = setTimeout(() => changeTo(current + 1), 2000);
    return () => clearTimeout(timer);
  }, [textDone, current, autoPlay, isLastScene, generating, continuing, pipeline, changeTo]);

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
          <button
            onClick={() => setAutoPlay(!autoPlay)}
            className="text-xs px-2 py-0.5 rounded border transition-colors"
            style={{
              borderColor: autoPlay ? 'var(--primary)' : 'var(--border)',
              color: autoPlay ? 'var(--primary)' : 'var(--muted-foreground)',
            }}
          >
            {autoPlay ? 'Auto' : 'Manual'}
          </button>
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
        {/* Scene visual — video clip (dissolve from image) or image with camera iris */}
        {scene.videoBase64 ? (
          <div className="relative overflow-hidden rounded-lg max-h-[50vh] max-w-full">
            {/* Image underneath fades out during dissolve */}
            {scene.imageBase64 && (
              <img
                src={`data:${scene.mimeType || 'image/png'};base64,${scene.imageBase64}`}
                alt=""
                className="absolute inset-0 w-full h-full object-contain"
                style={{
                  animation: 'dissolveOut 500ms ease-in forwards',
                  boxShadow: '0 0 80px rgba(180, 140, 60, 0.12), 0 8px 40px rgba(0,0,0,0.7)',
                }}
              />
            )}
            <video
              src={`data:${scene.videoMimeType || 'video/mp4'};base64,${scene.videoBase64}`}
              autoPlay
              loop
              muted
              playsInline
              className="max-h-[50vh] max-w-full object-contain"
              style={{
                animation: 'dissolveIn 800ms ease-out',
                boxShadow: '0 0 80px rgba(180, 140, 60, 0.12), 0 8px 40px rgba(0,0,0,0.7)',
              }}
            />
          </div>
        ) : scene.imageBase64 ? (
          <div className="relative overflow-hidden rounded-lg max-h-[50vh] max-w-full">
            <div
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
            {/* Graceful "still frame" badge when video generation failed */}
            {scene.videoFailed && (
              <div
                className="absolute bottom-2 right-2 px-2 py-1 rounded text-[10px] tracking-wide uppercase"
                style={{
                  background: 'rgba(0,0,0,0.6)',
                  color: 'oklch(0.7 0.02 80)',
                  backdropFilter: 'blur(4px)',
                }}
              >
                Still frame
              </div>
            )}
          </div>
        ) : null}

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

        {/* "What happens next?" + Rashomon + Generate Film on last scene */}
        {isLastScene && textDone && !continuing && !generating && (
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
            <div className="flex items-center gap-3">
              <button
                onClick={onRashomon}
                className="text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors border border-[var(--border)] rounded-md px-3 py-1.5 hover:border-[var(--primary)]"
                style={{ fontFamily: "'Georgia', 'Times New Roman', serif" }}
              >
                Tell it from the other side &hellip;
              </button>
              {veoEnabled && !filmComplete && (
                <button
                  onClick={onGenerateFilm}
                  disabled={filmGenerating}
                  className="text-xs font-medium transition-all rounded-md px-4 py-1.5 disabled:opacity-50"
                  style={{
                    fontFamily: "'Georgia', 'Times New Roman', serif",
                    background: filmGenerating ? 'var(--border)' : 'var(--primary)',
                    color: filmGenerating ? 'var(--muted-foreground)' : 'var(--primary-foreground)',
                    boxShadow: filmGenerating ? 'none' : '0 0 12px rgba(180, 140, 60, 0.3)',
                  }}
                >
                  {filmGenerating ? 'Generating...' : '\u25B6 Generate Film'}
                </button>
              )}
              {filmComplete && (
                <>
                  <button
                    onClick={onDownloadFilm}
                    className="text-xs text-[var(--foreground)] transition-colors border border-[var(--primary)] rounded-md px-3 py-1.5 hover:bg-[var(--primary)] hover:text-[var(--primary-foreground)]"
                    style={{ fontFamily: "'Georgia', 'Times New Roman', serif" }}
                  >
                    Download Film
                  </button>
                  {isDemoReel && (
                    <span
                      className="text-[10px] uppercase tracking-widest px-2 py-0.5 rounded border"
                      style={{
                        color: 'oklch(0.75 0.12 80)',
                        borderColor: 'oklch(0.55 0.08 80)',
                        fontFamily: "'Georgia', 'Times New Roman', serif",
                      }}
                    >
                      Demo Reel
                    </span>
                  )}
                </>
              )}
            </div>
          </div>
        )}

        {/* Film generation progress grid */}
        {filmGenerating && (
          <div className="flex flex-col items-center gap-3 mt-2" style={{ animation: 'fadeIn 400ms ease-out' }}>
            <div className="flex items-center gap-1.5 flex-wrap justify-center max-w-md">
              {scenes.map((s, i) => (
                <div
                  key={i}
                  className="relative w-12 h-8 rounded overflow-hidden border"
                  style={{
                    borderColor: s.videoBase64
                      ? 'var(--primary)'
                      : s.videoFailed
                        ? 'oklch(0.6 0.15 30)'
                        : 'var(--border)',
                    opacity: s.videoBase64 || s.videoFailed ? 1 : 0.6,
                  }}
                >
                  {s.imageBase64 && (
                    <img
                      src={`data:${s.mimeType || 'image/png'};base64,${s.imageBase64}`}
                      alt=""
                      className="absolute inset-0 w-full h-full object-cover"
                    />
                  )}
                  {/* Spinner overlay for pending scenes */}
                  {!s.videoBase64 && !s.videoFailed && (
                    <div className="absolute inset-0 flex items-center justify-center bg-black/50">
                      <span
                        className="w-3 h-3 border-2 border-[var(--primary)] border-t-transparent rounded-full"
                        style={{ animation: 'spin 800ms linear infinite' }}
                      />
                    </div>
                  )}
                  {/* Check for completed scenes */}
                  {s.videoBase64 && (
                    <div className="absolute inset-0 flex items-center justify-center bg-black/30">
                      <span className="text-[var(--primary)] text-xs font-bold">&#x2713;</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
            {filmProgress && (
              <p className="text-xs text-[var(--muted-foreground)] italic">{filmProgress}</p>
            )}
          </div>
        )}

        {/* Generating indicator — more scenes incoming */}
        {generating && isLastScene && textDone && (
          <div className="flex items-center gap-2 text-sm text-[var(--muted-foreground)] italic animate-pulse">
            <span className="inline-block w-2 h-2 rounded-full bg-[var(--primary)] animate-ping" />
            Next scene rolling...
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
        @keyframes dissolveOut {
          0% { opacity: 1; }
          70% { opacity: 0.3; }
          100% { opacity: 0; }
        }
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes blink {
          50% { opacity: 0; }
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
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
  const [stageEvents, setStageEvents] = useState<StageEvent[]>([]);
  const [resetKey, setResetKey] = useState(0);
  const [filmGenerating, setFilmGenerating] = useState(false);
  const [filmProgress, setFilmProgress] = useState<string | null>(null);
  const [filmComplete, setFilmComplete] = useState(false);
  const [videoClips, setVideoClips] = useState<Map<number, { base64: string; mimeType: string }>>(new Map());
  const [failedScenes, setFailedScenes] = useState<Set<number>>(new Set());
  const [veoEnabled, setVeoEnabled] = useState(true);
  const [isDemoReel, setIsDemoReel] = useState(false);

  const scenes = pairParts(parts).map((scene, i) => {
    const clip = videoClips.get(i);
    if (clip) {
      return { ...scene, videoBase64: clip.base64, videoMimeType: clip.mimeType };
    }
    if (failedScenes.has(i)) {
      return { ...scene, videoFailed: true };
    }
    return scene;
  });
  const stageStates = buildStageStates(stageEvents);

  const casting = extractCasting(parts);

  // ── Narration pipeline (page-level) ──────────────────────────
  // Lifted here so narration prefetch starts as soon as scene text
  // arrives, even while the CastingInterstitial is displayed.
  const [currentSceneIdx, setCurrentSceneIdx] = useState(0);
  const pipeline = useNarrationPipeline(scenes, currentSceneIdx, scenes.length > 0);

  // Reset narration cache on new story / rashomon
  const prevResetKey = useRef(resetKey);
  useEffect(() => {
    if (prevResetKey.current !== resetKey) {
      pipeline.reset();
      setCurrentSceneIdx(0);
      prevResetKey.current = resetKey;
    }
  }, [resetKey, pipeline]);

  // Gate: scene 0 narration ready → safe to transition from casting to SceneViewer.
  // pipeline.narrationReady is reactive state tracking currentSceneIdx (starts at 0).
  // Fallback: after 30s, show SceneViewer even without narration so images appear.
  // Narration typically takes 22-46s; this catches cases where it fully fails.
  const [narrationTimeout, setNarrationTimeout] = useState(false);
  useEffect(() => {
    if (scenes.length > 0 && !pipeline.narrationReady && loading) {
      const timer = setTimeout(() => setNarrationTimeout(true), 30_000);
      return () => clearTimeout(timer);
    }
    if (!loading) setNarrationTimeout(false);
  }, [scenes.length, pipeline.narrationReady, loading]);
  const firstSceneNarrationReady = scenes.length > 0 && (pipeline.narrationReady || narrationTimeout);

  // Auto-open viewer as soon as casting or first scene arrives (streaming)
  useEffect(() => {
    if (!viewerOpen && (loading || continuing || stats)) {
      if (scenes.length > 0 || casting) {
        setViewerOpen(true);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scenes.length, !!casting]);

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
      setStageEvents([]);
      setResetKey((k) => k + 1);
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
          } else if (data.type === 'stage') {
            setStageEvents((prev) => [...prev, data as StageEvent]);
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

  /** Generate Veo video clips for all scenes */
  async function generateFilm() {
    const rawScenes = pairParts(parts);
    const scenesWithImages = rawScenes.filter((s) => s.imageBase64);
    if (scenesWithImages.length === 0) return;

    setFilmGenerating(true);
    setFilmComplete(false);
    setFailedScenes(new Set());
    setIsDemoReel(false);
    setFilmProgress(`Starting film generation for ${scenesWithImages.length} scenes...`);

    try {
      const body = {
        scenes: scenesWithImages.map((s) => ({
          text: s.text,
          image_base64: s.imageBase64,
          mime_type: s.mimeType || 'image/png',
        })),
      };

      const res = await fetch('/api/live-video/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        if (res.status === 503) setVeoEnabled(false);
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let completed = 0;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const data = JSON.parse(line.slice(6));

          if (data.type === 'scene_video') {
            completed++;
            setFilmProgress(`Generated scene ${completed} of ${scenesWithImages.length}`);
            setVideoClips((prev) => {
              const next = new Map(prev);
              next.set(data.scene_idx, {
                base64: data.video_base64,
                mimeType: data.mime_type || 'video/mp4',
              });
              return next;
            });
          } else if (data.type === 'scene_video_error') {
            completed++;
            setFailedScenes((prev) => new Set(prev).add(data.scene_idx));
            setFilmProgress(`Scene ${data.scene_idx + 1} using still frame, continuing...`);
          } else if (data.type === 'film_complete') {
            if (data.completed > 0) {
              setFilmComplete(true);
              setFilmProgress(null);
            } else {
              // All scenes failed — try demo fallback
              await tryDemoFallback();
            }
          }
        }
      }
    } catch (e: unknown) {
      // Total failure (network, 503, etc.) — try demo fallback
      const fell = await tryDemoFallback();
      if (!fell) {
        setError(e instanceof Error ? e.message : String(e));
      }
      setFilmProgress(null);
    } finally {
      setFilmGenerating(false);
    }
  }

  /** Try loading pre-baked demo fallback clips. Returns true if successful. */
  async function tryDemoFallback(): Promise<boolean> {
    try {
      setFilmProgress('Trying demo reel fallback...');
      const res = await fetch('/api/live-video/demo-fallback');
      if (!res.ok) return false;
      const data = await res.json();
      if (!data.scenes || data.scenes.length === 0) return false;

      // Load pre-baked video clips into state
      const newClips = new Map<number, { base64: string; mimeType: string }>();
      for (let i = 0; i < data.scenes.length; i++) {
        const s = data.scenes[i];
        if (s.video_base64) {
          newClips.set(i, { base64: s.video_base64, mimeType: 'video/mp4' });
        }
      }

      if (newClips.size === 0) return false;

      setVideoClips(newClips);
      setIsDemoReel(true);
      setFilmComplete(true);
      setFilmProgress(null);
      return true;
    } catch {
      return false;
    }
  }

  /** Download assembled film */
  async function downloadFilm() {
    const clips = Array.from(videoClips.entries())
      .sort(([a], [b]) => a - b)
      .map(([, v]) => v.base64);

    if (clips.length === 0) return;

    try {
      const res = await fetch('/api/live-video/assemble', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ video_base64_list: clips }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      const data = await res.json();
      // Trigger download
      const blob = await fetch(`data:video/mp4;base64,${data.video_base64}`).then((r) => r.blob());
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'chrononoir-film.mp4';
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  /* ── Viewer overlay ──────────────────────────────────────────── */
  // SceneViewer mounts only when scene 0 narration is ready (or on
  // non-generating views like re-entering a finished story).
  if (viewerOpen && scenes.length > 0 && (firstSceneNarrationReady || !loading)) {
    return (
      <SceneViewer
        scenes={scenes}
        stats={stats}
        continuing={continuing}
        generating={loading}
        onClose={() => setViewerOpen(false)}
        onContinue={continueStory}
        onRashomon={rashomonRetell}
        onGenerateFilm={generateFilm}
        onDownloadFilm={downloadFilm}
        casting={casting}
        filmGenerating={filmGenerating}
        filmProgress={filmProgress}
        filmComplete={filmComplete}
        veoEnabled={veoEnabled}
        isDemoReel={isDemoReel}
        pipeline={pipeline}
        onSceneChange={setCurrentSceneIdx}
      />
    );
  }

  /* ── Casting interstitial — shown while casting/scenes stream in ── */
  // Stays visible until scene 0 narration is ready, then dissolves to SceneViewer.
  if (viewerOpen && loading && (casting || scenes.length > 0)) {
    return (
      <CastingInterstitial
        casting={casting ?? { text: '' }}
        onClose={() => setViewerOpen(false)}
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

      {/* Pipeline progress — real stage tracking from backend */}
      <PipelineProgress
        stages={stageStates}
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
