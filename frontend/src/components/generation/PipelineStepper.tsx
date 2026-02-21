import { Badge } from "@/components/ui/badge";
import { CheckCircle, Circle, Loader, XCircle } from "lucide-react";
import type { LLMCallDetail } from "@/api/types";
import type { ImageProgress } from "@/api/hooks/useGenerationWS";

const PIPELINE_STAGES = [
  { key: "extraction", label: "Extraction" },
  { key: "research", label: "Research" },
  { key: "face_search", label: "Face Search" },
  { key: "prompt_generation", label: "Prompt Generation" },
  { key: "image_generation", label: "Image Generation" },
  { key: "validation", label: "Validation" },
  { key: "facial_compositing", label: "Facial Compositing" },
  { key: "export", label: "Export" },
] as const;

interface PipelineStepperProps {
  currentAgent: string | null;
  status: string;
  agentTrace: Array<Record<string, unknown>>;
  llmCalls?: LLMCallDetail[];
  imageProgress?: ImageProgress | null;
}

function getStageStatus(
  stageKey: string,
  currentAgent: string | null,
  status: string,
  completedAgents: Set<string>,
) {
  if (status === "failed" && currentAgent === stageKey) return "error";
  if (completedAgents.has(stageKey)) return "completed";
  if (currentAgent === stageKey && status !== "completed" && status !== "failed") return "running";
  return "pending";
}

export function PipelineStepper({ currentAgent, status, agentTrace, llmCalls = [], imageProgress }: PipelineStepperProps) {
  const completedAgents = new Set(agentTrace.map((t) => String(t.agent)));

  const callsByAgent = new Map<string, LLMCallDetail[]>();
  for (const call of llmCalls) {
    const existing = callsByAgent.get(call.agent) || [];
    existing.push(call);
    callsByAgent.set(call.agent, existing);
  }

  return (
    <div className="space-y-1">
      {PIPELINE_STAGES.map((stage) => {
        const stageStatus = getStageStatus(stage.key, currentAgent, status, completedAgents);
        const calls = callsByAgent.get(stage.key) || [];
        const totalCost = calls.reduce((sum, c) => sum + c.cost, 0);
        const totalDuration = calls.reduce((sum, c) => sum + c.duration_ms, 0);

        const traceEntry = agentTrace.find((t) => t.agent === stage.key);
        let summary = "";
        let summaryHref: string | undefined;
        if (stage.key === "extraction" && traceEntry?.extracted) {
          const extracted = traceEntry.extracted as Record<string, unknown>;
          summary = String(extracted.figure_name || "");
        } else if (stage.key === "face_search" && traceEntry) {
          if (traceEntry.skipped) {
            const reason = String(traceEntry.reason ?? "skipped");
            const labels: Record<string, string> = {
              no_api_key: "no API key",
              no_results: "no results found",
              download_failed: "download failed",
              already_set: "face already provided",
              no_figure_name: "no figure name",
              search_api_error: "search error",
            };
            summary = `Skipped — ${labels[reason] ?? reason}`;
          } else {
            const url = String(traceEntry.source_url ?? "");
            summary = url ? new URL(url).hostname : "image found";
            summaryHref = url || undefined;
          }
        } else if (stage.key === "validation" && traceEntry) {
          summary = `Score: ${traceEntry.score ?? "—"} ${traceEntry.passed ? "(passed)" : "(failed)"}`;
        }

        return (
          <div key={stage.key} className="flex items-center gap-3 py-1.5">
            <div className="flex-shrink-0">
              {stageStatus === "completed" && <CheckCircle className="w-5 h-5 text-green-600" />}
              {stageStatus === "running" && <Loader className="w-5 h-5 text-blue-500 animate-spin" />}
              {stageStatus === "error" && <XCircle className="w-5 h-5 text-red-500" />}
              {stageStatus === "pending" && <Circle className="w-5 h-5 text-gray-300" />}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">{stage.label}</span>
                {stageStatus === "completed" && totalDuration > 0 && (
                  <span className="text-xs text-[var(--muted-foreground)]">
                    {totalDuration < 1000
                      ? `${Math.round(totalDuration)}ms`
                      : `${(totalDuration / 1000).toFixed(1)}s`}
                  </span>
                )}
                {stageStatus === "completed" && totalCost > 0 && (
                  <Badge variant="outline" className="text-xs">
                    ${totalCost.toFixed(6)}
                  </Badge>
                )}
                {stage.key === "image_generation" && stageStatus === "running" && imageProgress && (
                  <span className="text-xs text-[var(--muted-foreground)]">
                    Step {imageProgress.step}/{imageProgress.total}
                  </span>
                )}
              </div>
              {stage.key === "image_generation" && stageStatus === "running" && imageProgress && (
                <div className="mt-1 h-1.5 w-full rounded-full bg-[var(--muted)] overflow-hidden">
                  <div
                    className="h-full rounded-full bg-blue-500 transition-all duration-300"
                    style={{ width: `${Math.round((imageProgress.step / imageProgress.total) * 100)}%` }}
                  />
                </div>
              )}
              {summary && (
                <p className="text-xs text-[var(--muted-foreground)] truncate">
                  {summaryHref ? (
                    <a href={summaryHref} target="_blank" rel="noopener noreferrer" className="underline hover:text-[var(--foreground)]">
                      {summary}
                    </a>
                  ) : summary}
                </p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
