import { useEffect, useRef } from 'react';

interface StreamingTextProps {
  agent: string;
  text: string;
  isStreaming: boolean;
}

const AGENT_LABELS: Record<string, string> = {
  research: 'Research Agent',
  prompt_generation: 'Prompt Generation Agent',
  extraction: 'Extraction Agent',
  validation: 'Validation Agent',
  orchestrator: 'Orchestrator',
};

export function StreamingText({ agent, text, isStreaming }: StreamingTextProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [text]);

  if (!text) return null;

  const label = AGENT_LABELS[agent] ?? agent;

  return (
    <div className="rounded-md border border-[var(--border)] bg-[var(--muted)] p-3 space-y-1">
      <p className="text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
        {label} — live output
      </p>
      <p className="text-sm font-mono whitespace-pre-wrap break-words leading-relaxed">
        {text}
        {isStreaming && (
          <span className="inline-block w-[2px] h-[1em] ml-[1px] bg-current align-middle animate-[blink_1s_step-end_infinite]" />
        )}
      </p>
      <div ref={bottomRef} />
    </div>
  );
}
