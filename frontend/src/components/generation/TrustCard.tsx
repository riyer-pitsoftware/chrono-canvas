import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { LLMCallDetail } from "@/api/types";
import {
  CheckCircle,
  XCircle,
  MinusCircle,
  ChevronDown,
  ChevronRight,
  Shield,
  Clock,
  DollarSign,
  Cpu,
  Eye,
} from "lucide-react";

// ── Pipeline step definitions ─────────────────────────────────────────────────

const PORTRAIT_STEPS = [
  { key: "extraction", label: "Extraction", description: "Parse figure name, era, and context from input" },
  { key: "research", label: "Research", description: "Gather historical context via grounded search" },
  { key: "face_search", label: "Face Search", description: "Find reference face image online" },
  { key: "prompt_generation", label: "Prompt Generation", description: "Craft image generation prompt from research" },
  { key: "image_generation", label: "Image Generation", description: "Generate portrait via Imagen" },
  { key: "validation", label: "Validation", description: "AI quality assessment of output" },
  { key: "facial_compositing", label: "Facial Compositing", description: "Composite reference face onto portrait" },
  { key: "export", label: "Export", description: "Save final output artifacts" },
] as const;

const STORY_STEPS = [
  { key: "story_orchestrator", label: "Orchestrator", description: "Plan the storyboard structure" },
  { key: "image_to_story", label: "Image to Story", description: "Extract narrative from uploaded image" },
  { key: "reference_image_analysis", label: "Ref Image Analysis", description: "Analyze reference images for style cues" },
  { key: "character_extraction", label: "Character Extraction", description: "Identify characters and traits from input" },
  { key: "scene_decomposition", label: "Scene Decomposition", description: "Break narrative into visual scenes" },
  { key: "scene_prompt_generation", label: "Prompt Generation", description: "Generate image prompts per scene" },
  { key: "scene_image_generation", label: "Image Generation", description: "Generate scene images via Imagen" },
  { key: "storyboard_coherence", label: "Coherence Check", description: "Multimodal consistency review across panels" },
  { key: "narration_script", label: "Narration Script", description: "Write voice-over narration text" },
  { key: "narration_audio", label: "Narration Audio", description: "Synthesize narration via TTS" },
  { key: "video_assembly", label: "Video Assembly", description: "Combine panels + audio into video" },
  { key: "storyboard_export", label: "Export", description: "Save storyboard artifacts" },
] as const;

// ── Provider badge colors ─────────────────────────────────────────────────────

const PROVIDER_STYLES: Record<string, string> = {
  gemini: "bg-blue-900/40 text-blue-300 border-blue-700/50",
  imagen: "bg-purple-900/40 text-purple-300 border-purple-700/50",
  "google-tts": "bg-teal-900/40 text-teal-300 border-teal-700/50",
  openai: "bg-green-900/40 text-green-300 border-green-700/50",
  mock: "bg-gray-700/40 text-gray-300 border-gray-600/50",
};

function providerBadgeClass(provider: string | null): string {
  if (!provider) return "bg-gray-700/40 text-gray-300 border-gray-600/50";
  const key = provider.toLowerCase();
  for (const [k, v] of Object.entries(PROVIDER_STYLES)) {
    if (key.includes(k)) return v;
  }
  return "bg-gray-700/40 text-gray-300 border-gray-600/50";
}

// ── Formatting helpers ────────────────────────────────────────────────────────

function fmtDuration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
}

function fmtCost(cost: number): string {
  if (cost === 0) return "$0.00";
  if (cost < 0.01) return `$${cost.toFixed(4)}`;
  return `$${cost.toFixed(2)}`;
}

// ── Step status derivation ────────────────────────────────────────────────────

type StepStatus = "completed" | "failed" | "skipped" | "pending";

interface StepData {
  status: StepStatus;
  provider: string | null;
  model: string | null;
  duration_ms: number;
  cost: number;
  callCount: number;
  inputTokens: number;
  outputTokens: number;
  calls: LLMCallDetail[];
  cacheHit: boolean;
}

