import { useState, useRef, useEffect, useCallback } from 'react';

type NarrationStatus = 'idle' | 'fetching' | 'ready' | 'error';

/**
 * Streaming PCM16 audio player using Web Audio API.
 * Schedules AudioBufferSourceNodes from raw PCM16 LE chunks.
 */
class PCMPlayer {
  private ctx: AudioContext;
  private nextTime = 0;
  private leftover: Uint8Array | null = null;
  private sources: AudioBufferSourceNode[] = [];
  onended: (() => void) | null = null;

  constructor() {
    this.ctx = new AudioContext({ sampleRate: 24000 });
  }

  /** Schedule a raw PCM16 LE chunk for playback. */
  schedule(raw: Uint8Array) {
    // Merge leftover byte from previous chunk
    let data = raw;
    if (this.leftover) {
      const merged = new Uint8Array(this.leftover.length + data.length);
      merged.set(this.leftover);
      merged.set(data, this.leftover.length);
      data = merged;
      this.leftover = null;
    }

    // PCM16 = 2 bytes per sample — stash odd trailing byte
    if (data.length % 2 !== 0) {
      this.leftover = data.slice(-1);
      data = data.slice(0, -1);
    }

    if (data.length < 2) return;

    // Convert Int16 LE → Float32
    const int16 = new Int16Array(data.buffer, data.byteOffset, data.length / 2);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) {
      float32[i] = int16[i] / 32768;
    }

    const buffer = this.ctx.createBuffer(1, float32.length, 24000);
    buffer.getChannelData(0).set(float32);

    const source = this.ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(this.ctx.destination);

    const when = Math.max(this.ctx.currentTime + 0.005, this.nextTime);
    source.start(when);
    this.nextTime = when + buffer.duration;
    this.sources.push(source);
  }

  /** Call when the stream is fully consumed — attaches onended to last node. */
  finalize() {
    const last = this.sources[this.sources.length - 1];
    if (last && this.onended) {
      last.onended = this.onended;
    }
  }

  stop() {
    for (const s of this.sources) {
      try {
        s.stop();
      } catch {
        /* already stopped */
      }
    }
    this.sources = [];
    this.ctx.close().catch(() => {});
  }

  get currentTime() {
    return this.ctx.currentTime;
  }
}

type CacheEntry = {
  status: NarrationStatus;
  retries: number;
  // Streaming state
  chunks: Uint8Array[];
  totalBytes: number;
  streamDone: boolean;
  // Playback — created on play()
  player: PCMPlayer | null;
  chunksScheduled: number;
};

type Scene = {
  text: string;
  imageBase64?: string;
  mimeType?: string;
};

const MAX_CONCURRENT = 4;
// Mark narration as ready once we have this many PCM bytes (~0.25s at 24kHz 16-bit mono)
const READY_THRESHOLD_BYTES = 12000;

function makeEntry(retries = 0): CacheEntry {
  return {
    status: 'idle',
    retries,
    chunks: [],
    totalBytes: 0,
    streamDone: false,
    player: null,
    chunksScheduled: 0,
  };
}

