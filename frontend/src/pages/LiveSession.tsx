import { useState, useRef, useCallback, useEffect } from 'react';

/* ── Turn state — drives all visual cues ──────────────────────── */

type TurnState = 'idle' | 'listening' | 'narrating' | 'generating_image';

const TURN_LABELS: Record<TurnState, string> = {
  idle: '',
  listening: 'Your turn \u2014 speak now',
  narrating: 'Dash is speaking\u2026',
  generating_image: 'Conjuring the scene\u2026',
};

/* ── Audio helpers ────────────────────────────────────────────── */

function float32ToInt16(float32: Float32Array): Int16Array {
  const int16 = new Int16Array(float32.length);
  for (let i = 0; i < float32.length; i++) {
    int16[i] = Math.max(-32768, Math.min(32767, Math.round(float32[i] * 32768)));
  }
  return int16;
}

function int16ToFloat32(int16: Int16Array): Float32Array {
  const float32 = new Float32Array(int16.length);
  for (let i = 0; i < int16.length; i++) {
    float32[i] = int16[i] / 32768;
  }
  return float32;
}

function toBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

function fromBase64(base64: string): Uint8Array {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

/**
 * Play a short "your turn" chime using Web Audio API oscillators.
 * Two quick ascending tones — subtle but unmistakable.
 */
function playTurnChime(ctx: AudioContext) {
  const now = ctx.currentTime;
  const gain = ctx.createGain();
  gain.connect(ctx.destination);
  gain.gain.setValueAtTime(0.08, now);
  gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);

  // First tone
  const osc1 = ctx.createOscillator();
  osc1.type = 'sine';
  osc1.frequency.setValueAtTime(880, now);
  osc1.connect(gain);
  osc1.start(now);
  osc1.stop(now + 0.12);

  // Second tone (higher)
  const gain2 = ctx.createGain();
  gain2.connect(ctx.destination);
  gain2.gain.setValueAtTime(0.08, now + 0.12);
  gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.45);

  const osc2 = ctx.createOscillator();
  osc2.type = 'sine';
  osc2.frequency.setValueAtTime(1175, now + 0.12); // D6
  osc2.connect(gain2);
  osc2.start(now + 0.12);
  osc2.stop(now + 0.3);
}

/* ── LiveSession component ────────────────────────────────────── */

