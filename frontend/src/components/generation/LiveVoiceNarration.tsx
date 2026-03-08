import { useState, useRef } from "react";
import { Button } from "@/components/ui/button";

interface LiveVoiceNarrationProps {
  text: string;
  disabled?: boolean;
}

export function LiveVoiceNarration({ text, disabled }: LiveVoiceNarrationProps) {
  const [loading, setLoading] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  async function handleNarrate() {
    if (loading || playing) {
      // Stop playback
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
      setPlaying(false);
      return;
    }

    setError(null);
    setLoading(true);

    try {
      const res = await fetch("/api/live-voice/narrate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioRef.current = audio;

      audio.onended = () => {
        setPlaying(false);
        URL.revokeObjectURL(url);
        audioRef.current = null;
      };

      audio.onerror = () => {
        setPlaying(false);
        setError("Audio playback failed");
        URL.revokeObjectURL(url);
        audioRef.current = null;
      };

      await audio.play();
      setPlaying(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="inline-flex items-center gap-1">
      <Button
        variant="ghost"
        size="sm"
        className="h-6 px-2 text-xs"
        onClick={handleNarrate}
        disabled={disabled || !text}
        title={playing ? "Stop narration" : "Narrate with Live API"}
      >
        {loading ? (
          <span className="animate-pulse">...</span>
        ) : playing ? (
          <StopIcon className="w-3 h-3" />
        ) : (
          <SpeakerIcon className="w-3 h-3" />
        )}
      </Button>
      {error && <span className="text-xs text-red-400">{error}</span>}
    </div>
  );
}

function SpeakerIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
      <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
      <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
    </svg>
  );
}

function StopIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <rect x="6" y="6" width="12" height="12" rx="1" />
    </svg>
  );
}