function deriveStepData(
  stepKey: string,
  agentTrace: Array<Record<string, unknown>>,
  llmCalls: LLMCallDetail[],
): StepData {
  const traceEntry = agentTrace.find((t) => t.agent === stepKey);
  const calls = llmCalls.filter((c) => c.agent === stepKey);

  // Determine status
  let status: StepStatus = "pending";
  if (traceEntry) {
    if (traceEntry.skipped) {
      status = "skipped";
    } else if (traceEntry.error) {
      status = "failed";
    } else {
      status = "completed";
    }
  } else if (calls.length > 0) {
    status = "completed";
  }

  // Aggregate metrics from LLM calls
  const duration_ms = calls.reduce((s, c) => s + c.duration_ms, 0);
  const cost = calls.reduce((s, c) => s + c.cost, 0);
  const inputTokens = calls.reduce((s, c) => s + c.input_tokens, 0);
  const outputTokens = calls.reduce((s, c) => s + c.output_tokens, 0);

  // Provider: use the first call's provider, or infer from step key
  let provider = calls[0]?.provider ?? null;
  let model = calls[0]?.model ?? null;
  if (!provider && status === "completed") {
    if (stepKey.includes("image_generation")) {
      provider = "imagen";
      model = "imagen-4.0-fast";
    } else if (stepKey === "narration_audio") {
      provider = "google-tts";
    } else if (stepKey === "video_assembly") {
      provider = "ffmpeg";
    } else if (stepKey === "facial_compositing") {
      provider = "facefusion";
    } else if (stepKey === "face_search") {
      provider = "google-search";
    }
  }

  const cacheHit = stepKey === "research" && traceEntry?.cache_hit === true;

  return { status, provider, model, duration_ms, cost, callCount: calls.length, inputTokens, outputTokens, calls, cacheHit };
}

// ── Step row component ────────────────────────────────────────────────────────

function StatusIcon({ status }: { status: StepStatus }) {
  switch (status) {
    case "completed":
      return <CheckCircle className="w-4 h-4 text-green-400" />;
    case "failed":
      return <XCircle className="w-4 h-4 text-red-400" />;
    case "skipped":
      return <MinusCircle className="w-4 h-4 text-gray-500" />;
    default:
      return <div className="w-4 h-4 rounded-full border-2 border-gray-600" />;
  }
}