export function useNarrationPipeline(scenes: Scene[], currentIndex: number, active: boolean) {
  const cache = useRef<Map<number, CacheEntry>>(new Map());
  const abortMap = useRef<Map<number, AbortController>>(new Map());
  const inflightCount = useRef(0);
  const [currentReady, setCurrentReady] = useState(false);
  const [currentDone, setCurrentDone] = useState(false);
  const currentRef = useRef(currentIndex);
  currentRef.current = currentIndex;

  // Build priority-ordered queue of scene indices to fetch
  const buildQueue = useCallback((cur: number, total: number): number[] => {
    const order: number[] = [];
    for (const offset of [0, 1, 2]) {
      const idx = cur + offset;
      if (idx < total) order.push(idx);
    }
    for (let i = 0; i < total; i++) {
      if (!order.includes(i)) order.push(i);
    }
    return order;
  }, []);

  const MAX_RETRIES = 2;

  // Fetch narration for a single scene using streaming endpoint
  const fetchNarration = useCallback((idx: number, text: string) => {
    if (!text) {
      const entry = makeEntry();
      entry.status = 'ready';
      entry.streamDone = true;
      cache.current.set(idx, entry);
      if (idx === currentRef.current) setCurrentReady(true);
      return;
    }

    const prev = cache.current.get(idx);
    const retryCount = prev?.retries ?? 0;
    const entry = makeEntry(retryCount);
    entry.status = 'fetching';
    cache.current.set(idx, entry);
    inflightCount.current++;

    const ctrl = new AbortController();
    abortMap.current.set(idx, ctrl);

    fetch('/api/live-voice/narrate-stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
      signal: ctrl.signal,
    })
      .then(async (res) => {
        if (!res.ok) throw new Error(`Narration stream failed: ${res.status}`);
        const reader = res.body?.getReader();
        if (!reader) throw new Error('No readable stream');

        while (true) {
          const { done, value } = await reader.read();
          if (done || ctrl.signal.aborted) break;
          if (!value || value.length === 0) continue;

          entry.chunks.push(value);
          entry.totalBytes += value.length;

          // If this scene is currently playing, schedule the new chunk
          if (entry.player && entry.chunksScheduled < entry.chunks.length) {
            for (let i = entry.chunksScheduled; i < entry.chunks.length; i++) {
              entry.player.schedule(entry.chunks[i]);
            }
            entry.chunksScheduled = entry.chunks.length;
          }

          // Mark ready after threshold
          if (entry.status === 'fetching' && entry.totalBytes >= READY_THRESHOLD_BYTES) {
            entry.status = 'ready';
            if (idx === currentRef.current) setCurrentReady(true);
          }
        }

        // Stream complete
        if (!ctrl.signal.aborted) {
          entry.streamDone = true;
          if (entry.status === 'fetching') {
            // Got some data but below threshold — still mark ready
            entry.status = entry.totalBytes > 0 ? 'ready' : 'error';
            if (idx === currentRef.current) setCurrentReady(true);
          }
          if (entry.player) {
            entry.player.finalize();
          }
        }
      })
      .catch((err) => {
        if (err.name === 'AbortError') return;
        console.warn(`Narration stream failed for scene ${idx} (attempt ${retryCount + 1}):`, err);

        if (retryCount < MAX_RETRIES) {
          const retry = makeEntry(retryCount + 1);
          cache.current.set(idx, retry);
        } else {
          entry.status = 'error';
          entry.streamDone = true;
          if (idx === currentRef.current) setCurrentReady(true);
        }
      })
      .finally(() => {
        if (!ctrl.signal.aborted) {
          inflightCount.current--;
          abortMap.current.delete(idx);
        }
        drainQueue();
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Mutual recursion: fetchNarration → drainQueue → fetchNarration

  // Queue ref to coordinate between schedule and drain
  const queueRef = useRef<number[]>([]);

  const drainQueue = useCallback(() => {
    while (inflightCount.current < MAX_CONCURRENT && queueRef.current.length > 0) {
      const nextIdx = queueRef.current.shift()!;
      const entry = cache.current.get(nextIdx);
      if (entry && entry.status !== 'idle') continue;
      const scene = scenesRef.current[nextIdx];
      if (!scene) continue;
      fetchNarration(nextIdx, scene.text);
    }
  }, [fetchNarration]);

  const scenesRef = useRef(scenes);
  scenesRef.current = scenes;

  // Priority bumping
  const bumpPriority = useCallback((cur: number) => {
    const currentEntry = cache.current.get(cur);
    if (currentEntry && currentEntry.status !== 'idle') return;

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
        cache.current.set(worstIdx, makeEntry());
      }
    }
  }, []);

  // Schedule fetches when scenes or currentIndex changes
  useEffect(() => {
    if (!active) return;

    const currentEntry = cache.current.get(currentIndex);
    if (currentEntry?.status === 'ready') {
      setCurrentReady(true);
    } else if (currentEntry?.status === 'error') {
      setCurrentReady(true);
    } else {
      setCurrentReady(false);
    }
    setCurrentDone(false);

    bumpPriority(currentIndex);

    const queue = buildQueue(currentIndex, scenes.length);
    queueRef.current = queue.filter((idx) => {
      const entry = cache.current.get(idx);
      return !entry || entry.status === 'idle';
    });

    drainQueue();
  }, [scenes.length, currentIndex, active, buildQueue, bumpPriority, drainQueue]);

  // When currentIndex changes, stop previous scene's player
  const prevIndex = useRef(currentIndex);
  useEffect(() => {
    if (prevIndex.current !== currentIndex) {
      const prevEntry = cache.current.get(prevIndex.current);
      if (prevEntry?.player) {
        prevEntry.player.stop();
        prevEntry.player = null;
        prevEntry.chunksScheduled = 0;
      }
      prevIndex.current = currentIndex;
    }
  }, [currentIndex]);

  const playCurrentNarration = useCallback(() => {
    const entry = cache.current.get(currentRef.current);
    if (!entry || entry.chunks.length === 0) return;

    // Stop existing player if replaying
    if (entry.player) {
      entry.player.stop();
    }

    const player = new PCMPlayer();
    entry.player = player;
    setCurrentDone(false);

    // Signal when playback finishes
    player.onended = () => setCurrentDone(true);

    // Schedule all accumulated chunks
    for (const chunk of entry.chunks) {
      player.schedule(chunk);
    }
    entry.chunksScheduled = entry.chunks.length;

    // If stream is done, finalize (sets onended on last node)
    if (entry.streamDone) {
      player.finalize();
    }
  }, []);

  const stopNarration = useCallback(() => {
    const entry = cache.current.get(currentRef.current);
    if (entry?.player) {
      entry.player.stop();
      entry.player = null;
      entry.chunksScheduled = 0;
    }
  }, []);

  const getStatus = useCallback((idx: number): NarrationStatus => {
    return cache.current.get(idx)?.status || 'idle';
  }, []);

  const reset = useCallback(() => {
    for (const ctrl of abortMap.current.values()) {
      ctrl.abort();
    }
    abortMap.current.clear();
    inflightCount.current = 0;

    for (const entry of cache.current.values()) {
      if (entry.player) {
        entry.player.stop();
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
        if (entry.player) entry.player.stop();
      }
    };
  }, []);

  return {
    narrationReady: currentReady,
    narrationDone: currentDone,
    playCurrentNarration,
    stopNarration,
    getStatus,
    reset,
  };
}
