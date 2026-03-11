import { useState, useRef, useCallback, useEffect } from 'react';

/* ── Status label mapping ─────────────────────────────────────── */

const STATUS_LABELS: Record<string, string> = {
  listening: 'Listening\u2026',
  narrating: 'Narrating\u2026',
  generating_image: 'Finding the right shadows\u2026',
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

/* ── LiveSession component ────────────────────────────────────── */

export function LiveSession() {
  const [sessionActive, setSessionActive] = useState(false);
  const [status, setStatus] = useState('');
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

  /* ── Audio playback ─────────────────────────────────────────── */

  const playAudioChunk = useCallback((base64Data: string) => {
    if (!playbackCtxRef.current) {
      playbackCtxRef.current = new AudioContext({ sampleRate: 24000 });
    }
    const ctx = playbackCtxRef.current;

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

  /* ── WebSocket message handler ──────────────────────────────── */

  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const msg = JSON.parse(event.data);
      switch (msg.type) {
        case 'audio':
          playAudioChunk(msg.data);
          break;
        case 'image':
          handleImageArrival(msg.data, msg.description || '');
          break;
        case 'status':
          setStatus(STATUS_LABELS[msg.content] || msg.content);
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
  }, [playAudioChunk, handleImageArrival]);

  /* ── Start session ──────────────────────────────────────────── */

  const startSession = useCallback(async () => {
    setError(null);
    setSummary(null);
    setTranscript('');
    setCurrentImage(null);
    setPrevImage(null);
    setImageTransition('idle');
    sceneCountRef.current = 0;
    nextPlayTimeRef.current = 0;

    // Request mic access
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setError('Microphone access denied. Please allow mic access and try again.');
      return;
    }
    streamRef.current = stream;

    // Connect WebSocket
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/api/live-session/ws`);
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({ type: 'start' }));
      setSessionActive(true);
      setStatus('Listening\u2026');
      setSessionStats({ scenes: 0, startTime: Date.now() });

      // Set up audio capture at 16kHz
      const audioContext = new AudioContext({ sampleRate: 16000 });
      captureCtxRef.current = audioContext;

      const source = audioContext.createMediaStreamSource(stream);
      sourceRef.current = source;

      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (e) => {
        if (ws.readyState !== WebSocket.OPEN) return;
        const float32 = e.inputBuffer.getChannelData(0);
        const int16 = float32ToInt16(float32);
        const base64 = toBase64(int16.buffer);
        ws.send(JSON.stringify({ type: 'audio', data: base64 }));
      };

      source.connect(processor);
      processor.connect(audioContext.destination);
    };

    ws.onmessage = handleMessage;

    ws.onerror = () => {
      setError('WebSocket connection error.');
    };

    ws.onclose = () => {
      cleanupCapture();
      setSessionActive(false);
      setStatus('');
      // Show summary
      if (sessionStats) {
        const elapsed = (Date.now() - sessionStats.startTime) / 60000;
        setSummary({ scenes: sceneCountRef.current, minutes: Math.round(elapsed * 10) / 10 });
      }
    };
  }, [handleMessage, sessionStats]);

  /* ── Stop session ───────────────────────────────────────────── */

  const cleanupCapture = useCallback(() => {
    processorRef.current?.disconnect();
    sourceRef.current?.disconnect();
    captureCtxRef.current?.close().catch(() => {});
    streamRef.current?.getTracks().forEach((t) => t.stop());
    processorRef.current = null;
    sourceRef.current = null;
    captureCtxRef.current = null;
    streamRef.current = null;
  }, []);

  const stopSession = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'stop' }));
      wsRef.current.close();
    }
    cleanupCapture();
    setSessionActive(false);
    setStatus('');

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

  /* ── Render ─────────────────────────────────────────────────── */

  return (
    <div
      className="fixed inset-0 z-40 flex flex-col items-center justify-between"
      style={{ backgroundColor: 'oklch(0.08 0.01 60)' }}
    >
      {/* ── Top: Status ──────────────────────────────────────── */}
      <div className="pt-8 pb-4 flex items-center gap-2 min-h-[48px]">
        {status && (
          <div
            className="flex items-center gap-2 text-sm"
            style={{
              color: 'oklch(0.65 0.03 80)',
              fontFamily: "'Georgia', 'Times New Roman', serif",
              animation: 'fadeIn 400ms ease-out',
            }}
          >
            <span
              className="inline-block w-1.5 h-1.5 rounded-full"
              style={{
                backgroundColor: 'var(--primary)',
                animation: 'pulse-dot 1.5s ease-in-out infinite',
              }}
            />
            {status}
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
            backgroundColor: sessionActive ? 'oklch(0.15 0.02 60)' : 'oklch(0.12 0.01 60)',
            border: sessionActive ? '3px solid var(--primary)' : '2px solid oklch(0.3 0.02 60)',
            boxShadow: sessionActive
              ? '0 0 0 6px rgba(180, 140, 60, 0.15), 0 0 40px rgba(180, 140, 60, 0.1)'
              : '0 0 20px rgba(0,0,0,0.3)',
            animation: sessionActive ? 'pulse-ring 2s ease-in-out infinite' : undefined,
          }}
          aria-label={sessionActive ? 'Stop session' : 'Start session'}
        >
          {/* Mic icon */}
          <svg
            width="28"
            height="28"
            viewBox="0 0 24 24"
            fill="none"
            stroke={sessionActive ? 'var(--primary)' : 'oklch(0.6 0.02 80)'}
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <rect x="9" y="2" width="6" height="11" rx="3" />
            <path d="M5 10a7 7 0 0 0 14 0" />
            <line x1="12" y1="17" x2="12" y2="21" />
            <line x1="8" y1="21" x2="16" y2="21" />
            {sessionActive && (
              <>
                {/* "Recording" stop indicator: small square in center */}
              </>
            )}
          </svg>

          {/* Pulsing ring when active */}
          {sessionActive && (
            <span
              className="absolute inset-0 rounded-full"
              style={{
                border: '2px solid var(--primary)',
                animation: 'ping-ring 1.5s cubic-bezier(0, 0, 0.2, 1) infinite',
                opacity: 0.4,
              }}
            />
          )}
        </button>

        <span
          className="text-xs transition-colors"
          style={{
            color: sessionActive ? 'var(--primary)' : 'oklch(0.4 0.02 80)',
            fontFamily: "'Georgia', 'Times New Roman', serif",
          }}
        >
          {sessionActive ? 'Recording' : 'Tap to begin'}
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
