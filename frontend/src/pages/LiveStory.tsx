import { useState, useRef, useEffect } from "react";

type StoryPart =
  | { type: "text"; content: string }
  | { type: "image"; content: string; mime_type: string };

type DoneEvent = {
  type: "done";
  model?: string;
  elapsed_s?: number;
  text_parts?: number;
  image_parts?: number;
};

const SUGGESTED_PROMPTS = [
  "A jazz singer discovers a coded message hidden in a vinyl record, 1940s Harlem",
  "Hatshepsut's tomb guard witnesses something impossible at midnight",
  "A private eye in rain-soaked Tokyo, 1952, follows a woman who shouldn't exist",
  "Two astronomers in 1920s Berlin decode a signal that changes everything",
];

export function LiveStory() {
  const [prompt, setPrompt] = useState("");
  const [numScenes, setNumScenes] = useState(4);
  const [parts, setParts] = useState<StoryPart[]>([]);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<DoneEvent | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [parts]);

  async function generate() {
    if (!prompt.trim()) return;
    setParts([]);
    setError(null);
    setStats(null);
    setStatus(null);
    setLoading(true);

    try {
      const res = await fetch("/api/live-story", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, num_scenes: numScenes }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const data = JSON.parse(line.slice(6));
          if (data.type === "done") {
            setStats(data);
            setStatus(null);
          } else if (data.type === "error") {
            setError(data.content);
          } else if (data.type === "status") {
            setStatus(data.content);
          } else {
            setParts((prev) => [...prev, data as StoryPart]);
          }
        }
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold mb-1 tracking-tight">Live Story</h1>
        <p className="text-sm text-[var(--muted-foreground)]">
          Gemini generates interleaved text and images — the story and its visuals arrive together.
        </p>
      </div>

      {/* Prompt input */}
      <div className="space-y-3">
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) generate();
          }}
          placeholder="A noir detective story set in ancient Egypt with Hatshepsut..."
          className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] p-3 text-sm min-h-[80px] resize-y focus:ring-1 focus:ring-[var(--primary)] focus:border-[var(--primary)] transition-colors"
          disabled={loading}
        />

        {/* Scene count + generate */}
        <div className="flex items-center gap-3">
          <label className="text-sm text-[var(--muted-foreground)] shrink-0">
            Scenes:
          </label>
          <select
            value={numScenes}
            onChange={(e) => setNumScenes(Number(e.target.value))}
            disabled={loading}
            className="rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm"
          >
            {[2, 3, 4, 5, 6].map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
          <div className="flex-1" />
          <button
            onClick={generate}
            disabled={loading || !prompt.trim()}
            className="px-5 py-2 rounded-md bg-[var(--primary)] text-[var(--primary-foreground)] text-sm font-medium disabled:opacity-50 transition-opacity"
          >
            {loading ? "Generating..." : "Generate"}
          </button>
        </div>
      </div>

      {/* Suggested prompts */}
      {parts.length === 0 && !loading && (
        <div className="space-y-2">
          <p className="text-xs text-[var(--muted-foreground)] uppercase tracking-wider">Try a prompt</p>
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

      {/* Story output */}
      {parts.length > 0 && (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] overflow-hidden">
          <div className="p-6 space-y-5">
            {parts.map((part, i) =>
              part.type === "text" ? (
                <p
                  key={i}
                  className="text-sm leading-relaxed whitespace-pre-wrap animate-in fade-in duration-500"
                  style={{ fontFamily: "'Georgia', 'Times New Roman', serif" }}
                >
                  {part.content}
                </p>
              ) : (
                <img
                  key={i}
                  src={`data:${part.mime_type};base64,${part.content}`}
                  alt={`Scene ${Math.ceil((i + 1) / 2)}`}
                  className="rounded-lg max-w-full shadow-lg animate-in fade-in slide-in-from-bottom-2 duration-700"
                />
              ),
            )}
            <div ref={scrollRef} />
          </div>

          {/* Completion stats */}
          {stats && (
            <div className="border-t border-[var(--border)] px-6 py-3 flex items-center gap-4 text-xs text-[var(--muted-foreground)]">
              <span>{stats.text_parts} text + {stats.image_parts} images</span>
              <span>{stats.elapsed_s}s</span>
              {stats.model && <span className="opacity-60">{stats.model}</span>}
            </div>
          )}
        </div>
      )}

      {/* AI disclaimer */}
      {parts.length > 0 && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-md bg-amber-950/30 border border-amber-900/40 text-amber-200/80 text-xs">
          <span>AI-generated content — for creative entertainment only.</span>
          <span className="ml-auto opacity-60">Powered by Gemini</span>
        </div>
      )}
    </div>
  );
}
