import { Badge } from "@/components/ui/badge";
import { CheckCircle, Circle, Loader, XCircle } from "lucide-react";
import type { LLMCallDetail } from "@/api/types";
import type { ImageProgress } from "@/api/hooks/useGenerationWS";
import { PatienceMeter } from "./PatienceMeter";

const PORTRAIT_STAGES = [
  { key: "extraction", label: "Extraction" },
  { key: "research", label: "Research" },
  { key: "face_search", label: "Face Search" },
  { key: "prompt_generation", label: "Prompt Generation" },
  { key: "image_generation", label: "Image Generation" },
  { key: "validation", label: "Validation" },
  { key: "facial_compositing", label: "Facial Compositing" },
  { key: "export", label: "Export" },
] as const;

const STORY_STAGES = [
  { key: "story_orchestrator", label: "Orchestrator" },
  { key: "image_to_story", label: "Image to Story" },
  { key: "reference_image_analysis", label: "Ref Image Analysis" },
  { key: "character_extraction", label: "Character Extraction" },
  { key: "scene_decomposition", label: "Scene Decomposition" },
  { key: "scene_prompt_generation", label: "Prompt Generation" },
  { key: "scene_image_generation", label: "Image Generation" },
  { key: "storyboard_coherence", label: "Coherence Check" },
  { key: "narration_script", label: "Narration Script" },
  { key: "narration_audio", label: "Narration Audio" },
  { key: "video_assembly", label: "Video Assembly" },
  { key: "storyboard_export", label: "Export" },
] as const;

interface PipelineStepperProps {
  currentAgent: string | null;
  status: string;
  agentTrace: Array<Record<string, unknown>>;
  llmCalls?: LLMCallDetail[];
  imageProgress?: ImageProgress | null;
  runType?: string;
}

function getStageStatus(
  stageKey: string,
  currentAgent: string | null,
  status: string,
  completedAgents: Set<string>,
): "pending" | "running" | "completed" | "error" {
  if (status === "failed" && currentAgent === stageKey) return "error";
  if (completedAgents.has(stageKey)) return "completed";
  if (currentAgent === stageKey && status !== "completed" && status !== "failed") return "running";
  return "pending";
}

export function PipelineStepper({ currentAgent, status, agentTrace, llmCalls = [], imageProgress, runType }: PipelineStepperProps) {
  const stages = runType === "creative_story" ? STORY_STAGES : PORTRAIT_STAGES;
  const completedAgents = new Set(agentTrace.map((t) => String(t.agent)));

  const callsByAgent = new Map<string, LLMCallDetail[]>();
  for (const call of llmCalls) {
    const existing = callsByAgent.get(call.agent) || [];
    existing.push(call);
    callsByAgent.set(call.agent, existing);
  }

  return (
    <div className="space-y-1">
      {stages.map((stage) => {
        const stageStatus = getStageStatus(stage.key, currentAgent, status, completedAgents);
        const calls = callsByAgent.get(stage.key) || [];
        const totalCost = calls.reduce((sum, c) => sum + c.cost, 0);
        const totalDuration = calls.reduce((sum, c) => sum + c.duration_ms, 0);

        const traceEntry = agentTrace.find((t) => t.agent === stage.key);
        let summary = "";
        let summaryHref: string | undefined;
        const cacheHit = stage.key === "research" && traceEntry?.cache_hit === true;
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

        // For scene_image_generation with per-scene progress, show fraction instead
        const isSceneImageRunning =
          (stage.key === "scene_image_generation" || stage.key === "image_generation") &&
          stageStatus === "running" &&
          imageProgress;

        return (
          <div key={stage.key} className="flex items-start gap-3 py-1.5">
            <div className="flex-shrink-0 mt-0.5">
              {stageStatus === "completed" && <CheckCircle className="w-5 h-5 text-green-600" />}
              {stageStatus === "running" && <Loader className="w-5 h-5 text-blue-500 animate-spin" />}
              {stageStatus === "error" && <XCircle className="w-5 h-5 text-red-500" />}
              {stageStatus === "pending" && <Circle className="w-5 h-5 text-gray-300" />}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">{stage.label}</span>
                {cacheHit && (
                  <Badge variant="secondary" className="text-xs">
                    from memory
                  </Badge>
                )}
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
                {isSceneImageRunning && (
                  <span className="text-xs text-[var(--muted-foreground)]">
                    {imageProgress.step}/{imageProgress.total} scenes
                  </span>
                )}
              </div>
              {summary && (
                <p className="text-xs text-[var(--muted-foreground)] truncate">
                  {summaryHref ? (
                    <a href={summaryHref} target="_blank" rel="noopener noreferrer" className="underline hover:text-[var(--foreground)]">
                      {summary}
                    </a>
                  ) : summary}
                </p>
              )}
              <PatienceMeter
                phase={stage.key}
                status={stageStatus}
                elapsedMs={stageStatus === "completed" ? totalDuration : undefined}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
