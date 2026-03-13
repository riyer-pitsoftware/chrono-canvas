import { useState, useRef, useEffect, useCallback } from 'react';

type NarrationStatus = 'idle' | 'fetching' | 'ready' | 'error';

type CacheEntry = {
  status: NarrationStatus;
  audio: HTMLAudioElement | null;
  blobUrl: string | null;
};

type Scene = {
  text: string;
  imageBase64?: string;
  mimeType?: string;
};

const MAX_CONCURRENT = 2;

export function useNarrationPipeline(
  scenes: Scene[],
  currentIndex: number,
  active: boolean,
) {
  const cache = useRef<Map<number, CacheEntry>>(new Map());
  const abortMap = useRef<Map<number, AbortController>>(new Map());
  const inflightCount = useRef(0);
  const [currentReady, setCurrentReady] = useState(false);
  // Track current index in a ref so async callbacks see the latest value
  const currentRef = useRef(currentIndex);
  currentRef.current = currentIndex;

  // Build priority-ordered queue of scene indices to fetch
  const buildQueue = useCallback(
    (cur: number, total: number): number[] => {
      const order: number[] = [];
      // Current, then +1, +2, then ascending remainder
      for (const offset of [0, 1, 2]) {
        const idx = cur + offset;
        if (idx < total) order.push(idx);
      }
      for (let i = 0; i < total; i++) {
        if (!order.includes(i)) order.push(i);
      }
      return order;
    },
    [],
  );

  // Fetch narration for a single scene
  const fetchNarration = useCallback((idx: number, text: string) => {
    if (!text) {
      // No text → mark ready immediately (image-only scene)
      cache.current.set(idx, { status: 'ready', audio: null, blobUrl: null });
      if (idx === currentRef.current) setCurrentReady(true);
      return;
    }

    cache.current.set(idx, { status: 'fetching', audio: null, blobUrl: null });
    inflightCount.current++;

    const ctrl = new AbortController();
    abortMap.current.set(idx, ctrl);

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
        cache.current.set(idx, { status: 'ready', audio, blobUrl: url });
        if (idx === currentRef.current) setCurrentReady(true);
      })
      .catch((err) => {
        if (err.name === 'AbortError') return;
        console.warn(`Narration failed for scene ${idx}:`, err);
        cache.current.set(idx, { status: 'error', audio: null, blobUrl: null });
        // Unblock cinema on error so it proceeds without audio
        if (idx === currentRef.current) setCurrentReady(true);
      })
      .finally(() => {
        if (!ctrl.signal.aborted) {
          inflightCount.current--;
          abortMap.current.delete(idx);
        }
        // Drain queue — schedule next fetch
        drainQueue();
      });
  }, []);

  // Queue ref to coordinate between schedule and drain
  const queueRef = useRef<number[]>([]);

  const drainQueue = useCallback(() => {
    while (inflightCount.current < MAX_CONCURRENT && queueRef.current.length > 0) {
      const nextIdx = queueRef.current.shift()!;
      const entry = cache.current.get(nextIdx);
      // Skip if already fetched/fetching
      if (entry && entry.status !== 'idle') continue;
      const scene = scenesRef.current[nextIdx];
      if (!scene) continue;
      fetchNarration(nextIdx, scene.text);
    }
  }, [fetchNarration]);

  // Keep scenes in a ref for async access
  const scenesRef = useRef(scenes);
  scenesRef.current = scenes;

  // Priority bumping: abort lowest-priority inflight if current scene needs fetching
  const bumpPriority = useCallback(
    (cur: number) => {
      const currentEntry = cache.current.get(cur);
      if (currentEntry && currentEntry.status !== 'idle') return; // already handled

      // If we're at max concurrency, abort the fetch furthest from current
      if (inflightCount.current >= MAX_CONCURRENT) {
        let worstIdx = -1;
        let worstDist = -1;
        for (const [idx] of abortMap.current) {
          const dist = Math.abs(idx - cur);
          if (dist > worstDist && idx !== cur) {
            worstDist = dist;
            worstIdx = idx;
          }
        }
        if (worstIdx >= 0 && worstDist > 1) {
          const ctrl = abortMap.current.get(worstIdx);
          ctrl?.abort();
          abortMap.current.delete(worstIdx);
          inflightCount.current--;
          // Reset the aborted entry so it can be re-queued later
          cache.current.set(worstIdx, { status: 'idle', audio: null, blobUrl: null });
        }
      }
    },
    [],
  );

  // Schedule fetches when scenes or currentIndex changes
  useEffect(() => {
    if (!active) return;

    // Check if current scene is already ready
    const currentEntry = cache.current.get(currentIndex);
    if (currentEntry?.status === 'ready') {
      setCurrentReady(true);
    } else if (currentEntry?.status === 'error') {
      setCurrentReady(true); // unblock cinema
    } else {
      setCurrentReady(false);
    }

    // Bump priority for current scene
    bumpPriority(currentIndex);

    // Build and set queue
    const queue = buildQueue(currentIndex, scenes.length);
    // Filter to only scenes that need fetching
    queueRef.current = queue.filter((idx) => {
      const entry = cache.current.get(idx);
      return !entry || entry.status === 'idle';
    });

    drainQueue();
  }, [scenes.length, currentIndex, active, buildQueue, bumpPriority, drainQueue]);

  // When currentIndex changes, pause previous scene audio
  const prevIndex = useRef(currentIndex);
  useEffect(() => {
    if (prevIndex.current !== currentIndex) {
      const prevEntry = cache.current.get(prevIndex.current);
      if (prevEntry?.audio) {
        prevEntry.audio.pause();
        prevEntry.audio.currentTime = 0;
      }
      prevIndex.current = currentIndex;
    }
  }, [currentIndex]);

  const playCurrentNarration = useCallback(() => {
    const entry = cache.current.get(currentRef.current);
    if (entry?.audio) {
      entry.audio.currentTime = 0;
      entry.audio.play().catch(() => {});
    }
  }, []);

  const stopNarration = useCallback(() => {
    const entry = cache.current.get(currentRef.current);
    if (entry?.audio) {
      entry.audio.pause();
      entry.audio.currentTime = 0;
    }
  }, []);

  const getStatus = useCallback((idx: number): NarrationStatus => {
    return cache.current.get(idx)?.status || 'idle';
  }, []);

  const reset = useCallback(() => {
    // Abort all in-flight fetches
    for (const ctrl of abortMap.current.values()) {
      ctrl.abort();
    }
    abortMap.current.clear();
    inflightCount.current = 0;

    // Revoke all blob URLs and clear cache
    for (const entry of cache.current.values()) {
      if (entry.blobUrl) {
        URL.revokeObjectURL(entry.blobUrl);
      }
      if (entry.audio) {
        entry.audio.pause();
      }
    }
    cache.current.clear();
    queueRef.current = [];
    setCurrentReady(false);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      for (const ctrl of abortMap.current.values()) {
        ctrl.abort();
      }
      for (const entry of cache.current.values()) {
        if (entry.blobUrl) URL.revokeObjectURL(entry.blobUrl);
        if (entry.audio) entry.audio.pause();
      }
    };
  }, []);

  return {
    narrationReady: currentReady,
    playCurrentNarration,
    stopNarration,
    getStatus,
    reset,
  };
}
