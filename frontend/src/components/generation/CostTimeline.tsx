import { useState } from "react";
import type { LLMCallDetail } from "@/api/types";

// ── Color palette — one per agent ────────────────────────────────────────────

const AGENT_COLORS: Record<string, string> = {
  orchestrator:     "#6366f1", // indigo
  extraction:       "#0ea5e9", // sky
  research:         "#10b981", // emerald
  face_search:      "#84cc16", // lime
  prompt_generation:"#f59e0b", // amber
  image_generation: "#f97316", // orange
  validation:       "#ef4444", // red
  face_swap:        "#ec4899", // pink
  export:           "#8b5cf6", // violet
};

const DEFAULT_COLOR = "#94a3b8";

function agentColor(agent: string) {
  return AGENT_COLORS[agent] ?? DEFAULT_COLOR;
}

function fmtDuration(ms: number) {
  return ms < 1000 ? `${Math.round(ms)}ms` : `${(ms / 1000).toFixed(2)}s`;
}

function fmtCost(cost: number) {
  if (cost === 0) return "$0";
  if (cost < 0.000001) return `$${(cost * 1e9).toFixed(1)}n`;
  if (cost < 0.001)    return `$${(cost * 1e6).toFixed(2)}μ`;
  if (cost < 1)        return `$${cost.toFixed(6)}`;
  return `$${cost.toFixed(4)}`;
}

// ── Aggregate llm_calls by agent ─────────────────────────────────────────────

interface AgentMetrics {
  agent: string;
  duration_ms: number;
  cost: number;
  calls: number;
}

function aggregate(calls: LLMCallDetail[]): AgentMetrics[] {
  const map = new Map<string, AgentMetrics>();
  for (const c of calls) {
    const existing = map.get(c.agent);
    if (existing) {
      existing.duration_ms += c.duration_ms;
      existing.cost += c.cost;
      existing.calls += 1;
    } else {
      map.set(c.agent, { agent: c.agent, duration_ms: c.duration_ms, cost: c.cost, calls: 1 });
    }
  }
  // Return in pipeline order
  const ORDER = ["orchestrator","extraction","research","face_search","prompt_generation","image_generation","validation","face_swap","export"];
  return [...map.values()].sort((a, b) => {
    const ai = ORDER.indexOf(a.agent);
    const bi = ORDER.indexOf(b.agent);
    return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
  });
}

// ── Stacked bar ───────────────────────────────────────────────────────────────

