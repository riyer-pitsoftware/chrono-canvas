import { useCallback, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { api } from "@/api/client";

type VoiceState = "idle" | "recording" | "processing";

interface VoiceInputButtonProps {
  onTranscript: (text: string) => void;
  disabled?: boolean;
  maxDuration?: number; // seconds, default 60
  className?: string;
}

export function VoiceInputButton({
  onTranscript,
  disabled = false,
  maxDuration = 60,
  className = "",
}: VoiceInputButtonProps) {
  const [state, setState] = useState<VoiceState>("idle");
  const [error, setError] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const stopRecording = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.stop();
    }
  }, []);

  const startRecording = useCallback(async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";
      const recorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = recorder;
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        if (blob.size < 100) {
          setState("idle");
          setError("Recording too short");
          return;
        }

        setState("processing");
        try {
          const formData = new FormData();
          formData.append("file", blob, "recording.webm");
          const result = await api.upload<{ transcript: string }>("/voice/transcribe", formData);
          if (result.transcript) {
            onTranscript(result.transcript);
          } else {
            setError("No speech detected");
          }
        } catch (err) {
          setError(err instanceof Error ? err.message : "Transcription failed");
        }
        setState("idle");
      };

      recorder.start(250); // collect data every 250ms
      setState("recording");

      // Auto-stop after maxDuration
      timerRef.current = setTimeout(() => {
        stopRecording();
      }, maxDuration * 1000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Mic access denied");
      setState("idle");
    }
  }, [onTranscript, maxDuration, stopRecording]);

  const handleClick = () => {
    if (state === "recording") {
      stopRecording();
    } else if (state === "idle") {
      startRecording();
    }
  };

  return (
    <div className={`inline-flex flex-col items-center gap-1 ${className}`}>
      <Button
        type="button"
        variant={state === "recording" ? "destructive" : "outline"}
        size="sm"
        onClick={handleClick}
        disabled={disabled || state === "processing"}
        title={state === "recording" ? "Stop recording" : "Start voice input"}
      >
        {state === "idle" && (
          <>
            <MicIcon className="w-4 h-4 mr-1" />
            Voice
          </>
        )}
        {state === "recording" && (
          <>
            <span className="w-2 h-2 rounded-full bg-white animate-pulse mr-1" />
            Stop
          </>
        )}
        {state === "processing" && (
          <>
            <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin mr-1" />
            ...
          </>
        )}
      </Button>
      {error && <span className="text-xs text-[var(--destructive)]">{error}</span>}
    </div>
  );
}

function MicIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" x2="12" y1="19" y2="22" />
    </svg>
  );
}
