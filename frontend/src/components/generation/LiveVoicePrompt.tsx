import { useState, useRef, useCallback } from 'react';
import { Button } from '@/components/ui/button';

interface LiveVoicePromptProps {
  onUse: (text: string) => void;
  disabled?: boolean;
}

export function LiveVoicePrompt({ onUse, disabled }: LiveVoicePromptProps) {
  const [recording, setRecording] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [result, setResult] = useState<{ transcript: string; response: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const stopRecording = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
    setRecording(false);
  }, []);

  const startRecording = useCallback(async () => {
    setError(null);
    setResult(null);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
        await sendAudio(blob);
      };

      mediaRecorder.start();
      setRecording(true);

      // Auto-stop after 15 seconds
      timerRef.current = setTimeout(() => stopRecording(), 15000);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Microphone access denied');
    }
  }, [stopRecording]);

  async function sendAudio(blob: Blob) {
    setProcessing(true);
    try {
      const buffer = await blob.arrayBuffer();
      const b64 = btoa(
        new Uint8Array(buffer).reduce((data, byte) => data + String.fromCharCode(byte), ''),
      );

      const res = await fetch('/api/live-voice/prompt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ audio_base64: b64, mime_type: 'audio/webm' }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      const data = await res.json();
      setResult({ transcript: data.transcript, response: data.response });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setProcessing(false);
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Button
          variant={recording ? 'destructive' : 'outline'}
          size="sm"
          onClick={recording ? stopRecording : startRecording}
          disabled={disabled || processing}
        >
          {recording ? (
            <>
              <span className="w-2 h-2 rounded-full bg-red-400 animate-pulse mr-1.5" />
              Stop Recording
            </>
          ) : processing ? (
            'Processing...'
          ) : (
            <>
              <MicIcon className="w-3.5 h-3.5 mr-1.5" />
              Speak Your Story Idea
            </>
          )}
        </Button>
        {recording && <span className="text-xs text-[var(--muted-foreground)]">Max 15s</span>}
      </div>

      {error && <div className="text-xs text-red-400">{error}</div>}

      {result && (
        <div className="rounded-md border border-[var(--border)] bg-[var(--muted)] p-3 space-y-2">
          {result.transcript && (
            <div>
              <span className="text-xs text-[var(--muted-foreground)]">You said:</span>
              <p className="text-sm">{result.transcript}</p>
            </div>
          )}
          {result.response && (
            <div>
              <span className="text-xs text-[var(--muted-foreground)]">Dash suggests:</span>
              <p className="text-sm italic">{result.response}</p>
            </div>
          )}
          <Button
            size="sm"
            variant="secondary"
            onClick={() => onUse(result.response || result.transcript)}
          >
            Use This
          </Button>
        </div>
      )}
    </div>
  );
}

function MicIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" x2="12" y1="19" y2="22" />
    </svg>
  );
}
