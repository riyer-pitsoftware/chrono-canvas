import { useEffect, useRef, useState } from 'react';

/**
 * PatienceMeter — an honest progress bar for unpredictable async work.
 *
 * Instead of faking completion %, it shows how much of the *timeout budget*
 * has been consumed. The bar fills toward the timeout limit:
 *   blue (relaxed) → amber (getting long) → red (near timeout)
 *
 * When the phase completes, the bar snaps to green.
 */

// Per-phase timeout budgets (seconds). These match backend timeouts
// but are intentionally a bit shorter so the bar fills before the hard cut.
const PHASE_BUDGETS: Record<string, number> = {
  // Story pipeline
  story_orchestrator: 15,
  image_to_story: 60,
  reference_image_analysis: 60,
  character_extraction: 45,
  scene_decomposition: 45,
  character_anchor_generation: 30,
  scene_prompt_generation: 90,
  scene_image_generation: 180,
  storyboard_coherence: 60,
  narration_script: 45,
  narration_audio: 90,
  video_assembly: 60,
  storyboard_export: 15,
  // Portrait pipeline
  extraction: 30,
  research: 30,
  face_search: 20,
  prompt_generation: 45,
  image_generation: 120,
  validation: 30,
  facial_compositing: 60,
  export: 10,
};

const DEFAULT_BUDGET = 60;

function getBarColor(pct: number): string {
  if (pct < 0.5) return 'var(--patience-blue, #3b82f6)';
  if (pct < 0.8) return 'var(--patience-amber, #f59e0b)';
  return 'var(--patience-red, #ef4444)';
}

function formatElapsed(ms: number): string {
  const s = ms / 1000;
  if (s < 1) return `${Math.round(ms)}ms`;
  if (s < 10) return `${s.toFixed(1)}s`;
  return `${Math.round(s)}s`;
}

interface PatienceMeterProps {
  phase: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  /** Elapsed ms from agent_trace (for completed phases) */
  elapsedMs?: number;
}

export function PatienceMeter({ phase, status, elapsedMs }: PatienceMeterProps) {
  const budget = PHASE_BUDGETS[phase] ?? DEFAULT_BUDGET;
  const [elapsed, setElapsed] = useState(0);
  const startRef = useRef<number | null>(null);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    if (status !== 'running') {
      startRef.current = null;
      cancelAnimationFrame(rafRef.current);
      setElapsed(0);
      return;
    }

    startRef.current = Date.now();

    function tick() {
      if (startRef.current === null) return;
      setElapsed(Date.now() - startRef.current);
      rafRef.current = requestAnimationFrame(tick);
    }
    rafRef.current = requestAnimationFrame(tick);

    return () => cancelAnimationFrame(rafRef.current);
  }, [status]);

  const pct = Math.min(elapsed / (budget * 1000), 1);
  const completedPct = elapsedMs != null ? Math.min(elapsedMs / (budget * 1000), 1) : 0;

  if (status === 'pending') {
    return <div className="mt-1 h-1 w-full rounded-full bg-[var(--muted)] opacity-40" />;
  }

  if (status === 'error') {
    return (
      <div className="mt-1 h-1 w-full rounded-full bg-[var(--muted)] overflow-hidden">
        <div className="h-full rounded-full bg-red-500" style={{ width: '100%' }} />
      </div>
    );
  }

  if (status === 'completed') {
    return (
      <div className="mt-1 h-1 w-full rounded-full bg-[var(--muted)] overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500 ease-out"
          style={{
            width: `${Math.max(completedPct * 100, 8)}%`,
            backgroundColor: 'var(--patience-green, #22c55e)',
          }}
        />
      </div>
    );
  }

  // status === "running"
  return (
    <div className="mt-1 space-y-0.5">
      <div className="h-1.5 w-full rounded-full bg-[var(--muted)] overflow-hidden">
        <div
          className="h-full rounded-full transition-[width] duration-200 ease-linear"
          style={{
            width: `${Math.max(pct * 100, 2)}%`,
            backgroundColor: getBarColor(pct),
            boxShadow: `0 0 6px ${getBarColor(pct)}40`,
          }}
        />
      </div>
      <div className="flex justify-between text-[10px] text-[var(--muted-foreground)]">
        <span>{formatElapsed(elapsed)}</span>
        <span className="opacity-60">timeout {budget}s</span>
      </div>
    </div>
  );
}