export function LiveSession() {
  const [sessionActive, setSessionActive] = useState(false);
  const [turn, setTurn] = useState<TurnState>('idle');
  const [currentImage, setCurrentImage] = useState<{ data: string; description: string } | null>(null);
  const [prevImage, setPrevImage] = useState<{ data: string; description: string } | null>(null);
  const [transcript, setTranscript] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [imageTransition, setImageTransition] = useState<'idle' | 'dissolve-out' | 'iris-in'>('idle');
  const [sessionStats, setSessionStats] = useState<{ scenes: number; startTime: number } | null>(null);
  const [summary, setSummary] = useState<{ scenes: number; minutes: number } | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const captureCtxRef = useRef<AudioContext | null>(null);
  const playbackCtxRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const nextPlayTimeRef = useRef(0);
  const sceneCountRef = useRef(0);
  // True while Gemini is speaking — suppress mic audio to avoid self-interruption
  const geminiSpeakingRef = useRef(false);
  // Track previous turn to detect transitions
  const prevTurnRef = useRef<TurnState>('idle');

  /* ── Audio playback ─────────────────────────────────────────── */

  const audioChunksReceivedRef = useRef(0);

  const playAudioChunk = useCallback((base64Data: string) => {
    const ctx = playbackCtxRef.current;
    if (!ctx) {
      console.error('[LiveSession] No playback AudioContext — was it created during startSession?');
      return;
    }

    // Resume if suspended (shouldn't happen since we create during click)
    if (ctx.state === 'suspended') {
      console.warn('[LiveSession] Playback context suspended, resuming...');
      ctx.resume();
    }

    audioChunksReceivedRef.current += 1;
    if (audioChunksReceivedRef.current === 1) {
      console.log('[LiveSession] First audio chunk received for playback, ctx state:', ctx.state);
    } else if (audioChunksReceivedRef.current % 50 === 0) {
      console.log('[LiveSession] Audio chunks played:', audioChunksReceivedRef.current);
    }

    const bytes = fromBase64(base64Data);
    const int16 = new Int16Array(bytes.buffer);
    const float32 = int16ToFloat32(int16);

    const buffer = ctx.createBuffer(1, float32.length, 24000);
    buffer.getChannelData(0).set(float32);

    const src = ctx.createBufferSource();
    src.buffer = buffer;
    src.connect(ctx.destination);

    // Schedule sequentially to avoid overlapping chunks
    const now = ctx.currentTime;
    const startAt = Math.max(now, nextPlayTimeRef.current);
    src.start(startAt);
    nextPlayTimeRef.current = startAt + buffer.duration;
  }, []);

  /* ── Image arrival with iris animation ──────────────────────── */

  const handleImageArrival = useCallback((data: string, description: string) => {
    sceneCountRef.current += 1;

    if (currentImage) {
      // Dissolve out old image, then iris in new
      setPrevImage(currentImage);
      setImageTransition('dissolve-out');
      setTimeout(() => {
        setPrevImage(null);
        setCurrentImage({ data, description });
        setImageTransition('iris-in');
        setTimeout(() => setImageTransition('idle'), 1200);
      }, 600);
    } else {
      setCurrentImage({ data, description });
      setImageTransition('iris-in');
      setTimeout(() => setImageTransition('idle'), 1200);
    }
  }, [currentImage]);

  /* ── Turn transition handler ─────────────────────────────────── */

  // Ref to track pending listening-transition timer so we can cancel it
  const listeningTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleTurnChange = useCallback((newTurn: TurnState) => {
    const prev = prevTurnRef.current;

    if (newTurn === 'listening') {
      // Don't switch to listening immediately — audio chunks are received faster
      // than they play back. Wait until scheduled playback actually finishes,
      // otherwise the mic unmutes while Gemini's voice is still playing from
      // the queue, causing echo feedback.
      const ctx = playbackCtxRef.current;
      const remainingPlayback = ctx
        ? Math.max(0, nextPlayTimeRef.current - ctx.currentTime)
        : 0;

      // Add a small buffer (300ms) after playback ends
      const delay = Math.max(100, remainingPlayback * 1000 + 300);

      // Cancel any previous pending transition
      if (listeningTimerRef.current) clearTimeout(listeningTimerRef.current);

      console.log(
        '[LiveSession] turn_complete received, playback remaining:',
        remainingPlayback.toFixed(2) + 's, delaying listening by',
        Math.round(delay) + 'ms',
      );

      listeningTimerRef.current = setTimeout(() => {
        listeningTimerRef.current = null;
        prevTurnRef.current = 'listening';
        setTurn('listening');
        geminiSpeakingRef.current = false;

        // Play chime when transitioning TO listening from narrating/generating
        if (prev === 'narrating' || prev === 'generating_image') {
          if (playbackCtxRef.current) {
            playTurnChime(playbackCtxRef.current);
          }
        }
      }, delay);
    } else if (newTurn === 'narrating') {
      // Cancel any pending listening transition — Gemini is speaking again
      if (listeningTimerRef.current) {
        clearTimeout(listeningTimerRef.current);
        listeningTimerRef.current = null;
      }
      prevTurnRef.current = newTurn;
      setTurn(newTurn);
      geminiSpeakingRef.current = true;
    } else {
      prevTurnRef.current = newTurn;
      setTurn(newTurn);
    }
  }, []);

  /* ── WebSocket message handler ──────────────────────────────── */

  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const msg = JSON.parse(event.data);
      switch (msg.type) {
        case 'audio':
          if (prevTurnRef.current !== 'narrating') {
            handleTurnChange('narrating');
          }
          playAudioChunk(msg.data);
          break;
        case 'image':
          handleImageArrival(msg.data, msg.description || '');
          break;
        case 'status':
          if (msg.content === 'listening') {
            handleTurnChange('listening');
          } else if (msg.content === 'generating_image') {
            handleTurnChange('generating_image');
          } else if (msg.content === 'narrating') {
            handleTurnChange('narrating');
          }
          break;
        case 'transcript':
          setTranscript(msg.content || '');
          break;
        case 'error':
          setError(msg.content || 'Unknown error');
          break;
        default:
          break;
      }
    } catch {
      console.warn('LiveSession: failed to parse WS message');
    }
  }, [playAudioChunk, handleImageArrival, handleTurnChange]);

  /* ── Start session ──────────────────────────────────────────── */

  const startSession = useCallback(async () => {
    setError(null);
    setSummary(null);
    setTranscript('');
    setCurrentImage(null);
    setPrevImage(null);
    setImageTransition('idle');
    setTurn('idle');
    prevTurnRef.current = 'idle';
    sceneCountRef.current = 0;
    nextPlayTimeRef.current = 0;
    geminiSpeakingRef.current = false;

    // Request mic access
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      console.log('[LiveSession] Mic access granted, tracks:', stream.getAudioTracks().length);
    } catch {
      setError('Microphone access denied. Please allow mic access and try again.');
      return;
    }
    streamRef.current = stream;

    // Create AudioContexts NOW — during the click handler — so they start "running"
    // (creating outside user gesture risks "suspended" state due to autoplay policy)
    const audioContext = new AudioContext({ sampleRate: 16000 });
    captureCtxRef.current = audioContext;

    const playbackContext = new AudioContext({ sampleRate: 24000 });
    playbackCtxRef.current = playbackContext;
    audioChunksReceivedRef.current = 0;

    console.log(
      '[LiveSession] AudioContexts created — capture:', audioContext.state,
      'playback:', playbackContext.state,
    );

    // Ensure both are running (belt-and-suspenders for autoplay policy)
    if (audioContext.state === 'suspended') {
      await audioContext.resume();
    }
    if (playbackContext.state === 'suspended') {
      await playbackContext.resume();
    }

    // Connect WebSocket
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/api/live-session/ws`);
    wsRef.current = ws;

    // Track audio send stats for diagnostics
    let audioChunksSent = 0;
    let geminiMutedChunks = 0;

    ws.onopen = () => {
      console.log('[LiveSession] WebSocket connected, sending start');
      ws.send(JSON.stringify({ type: 'start' }));
      setSessionActive(true);
      handleTurnChange('listening');
      setSessionStats({ scenes: 0, startTime: Date.now() });

      // Wire up audio capture to the already-running AudioContext
      const source = audioContext.createMediaStreamSource(stream);
      sourceRef.current = source;

      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (e) => {
        if (ws.readyState !== WebSocket.OPEN) return;
        // Don't send mic audio while Gemini is speaking
        if (geminiSpeakingRef.current) {
          geminiMutedChunks++;
          return;
        }

        const float32 = e.inputBuffer.getChannelData(0);

        // Very low VAD threshold — only filters dead digital silence.
        // Gemini Live API needs continuous audio for its own VAD, so we pass
        // through anything above near-zero (ambient room noise, quiet speech).
        // The old threshold (0.01) was too aggressive and blocked real speech.
        let sumSq = 0;
        for (let i = 0; i < float32.length; i++) {
          sumSq += float32[i] * float32[i];
        }
        const rms = Math.sqrt(sumSq / float32.length);
        if (rms < 0.002) return;

        const int16 = float32ToInt16(float32);
        const base64 = toBase64(int16.buffer);
        ws.send(JSON.stringify({ type: 'audio', data: base64 }));
        audioChunksSent++;
        if (audioChunksSent === 1) {
          console.log('[LiveSession] First audio chunk sent');
        }
        if (audioChunksSent % 50 === 0) {
          console.log('[LiveSession] Audio stats — sent:', audioChunksSent, 'muted:', geminiMutedChunks);
        }
      };

      source.connect(processor);
      processor.connect(audioContext.destination);
      console.log('[LiveSession] Audio pipeline wired: mic → processor → destination');
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type !== 'ping') {
          console.log('[LiveSession] WS recv:', msg.type, msg.type === 'status' ? msg.content : '');
        }
      } catch { /* logged in handler */ }
      handleMessage(event);
    };

    ws.onerror = (event) => {
      console.error('[LiveSession] WebSocket error:', event);
      setError('WebSocket connection error.');
    };

    ws.onclose = (event) => {
      console.log('[LiveSession] WebSocket closed, code:', event.code, 'reason:', event.reason);
      cleanupCapture();
      setSessionActive(false);
      setTurn('idle');
      // Show summary
      if (sessionStats) {
        const elapsed = (Date.now() - sessionStats.startTime) / 60000;
        setSummary({ scenes: sceneCountRef.current, minutes: Math.round(elapsed * 10) / 10 });
      }
    };
  }, [handleMessage, handleTurnChange, sessionStats]);

  /* ── Stop session ───────────────────────────────────────────── */

  const cleanupCapture = useCallback(() => {
    if (listeningTimerRef.current) {
      clearTimeout(listeningTimerRef.current);
      listeningTimerRef.current = null;
    }
    processorRef.current?.disconnect();
    sourceRef.current?.disconnect();
    captureCtxRef.current?.close().catch(() => {});
    playbackCtxRef.current?.close().catch(() => {});
    streamRef.current?.getTracks().forEach((t) => t.stop());
    processorRef.current = null;
    sourceRef.current = null;
    captureCtxRef.current = null;
    playbackCtxRef.current = null;
    streamRef.current = null;
  }, []);

  const stopSession = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'stop' }));
      wsRef.current.close();
    }
    cleanupCapture();
    setSessionActive(false);
    setTurn('idle');

    if (sessionStats) {
      const elapsed = (Date.now() - sessionStats.startTime) / 60000;
      setSummary({ scenes: sceneCountRef.current, minutes: Math.round(elapsed * 10) / 10 });
    }
  }, [cleanupCapture, sessionStats]);

  /* ── Cleanup on unmount ─────────────────────────────────────── */

  useEffect(() => {
    return () => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'stop' }));
        wsRef.current.close();
      }
      processorRef.current?.disconnect();
      sourceRef.current?.disconnect();
      captureCtxRef.current?.close().catch(() => {});
      playbackCtxRef.current?.close().catch(() => {});
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  /* ── Compute iris clip-path ─────────────────────────────────── */

  const irisClipPath =
    imageTransition === 'iris-in'
      ? undefined // handled by CSS animation
      : imageTransition === 'dissolve-out'
        ? 'circle(0% at 50% 50%)'
        : 'circle(75% at 50% 50%)';

  /* ── Turn-dependent styles ───────────────────────────────────── */

  const isListening = turn === 'listening';
  const isNarrating = turn === 'narrating';

  // Status indicator dot color
  const dotColor = isListening
    ? '#4ade80'   // green — your turn
    : isNarrating
      ? 'var(--primary)'  // amber — Dash speaking
      : '#f59e0b';        // orange — generating

  // Mic button appearance changes with turn state
  const micBorder = isListening
    ? '3px solid #4ade80'
    : isNarrating
      ? '2px solid oklch(0.25 0.02 60)'
      : '2px solid #f59e0b';

  const micBg = isListening
    ? 'oklch(0.12 0.03 145)'   // faint green tint
    : 'oklch(0.1 0.01 60)';

  const micStroke = isListening
    ? '#4ade80'
    : isNarrating
      ? 'oklch(0.35 0.02 60)'  // dimmed when not your turn
      : '#f59e0b';

  const micShadow = isListening
    ? '0 0 0 6px rgba(74, 222, 128, 0.15), 0 0 30px rgba(74, 222, 128, 0.08)'
    : isNarrating
      ? '0 0 15px rgba(0,0,0,0.4)'
      : '0 0 0 4px rgba(245, 158, 11, 0.12)';

  const micLabel = !sessionActive
    ? 'Tap to begin'
    : isListening
      ? 'Speak now'
      : isNarrating
        ? 'Dash is speaking'
        : 'Generating\u2026';

  const micLabelColor = isListening
    ? '#4ade80'
    : isNarrating
      ? 'oklch(0.4 0.02 60)'
      : '#f59e0b';

  /* ── Render ─────────────────────────────────────────────────── */

  return (
    <div
      className="fixed inset-0 z-40 flex flex-col items-center justify-between"
      style={{ backgroundColor: 'oklch(0.08 0.01 60)' }}
    >
      {/* ── Top: Status ──────────────────────────────────────── */}
      <div className="pt-8 pb-4 flex items-center gap-2 min-h-[48px]">
        {sessionActive && turn !== 'idle' && (
          <div
            key={turn}
            className="flex items-center gap-2 text-sm"
            style={{
              color: isListening ? '#4ade80' : 'oklch(0.65 0.03 80)',
              fontFamily: "'Georgia', 'Times New Roman', serif",
              animation: 'fadeIn 300ms ease-out',
              fontWeight: isListening ? 600 : 400,
            }}
          >
            <span
              className="inline-block w-2 h-2 rounded-full"
              style={{
                backgroundColor: dotColor,
                animation: isListening
                  ? 'pulse-dot-listening 1s ease-in-out infinite'
                  : 'pulse-dot 1.5s ease-in-out infinite',
              }}
            />
            {TURN_LABELS[turn]}
          </div>
        )}
      </div>

      {/* ── Center: Image area + transcript ──────────────────── */}
      <div className="flex-1 flex flex-col items-center justify-center px-8 gap-6 min-h-0 max-w-3xl w-full">
        {/* Previous image (dissolving out) */}
        {prevImage && imageTransition === 'dissolve-out' && (
          <div
            className="overflow-hidden rounded-lg"
            style={{
              animation: 'fadeOut 600ms ease-in forwards',
            }}
          >
            <img
              src={`data:image/png;base64,${prevImage.data}`}
              alt="Previous scene"
              className="max-h-[50vh] max-w-full object-contain"
              style={{ boxShadow: '0 0 80px rgba(180, 140, 60, 0.12)' }}
            />
          </div>
        )}

        {/* Current image with iris animation */}
        {currentImage && imageTransition !== 'dissolve-out' && (
          <div
            className="overflow-hidden rounded-lg"
            style={{
              clipPath: irisClipPath,
              animation: imageTransition === 'iris-in' ? 'irisOpen 1.2s ease-out forwards' : undefined,
            }}
          >
            <img
              src={`data:image/png;base64,${currentImage.data}`}
              alt={currentImage.description || 'Scene'}
              className="max-h-[50vh] max-w-full object-contain"
              style={{ boxShadow: '0 0 80px rgba(180, 140, 60, 0.12), 0 8px 40px rgba(0,0,0,0.7)' }}
            />
          </div>
        )}

        {/* Transcript text */}
        {transcript && (
          <p
            className="max-w-2xl text-center leading-relaxed text-lg"
            style={{
              fontFamily: "'Georgia', 'Times New Roman', serif",
              color: 'oklch(0.9 0.02 80)',
              textShadow: '0 1px 8px rgba(0,0,0,0.5)',
              animation: 'fadeIn 600ms ease-out',
            }}
          >
            {transcript}
          </p>
        )}

        {/* Error */}
        {error && (
          <div className="rounded-md border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400 max-w-md text-center">
            {error}
            {!sessionActive && (
              <button
                onClick={() => { setError(null); startSession(); }}
                className="ml-3 underline hover:text-red-300 transition-colors"
              >
                Retry
              </button>
            )}
          </div>
        )}

        {/* Summary (after session ends) */}
        {summary && !sessionActive && (
          <div
            className="text-center space-y-1"
            style={{
              animation: 'fadeIn 800ms ease-out',
              fontFamily: "'Georgia', 'Times New Roman', serif",
            }}
          >
            <p className="text-sm" style={{ color: 'oklch(0.7 0.03 80)' }}>
              {summary.scenes} scene{summary.scenes !== 1 ? 's' : ''} created, {summary.minutes} minute{summary.minutes !== 1 ? 's' : ''}
            </p>
            <p className="text-xs" style={{ color: 'oklch(0.5 0.02 80)' }}>
              Session complete
            </p>
          </div>
        )}

        {/* Empty state */}
        {!sessionActive && !currentImage && !error && !summary && (
          <div
            className="text-center space-y-3"
            style={{ fontFamily: "'Georgia', 'Times New Roman', serif" }}
          >
            <p className="text-lg" style={{ color: 'oklch(0.6 0.03 80)' }}>
              Speak, and Dash will weave your noir story
            </p>
            <p className="text-xs" style={{ color: 'oklch(0.4 0.02 80)' }}>
              Tap the microphone to begin
            </p>
          </div>
        )}
      </div>

      {/* ── Bottom: Mic button ───────────────────────────────── */}
      <div className="pb-12 pt-6 flex flex-col items-center gap-3">
        <button
          onClick={sessionActive ? stopSession : startSession}
          className="relative flex items-center justify-center rounded-full transition-all duration-300 focus:outline-none"
          style={{
            width: 80,
            height: 80,
            backgroundColor: sessionActive ? micBg : 'oklch(0.12 0.01 60)',
            border: sessionActive ? micBorder : '2px solid oklch(0.3 0.02 60)',
            boxShadow: sessionActive ? micShadow : '0 0 20px rgba(0,0,0,0.3)',
            animation: isListening ? 'pulse-ring-green 2s ease-in-out infinite' : undefined,
            opacity: isNarrating ? 0.6 : 1,
            transition: 'all 0.4s ease',
          }}
          aria-label={sessionActive ? 'Stop session' : 'Start session'}
        >
          {/* Mic icon */}
          <svg
            width="28"
            height="28"
            viewBox="0 0 24 24"
            fill="none"
            stroke={sessionActive ? micStroke : 'oklch(0.6 0.02 80)'}
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            style={{ transition: 'stroke 0.3s ease' }}
          >
            <rect x="9" y="2" width="6" height="11" rx="3" />
            <path d="M5 10a7 7 0 0 0 14 0" />
            <line x1="12" y1="17" x2="12" y2="21" />
            <line x1="8" y1="21" x2="16" y2="21" />
            {/* Mute slash when Dash is speaking */}
            {isNarrating && (
              <line x1="2" y1="2" x2="22" y2="22" stroke="oklch(0.5 0.02 60)" strokeWidth="2.5" />
            )}
          </svg>

          {/* Pulsing ring when listening (green) */}
          {isListening && (
            <span
              className="absolute inset-0 rounded-full"
              style={{
                border: '2px solid #4ade80',
                animation: 'ping-ring-green 1.5s cubic-bezier(0, 0, 0.2, 1) infinite',
                opacity: 0.5,
              }}
            />
          )}
        </button>

        <span
          className="text-xs transition-all duration-300"
          style={{
            color: sessionActive ? micLabelColor : 'oklch(0.4 0.02 80)',
            fontFamily: "'Georgia', 'Times New Roman', serif",
            fontWeight: isListening ? 600 : 400,
          }}
        >
          {micLabel}
        </span>
      </div>

      {/* ── Keyframe animations ──────────────────────────────── */}
      <style>{`
        @keyframes irisOpen {
          0% { clip-path: circle(0% at 50% 50%); }
          100% { clip-path: circle(75% at 50% 50%); }
        }
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes fadeOut {
          from { opacity: 1; }
          to { opacity: 0; }
        }
        @keyframes pulse-dot {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.4; transform: scale(0.8); }
        }
        @keyframes pulse-dot-listening {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.6; transform: scale(1.3); }
        }
        @keyframes pulse-ring-green {
          0%, 100% { box-shadow: 0 0 0 6px rgba(74, 222, 128, 0.15), 0 0 30px rgba(74, 222, 128, 0.08); }
          50% { box-shadow: 0 0 0 10px rgba(74, 222, 128, 0.1), 0 0 50px rgba(74, 222, 128, 0.12); }
        }
        @keyframes ping-ring-green {
          0% { transform: scale(1); opacity: 0.5; }
          75%, 100% { transform: scale(1.3); opacity: 0; }
        }
        @keyframes pulse-ring {
          0%, 100% { box-shadow: 0 0 0 6px rgba(180, 140, 60, 0.15), 0 0 40px rgba(180, 140, 60, 0.1); }
          50% { box-shadow: 0 0 0 10px rgba(180, 140, 60, 0.08), 0 0 60px rgba(180, 140, 60, 0.15); }
        }
        @keyframes ping-ring {
          0% { transform: scale(1); opacity: 0.4; }
          75%, 100% { transform: scale(1.3); opacity: 0; }
        }
      `}</style>
    </div>
  );
}