function StepRow({
  label,
  description,
  data,
  isExpanded,
  onToggle,
}: {
  label: string;
  description: string;
  data: StepData;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const hasDetail = data.calls.length > 0 || data.status === "completed";

  return (
    <div className="border-b border-gray-800/60 last:border-b-0">
      <button
        onClick={hasDetail ? onToggle : undefined}
        className={`w-full flex items-center gap-3 px-4 py-3 text-left transition-colors ${
          hasDetail ? "hover:bg-white/[0.03] cursor-pointer" : "cursor-default opacity-60"
        }`}
      >
        {/* Expand chevron */}
        <div className="w-4 flex-shrink-0">
          {hasDetail && (
            isExpanded
              ? <ChevronDown className="w-4 h-4 text-gray-400" />
              : <ChevronRight className="w-4 h-4 text-gray-400" />
          )}
        </div>

        {/* Status icon */}
        <StatusIcon status={data.status} />

        {/* Label */}
        <div className="flex-1 min-w-0">
          <span className="text-sm font-medium text-gray-200">{label}</span>
          {data.cacheHit && (
            <Badge className="ml-2 text-[10px] bg-amber-900/40 text-amber-300 border-amber-700/50">
              cached
            </Badge>
          )}
        </div>

        {/* Provider pill */}
        {data.provider && data.status !== "skipped" && (
          <Badge className={`text-[10px] border ${providerBadgeClass(data.provider)}`}>
            {data.provider}
            {data.model ? ` / ${data.model.replace(/^.*\//, "").slice(0, 20)}` : ""}
          </Badge>
        )}

        {/* Duration */}
        {data.duration_ms > 0 && (
          <span className="text-xs text-gray-400 tabular-nums w-14 text-right flex-shrink-0">
            {fmtDuration(data.duration_ms)}
          </span>
        )}

        {/* Cost */}
        {data.cost > 0 && (
          <span className="text-xs text-gray-400 tabular-nums w-16 text-right flex-shrink-0">
            {fmtCost(data.cost)}
          </span>
        )}
      </button>

      {/* Expanded detail */}
      {isExpanded && data.calls.length > 0 && (
        <div className="px-4 pb-3 ml-11 space-y-2">
          <p className="text-xs text-gray-500">{description}</p>
          {data.calls.map((call, i) => (
            <div
              key={i}
              className="rounded-md bg-gray-900/50 border border-gray-800/60 px-3 py-2 text-xs space-y-1"
            >
              <div className="flex items-center justify-between">
                <span className="text-gray-300 font-medium">
                  Call {data.calls.length > 1 ? `${i + 1}/${data.calls.length}` : ""}
                </span>
                <div className="flex items-center gap-3 text-gray-500 tabular-nums">
                  <span>{call.input_tokens + call.output_tokens} tokens</span>
                  <span>{fmtDuration(call.duration_ms)}</span>
                  {call.cost > 0 && <span>{fmtCost(call.cost)}</span>}
                </div>
              </div>
              {call.user_prompt && (
                <div>
                  <p className="text-gray-500 mb-0.5">Prompt (truncated)</p>
                  <p className="text-gray-400 line-clamp-2">{call.user_prompt}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Expanded detail for non-LLM completed steps */}
      {isExpanded && data.calls.length === 0 && data.status === "completed" && (
        <div className="px-4 pb-3 ml-11">
          <p className="text-xs text-gray-500">{description}</p>
          {data.provider && (
            <p className="text-xs text-gray-500 mt-1">
              Provider: <span className="text-gray-400">{data.provider}</span>
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Public TrustCard component ────────────────────────────────────────────────

interface TrustCardProps {
  agentTrace: Array<Record<string, unknown>>;
  llmCalls: LLMCallDetail[];
  runType?: string;
  status?: string;
  totalCost?: number;
  totalDurationMs?: number;
  className?: string;
  /** Start collapsed — useful when embedded inline */
  defaultCollapsed?: boolean;
}

export function TrustCard({
  agentTrace,
  llmCalls,
  runType,
  status,
  totalCost,
  totalDurationMs,
  className = "",
  defaultCollapsed = false,
}: TrustCardProps) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);
  const [expandedSteps, setExpandedSteps] = useState<Set<string>>(new Set());

  const steps = runType === "creative_story" ? STORY_STEPS : PORTRAIT_STEPS;

  // Build step data for each pipeline stage
  const stepDataMap = new Map<string, StepData>();
  for (const step of steps) {
    stepDataMap.set(step.key, deriveStepData(step.key, agentTrace, llmCalls));
  }

  // Aggregate totals
  const completedCount = [...stepDataMap.values()].filter((d) => d.status === "completed").length;
  const skippedCount = [...stepDataMap.values()].filter((d) => d.status === "skipped").length;
  const failedCount = [...stepDataMap.values()].filter((d) => d.status === "failed").length;
  const totalLLMCalls = llmCalls.length;
  const aggregateCost = totalCost ?? llmCalls.reduce((s, c) => s + c.cost, 0);
  const aggregateDuration = totalDurationMs ?? llmCalls.reduce((s, c) => s + c.duration_ms, 0);
  const totalTokens = llmCalls.reduce((s, c) => s + c.input_tokens + c.output_tokens, 0);

  // Unique providers used
  const providers = new Set<string>();
  for (const call of llmCalls) {
    if (call.provider) providers.add(call.provider);
  }
  // Add non-LLM providers from step data
  for (const d of stepDataMap.values()) {
    if (d.provider && d.status === "completed") providers.add(d.provider);
  }

  const toggleStep = (key: string) => {
    setExpandedSteps((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  return (
    <Card
      className={`bg-gray-950 border-gray-800 text-gray-100 overflow-hidden ${className}`}
    >
      {/* Header */}
      <CardHeader className="pb-3">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center gap-3 w-full text-left"
        >
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-emerald-900/40 border border-emerald-700/30">
            <Eye className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="flex-1">
            <CardTitle className="text-base text-gray-100 flex items-center gap-2">
              Pipeline Transparency
              <Badge className="text-[10px] bg-emerald-900/30 text-emerald-400 border-emerald-700/40 border">
                TrustCard
              </Badge>
            </CardTitle>
            <p className="text-xs text-gray-500 mt-0.5">
              Full audit trail -- what AI did at every step
            </p>
          </div>
          {collapsed ? (
            <ChevronRight className="w-5 h-5 text-gray-500" />
          ) : (
            <ChevronDown className="w-5 h-5 text-gray-500" />
          )}
        </button>
      </CardHeader>

      {!collapsed && (
        <CardContent className="pt-0 space-y-4">
          {/* Summary stats row */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <StatBox
              icon={<Shield className="w-3.5 h-3.5 text-emerald-400" />}
              label="Steps"
              value={`${completedCount} done`}
              sub={
                [
                  skippedCount > 0 ? `${skippedCount} skipped` : "",
                  failedCount > 0 ? `${failedCount} failed` : "",
                ]
                  .filter(Boolean)
                  .join(", ") || "none skipped"
              }
            />
            <StatBox
              icon={<Cpu className="w-3.5 h-3.5 text-blue-400" />}
              label="AI Calls"
              value={String(totalLLMCalls)}
              sub={`${totalTokens.toLocaleString()} tokens`}
            />
            <StatBox
              icon={<Clock className="w-3.5 h-3.5 text-amber-400" />}
              label="Duration"
              value={fmtDuration(aggregateDuration)}
              sub="AI processing"
            />
            <StatBox
              icon={<DollarSign className="w-3.5 h-3.5 text-green-400" />}
              label="Cost"
              value={fmtCost(aggregateCost)}
              sub={[...providers].join(", ") || "n/a"}
            />
          </div>

          {/* Provider badges */}
          {providers.size > 0 && (
            <div className="flex flex-wrap gap-1.5">
              <span className="text-[10px] text-gray-500 uppercase tracking-wider mr-1 self-center">
                Providers:
              </span>
              {[...providers].map((p) => (
                <Badge
                  key={p}
                  className={`text-[10px] border ${providerBadgeClass(p)}`}
                >
                  {p}
                </Badge>
              ))}
            </div>
          )}

          {/* Pipeline steps list */}
          <div className="rounded-lg border border-gray-800/80 overflow-hidden bg-gray-950/50">
            {steps.map((step) => {
              const data = stepDataMap.get(step.key)!;
              // Skip steps that are pending and were never reached
              if (data.status === "pending" && status === "completed") return null;
              return (
                <StepRow
                  key={step.key}
                  label={step.label}
                  description={step.description}
                  data={data}
                  isExpanded={expandedSteps.has(step.key)}
                  onToggle={() => toggleStep(step.key)}
                />
              );
            })}
          </div>

          {/* Transparency footer */}
          <p className="text-[10px] text-gray-600 text-center">
            No black boxes -- every AI decision is logged and auditable
          </p>
        </CardContent>
      )}
    </Card>
  );
}

// ── StatBox ───────────────────────────────────────────────────────────────────

function StatBox({
  icon,
  label,
  value,
  sub,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub: string;
}) {
  return (
    <div className="rounded-lg border border-gray-800/60 bg-gray-900/40 px-3 py-2">
      <div className="flex items-center gap-1.5 mb-1">
        {icon}
        <span className="text-[10px] text-gray-500 uppercase tracking-wider">{label}</span>
      </div>
      <p className="text-sm font-semibold text-gray-200">{value}</p>
      <p className="text-[10px] text-gray-500 truncate">{sub}</p>
    </div>
  );
}
