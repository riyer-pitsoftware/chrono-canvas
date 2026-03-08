import { useState, useRef } from "react";

type StoryPart =
  | { type: "text"; content: string }
  | { type: "image"; content: string; mime_type: string };

export function LiveStory() {
  const [prompt, setPrompt] = useState("");
  const [style, setStyle] = useState("");
  const [era, setEra] = useState("");
  const [parts, setParts] = useState<StoryPart[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  async function generate() {
    if (!prompt.trim()) return;
    setParts([]);
    setError(null);
    setLoading(true);

    try {
      const res = await fetch("/api/live-story", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt,
          style: style || undefined,
          era: era || undefined,
        }),
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
          if (data.type === "done") break;
          if (data.type === "error") {
            setError(data.content);
            break;
          }
          setParts((prev) => [...prev, data as StoryPart]);
          scrollRef.current?.scrollIntoView({ behavior: "smooth" });
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
      <div>
        <h1 className="text-2xl font-bold mb-1">Live Story</h1>
        <p className="text-sm text-[var(--muted-foreground)]">
          Gemini 2.0 Flash generates interleaved text and images in one shot.
        </p>
      </div>

      <div className="space-y-3">
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="A noir detective story set in ancient Egypt with Hatshepsut..."
          className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] p-3 text-sm min-h-[80px] resize-y"
          disabled={loading}
        />
        <div className="flex gap-3">
          <input
            value={style}
            onChange={(e) => setStyle(e.target.value)}
            placeholder="Style (optional)"
            className="flex-1 rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm"
            disabled={loading}
          />
          <input
            value={era}
            onChange={(e) => setEra(e.target.value)}
            placeholder="Era (optional)"
            className="flex-1 rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm"
            disabled={loading}
          />
        </div>
        <button
          onClick={generate}
          disabled={loading || !prompt.trim()}
          className="px-4 py-2 rounded-md bg-[var(--primary)] text-[var(--primary-foreground)] text-sm font-medium disabled:opacity-50"
        >
          {loading ? "Generating..." : "Generate Live Story"}
        </button>
      </div>

      {error && (
        <div className="rounded-md border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {parts.length > 0 && (
        <div className="space-y-4 rounded-lg border border-[var(--border)] p-6 bg-[var(--card)]">
          {parts.map((part, i) =>
            part.type === "text" ? (
              <p key={i} className="text-sm leading-relaxed whitespace-pre-wrap">
                {part.content}
              </p>
            ) : (
              <img
                key={i}
                src={`data:${part.mime_type};base64,${part.content}`}
                alt={`Story illustration ${i}`}
                className="rounded-lg max-w-full shadow-lg"
              />
            ),
          )}
          <div ref={scrollRef} />
        </div>
      )}
    </div>
  );
}