function StackedBar({ metrics, totalMs, activeAgent, onHover }: {
  metrics: AgentMetrics[];
  totalMs: number;
  activeAgent: string | null;
  onHover: (agent: string | null) => void;
}) {
  return (
    <div className="relative">
      <div className="flex h-10 rounded-md overflow-hidden border border-[var(--border)]">
        {metrics.map((m) => {
          const pct = totalMs > 0 ? (m.duration_ms / totalMs) * 100 : 0;
          const isActive = activeAgent === m.agent;
          return (
            <div
              key={m.agent}
              style={{
                width: `${pct}%`,
                backgroundColor: agentColor(m.agent),
                opacity: activeAgent && !isActive ? 0.4 : 1,
                minWidth: pct > 0 ? "2px" : 0,
                transition: "opacity 150ms",
              }}
              onMouseEnter={() => onHover(m.agent)}
              onMouseLeave={() => onHover(null)}
              className="cursor-default"
              title={`${m.agent}: ${fmtDuration(m.duration_ms)} (${pct.toFixed(1)}%)`}
            />
          );
        })}
      </div>

      {/* Percentage labels below segments for wide-enough ones */}
      <div className="flex h-5 mt-0.5">
        {metrics.map((m) => {
          const pct = totalMs > 0 ? (m.duration_ms / totalMs) * 100 : 0;
          return (
            <div
              key={m.agent}
              style={{ width: `${pct}%`, minWidth: pct > 0 ? "2px" : 0 }}
              className="overflow-hidden"
            >
              {pct >= 8 && (
                <span className="text-[10px] text-[var(--muted-foreground)] pl-1 whitespace-nowrap">
                  {pct.toFixed(0)}%
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Breakdown table ───────────────────────────────────────────────────────────

const AGENT_LABELS: Record<string, string> = {
  orchestrator: "Orchestrator",
  extraction: "Extraction",
  research: "Research",
  face_search: "Face Search",
  prompt_generation: "Prompt Generation",
  image_generation: "Image Generation",
  validation: "Validation",
  face_swap: "Face Swap",
  export: "Export",
};

function MiniBar({ pct, color }: { pct: number; color: string }) {
  return (
    <div className="flex-1 h-2 bg-[var(--muted)] rounded-full overflow-hidden">
      <div
        style={{ width: `${pct}%`, backgroundColor: color }}
        className="h-full rounded-full transition-all"
      />
    </div>
  );
}

function BreakdownTable({ metrics, totalMs, totalCost, activeAgent, onHover }: {
  metrics: AgentMetrics[];
  totalMs: number;
  totalCost: number;
  activeAgent: string | null;
  onHover: (agent: string | null) => void;
}) {
  return (
    <table className="w-full text-sm border-separate border-spacing-0">
      <thead>
        <tr className="text-xs text-[var(--muted-foreground)] uppercase tracking-wide">
          <th className="text-left pb-2 font-medium w-36">Agent</th>
          <th className="text-right pb-2 font-medium">Duration</th>
          <th className="pb-2 w-28 px-3"></th>
          <th className="text-right pb-2 font-medium">Cost</th>
          <th className="pb-2 w-28 px-3"></th>
          <th className="text-right pb-2 font-medium">Calls</th>
        </tr>
      </thead>
      <tbody>
        {metrics.map((m) => {
          const durPct  = totalMs   > 0 ? (m.duration_ms / totalMs)   * 100 : 0;
          const costPct = totalCost > 0 ? (m.cost        / totalCost) * 100 : 0;
          const color   = agentColor(m.agent);
          const isActive = activeAgent === m.agent;

          return (
            <tr
              key={m.agent}
              onMouseEnter={() => onHover(m.agent)}
              onMouseLeave={() => onHover(null)}
              className={`transition-colors rounded-md ${isActive ? "bg-[var(--accent)]" : "hover:bg-[var(--accent)/50]"}`}
            >
              <td className="py-1.5 pr-3">
                <div className="flex items-center gap-2">
                  <span
                    className="inline-block w-2.5 h-2.5 rounded-sm shrink-0"
                    style={{ backgroundColor: color }}
                  />
                  <span className="font-medium truncate">
                    {AGENT_LABELS[m.agent] ?? m.agent}
                  </span>
                </div>
              </td>
              <td className="text-right py-1.5 tabular-nums text-xs text-[var(--muted-foreground)]">
                {fmtDuration(m.duration_ms)}
              </td>
              <td className="px-3 py-1.5">
                <div className="flex items-center gap-1.5">
                  <MiniBar pct={durPct} color={color} />
                  <span className="text-[10px] text-[var(--muted-foreground)] w-8 text-right tabular-nums">
                    {durPct.toFixed(0)}%
                  </span>
                </div>
              </td>
              <td className="text-right py-1.5 tabular-nums text-xs text-[var(--muted-foreground)]">
                {fmtCost(m.cost)}
              </td>
              <td className="px-3 py-1.5">
                <div className="flex items-center gap-1.5">
                  <MiniBar pct={costPct} color={color} />
                  <span className="text-[10px] text-[var(--muted-foreground)] w-8 text-right tabular-nums">
                    {costPct.toFixed(0)}%
                  </span>
                </div>
              </td>
              <td className="text-right py-1.5 text-xs text-[var(--muted-foreground)] tabular-nums">
                {m.calls}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

// ── Summary stats ─────────────────────────────────────────────────────────────

function StatPill({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="flex-1 min-w-32 rounded-md border border-[var(--border)] bg-[var(--muted)] px-3 py-2">
      <p className="text-[10px] uppercase tracking-wide text-[var(--muted-foreground)] font-medium">{label}</p>
      <p className="text-sm font-bold mt-0.5">{value}</p>
      {sub && <p className="text-[10px] text-[var(--muted-foreground)] mt-0.5">{sub}</p>}
    </div>
  );
}

// ── Public component ──────────────────────────────────────────────────────────

export function CostTimeline({ llmCalls }: { llmCalls: LLMCallDetail[] }) {
  const [activeAgent, setActiveAgent] = useState<string | null>(null);

  if (!llmCalls || llmCalls.length === 0) {
    return (
      <p className="text-sm text-[var(--muted-foreground)]">No LLM call data available.</p>
    );
  }

  const metrics  = aggregate(llmCalls);
  const totalMs  = metrics.reduce((s, m) => s + m.duration_ms, 0);
  const totalCost = metrics.reduce((s, m) => s + m.cost, 0);

  const slowest    = [...metrics].sort((a, b) => b.duration_ms - a.duration_ms)[0];
  const costliest  = [...metrics].sort((a, b) => b.cost - a.cost)[0];

  return (
    <div className="space-y-5">
      {/* Summary pills */}
      <div className="flex flex-wrap gap-2">
        <StatPill
          label="Total Time (LLM)"
          value={fmtDuration(totalMs)}
          sub={`${metrics.length} agent${metrics.length !== 1 ? "s" : ""}`}
        />
        <StatPill
          label="Total Cost"
          value={fmtCost(totalCost)}
          sub={`${llmCalls.length} call${llmCalls.length !== 1 ? "s" : ""}`}
        />
        <StatPill
          label="Slowest Step"
          value={AGENT_LABELS[slowest.agent] ?? slowest.agent}
          sub={fmtDuration(slowest.duration_ms)}
        />
        <StatPill
          label="Most Expensive"
          value={totalCost > 0 ? (AGENT_LABELS[costliest.agent] ?? costliest.agent) : "—"}
          sub={totalCost > 0 ? fmtCost(costliest.cost) : "all free"}
        />
      </div>

      {/* Stacked bar */}
      <StackedBar
        metrics={metrics}
        totalMs={totalMs}
        activeAgent={activeAgent}
        onHover={setActiveAgent}
      />

      {/* Breakdown table */}
      <BreakdownTable
        metrics={metrics}
        totalMs={totalMs}
        totalCost={totalCost}
        activeAgent={activeAgent}
        onHover={setActiveAgent}
      />
    </div>
  );
}
