import { useCallback, useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAuditDetail, useDeleteGeneration, useRetryGeneration } from "@/api/hooks/useGeneration";
import { useNavigation } from "@/stores/navigation";
import { PipelineStepper } from "@/components/generation/PipelineStepper";
import { StateInspector } from "@/components/generation/StateInspector";
import { CostTimeline } from "@/components/generation/CostTimeline";
import { BookOpen, ChevronDown, ChevronLeft, ChevronRight, RotateCcw, Trash2, X } from "lucide-react";
import type { GeneratedImage } from "@/api/types";

const PIPELINE_STEPS = [
  { value: "orchestrator", label: "Orchestrator" },
  { value: "extraction", label: "Extraction" },
  { value: "research", label: "Research" },
  { value: "prompt_generation", label: "Prompt Generation" },
  { value: "image_generation", label: "Image Generation" },
  { value: "validation", label: "Validation" },
  { value: "face_swap", label: "Face Swap" },
  { value: "export", label: "Export" },
];

export function AuditDetail({ requestId }: { requestId: string }) {
  const { data, isLoading, error } = useAuditDetail(requestId);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [retryStep, setRetryStep] = useState<string | null>(null);
  const deleteGeneration = useDeleteGeneration();
  const retryGeneration = useRetryGeneration();
  const { navigate } = useNavigation();

  const effectiveRetryStep = retryStep ?? data?.current_agent ?? "image_generation";

  const toggle = (key: string) =>
    setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));

  if (isLoading) return <div>Loading audit details...</div>;
  if (error) return <div className="text-[var(--destructive)]">Error: {error.message}</div>;
  if (!data) return <div>No audit data found.</div>;

  const statusColor = data.status === "completed" ? "success" as const
    : data.status === "failed" ? "destructive" as const
    : "secondary" as const;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3 mb-2">
          <h2 className="text-3xl font-bold">Audit Detail</h2>
          <Badge variant={statusColor}>{data.status}</Badge>
          <Button
            variant="destructive"
            size="sm"
            className="ml-auto"
            onClick={() => {
              if (window.confirm("Delete this generation? This cannot be undone.")) {
                deleteGeneration.mutate(requestId, {
                  onSuccess: () => navigate("/audit"),
                });
              }
            }}
          >
            <Trash2 className="h-4 w-4 mr-1" />
            Delete
          </Button>
        </div>
        <div className="text-sm text-[var(--muted-foreground)] space-y-1">
          {data.figure_name && <p>Figure: <span className="font-medium text-[var(--foreground)]">{data.figure_name}</span></p>}
          <p>Input: {data.input_text}</p>
          <p>Created: {new Date(data.created_at).toLocaleString()}</p>
          <div className="flex gap-4">
            <span>Total cost: ${data.total_cost.toFixed(6)}</span>
            <span>Total duration: {(data.total_duration_ms / 1000).toFixed(1)}s</span>
          </div>
        </div>
      </div>

      {/* Pipeline Timeline */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Pipeline Timeline</CardTitle>
        </CardHeader>
        <CardContent>
          <PipelineStepper
            currentAgent={null}
            status={data.status}
            agentTrace={data.llm_calls.map((c) => ({ agent: c.agent, timestamp: c.timestamp }))}
            llmCalls={data.llm_calls}
          />
        </CardContent>
      </Card>

      {/* Cost & Latency Timeline */}
      {data.llm_calls.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Cost &amp; Latency Breakdown</CardTitle>
            <p className="text-sm text-[var(--muted-foreground)]">
              Bar width = wall-clock duration · Hover a segment to highlight the row
            </p>
          </CardHeader>
          <CardContent>
            <CostTimeline llmCalls={data.llm_calls} />
          </CardContent>
        </Card>
      )}

      {/* LLM Call Sections */}
      {data.llm_calls.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">LLM Calls ({data.llm_calls.length})</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {data.llm_calls.map((call, i) => {
              const key = `llm-${i}`;
              const isExpanded = expanded[key] ?? false;
              return (
                <div key={key} className="border rounded-md">
                  <button
                    onClick={() => toggle(key)}
                    className="w-full flex items-center gap-3 p-3 text-left hover:bg-[var(--accent)] transition-colors"
                  >
                    {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                    <span className="font-medium text-sm">{call.agent}</span>
                    {call.provider && (
                      <Badge variant="outline" className="text-xs">{call.provider}/{call.model}</Badge>
                    )}
                    <button
                      onClick={(e) => { e.stopPropagation(); navigate(`/guide/${call.agent}`); }}
                      className="flex items-center gap-1 text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors ml-1"
                      title="Learn about this step"
                    >
                      <BookOpen className="w-3.5 h-3.5" />
                      Learn
                    </button>
                    <span className="text-xs text-[var(--muted-foreground)] ml-auto flex gap-3">
                      <span>{call.duration_ms < 1000 ? `${Math.round(call.duration_ms)}ms` : `${(call.duration_ms / 1000).toFixed(1)}s`}</span>
                      <span>{call.input_tokens + call.output_tokens} tokens</span>
                      {call.cost > 0 && <span>${call.cost.toFixed(6)}</span>}
                    </span>
                  </button>
                  {isExpanded && (
                    <div className="px-3 pb-3 space-y-3 border-t">
                      {call.system_prompt && (
                        <div className="mt-3">
                          <p className="text-xs font-medium text-[var(--muted-foreground)] mb-1">System Prompt</p>
                          <pre className="text-xs bg-[var(--muted)] p-3 rounded-md overflow-auto whitespace-pre-wrap max-h-64">{call.system_prompt}</pre>
                        </div>
                      )}
                      {call.user_prompt && (
                        <div>
                          <p className="text-xs font-medium text-[var(--muted-foreground)] mb-1">User Prompt</p>
                          <pre className="text-xs bg-[var(--muted)] p-3 rounded-md overflow-auto whitespace-pre-wrap max-h-64">{call.user_prompt}</pre>
                        </div>
                      )}
                      {call.raw_response && (
                        <div>
                          <p className="text-xs font-medium text-[var(--muted-foreground)] mb-1">Raw Response</p>
                          <pre className="text-xs bg-[var(--muted)] p-3 rounded-md overflow-auto whitespace-pre-wrap max-h-64">{call.raw_response}</pre>
                        </div>
                      )}
                      {call.parsed_output != null && (
                        <div>
                          <p className="text-xs font-medium text-[var(--muted-foreground)] mb-1">Parsed Output</p>
                          <pre className="text-xs bg-[var(--muted)] p-3 rounded-md overflow-auto whitespace-pre-wrap max-h-64">
                            {typeof call.parsed_output === "string" ? call.parsed_output : JSON.stringify(call.parsed_output, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}

      {/* Agent State Inspector */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Agent State Inspector</CardTitle>
          <p className="text-sm text-[var(--muted-foreground)]">
            Full AgentState snapshot after each node ran. Diff view shows what each agent added or changed.
          </p>
        </CardHeader>
        <CardContent>
          <StateInspector snapshots={data.state_snapshots ?? []} />
        </CardContent>
      </Card>

      {/* Validation Section */}
      {data.validation_score != null && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg">Validation</CardTitle>
              <div className="flex items-center gap-2">
                <span className="text-lg font-bold">{data.validation_score.toFixed(1)}</span>
                <Badge variant={data.validation_passed ? "success" : "destructive"}>
                  {data.validation_passed ? "Passed" : "Failed"}
                </Badge>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {data.validation_reasoning && (
              <p className="text-sm text-[var(--muted-foreground)]">{data.validation_reasoning}</p>
            )}
            {data.validation_categories.map((cat, i) => (
              <div key={i} className="border rounded-md p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-medium">{cat.category}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold">{cat.score.toFixed(1)}</span>
                    <Badge variant={cat.passed ? "success" : "destructive"} className="text-xs">
                      {cat.passed ? "Pass" : "Fail"}
                    </Badge>
                  </div>
                </div>
                {cat.details && <p className="text-xs text-[var(--muted-foreground)]">{cat.details}</p>}
                {cat.reasoning && <p className="text-xs mt-1">{cat.reasoning}</p>}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Generated Images Gallery */}
      {data.images.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">
              Generated Images ({data.images.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ImageGallery images={data.images} requestId={requestId} />
          </CardContent>
        </Card>
      )}

      {/* Error */}
      {data.error_message && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg text-[var(--destructive)]">Error</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm">{data.error_message}</p>
          </CardContent>
        </Card>
      )}

      {/* Retry */}
      {data.status === "failed" && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Retry from Step</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-3">
              <select
                value={effectiveRetryStep}
                onChange={(e) => setRetryStep(e.target.value)}
                className="flex-1 rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm"
              >
                {PIPELINE_STEPS.map((s) => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
              <Button
                variant="outline"
                size="sm"
                disabled={retryGeneration.isPending}
                onClick={() =>
                  retryGeneration.mutate(
                    { id: requestId, fromStep: effectiveRetryStep },
                    { onSuccess: () => navigate(`/audit/${requestId}`) },
                  )
                }
              >
                <RotateCcw className="h-4 w-4 mr-1" />
                {retryGeneration.isPending ? "Retrying…" : "Retry"}
              </Button>
            </div>
            {retryGeneration.isError && (
              <p className="text-xs text-[var(--destructive)] mt-2">
                {retryGeneration.error?.message}
              </p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function imageUrl(img: GeneratedImage, requestId: string) {
  // file_path may be absolute or relative; extract just the filename
  const filename = img.file_path.split("/").pop();
  return `/output/${requestId}/${filename}`;
}

function ImageGallery({ images, requestId }: { images: GeneratedImage[]; requestId: string }) {
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);

  // Sort by created_at so attempt order is chronological
  const sorted = [...images].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
  );

  return (
    <>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {sorted.map((img, i) => (
          <button
            key={img.id}
            onClick={() => setLightboxIndex(i)}
            className="group relative rounded-md overflow-hidden border hover:ring-2 hover:ring-[var(--ring)] transition-all text-left"
          >
            <img
              src={imageUrl(img, requestId)}
              alt={`Attempt ${i + 1}`}
              className="w-full aspect-square object-cover"
            />
            {/* Overlay badges */}
            <div className="absolute top-2 left-2 flex flex-col gap-1">
              <Badge variant="secondary" className="text-xs">
                #{i + 1}
              </Badge>
              <Badge variant="outline" className="text-xs bg-[var(--background)]/80">
                {img.provider}
              </Badge>
            </div>
            {img.validation_score != null && (
              <div className="absolute top-2 right-2">
                <Badge
                  variant={img.validation_score >= 70 ? "success" : "destructive"}
                  className="text-xs"
                >
                  {img.validation_score.toFixed(0)}
                </Badge>
              </div>
            )}
            {/* Hover hint */}
            <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors flex items-center justify-center">
              <span className="text-white opacity-0 group-hover:opacity-100 text-sm font-medium drop-shadow-md transition-opacity">
                Click to enlarge
              </span>
            </div>
          </button>
        ))}
      </div>
      {lightboxIndex !== null && (
        <Lightbox
          images={sorted}
          requestId={requestId}
          currentIndex={lightboxIndex}
          onClose={() => setLightboxIndex(null)}
          onNavigate={setLightboxIndex}
        />
      )}
    </>
  );
}

function Lightbox({
  images,
  requestId,
  currentIndex,
  onClose,
  onNavigate,
}: {
  images: GeneratedImage[];
  requestId: string;
  currentIndex: number;
  onClose: () => void;
  onNavigate: (index: number) => void;
}) {
  const img = images[currentIndex];
  const hasPrev = currentIndex > 0;
  const hasNext = currentIndex < images.length - 1;

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowLeft" && hasPrev) onNavigate(currentIndex - 1);
      if (e.key === "ArrowRight" && hasNext) onNavigate(currentIndex + 1);
    },
    [onClose, onNavigate, currentIndex, hasPrev, hasNext],
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  return (
    <div
      className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center"
      onClick={onClose}
    >
      <div
        className="relative max-w-4xl max-h-[90vh] mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute -top-10 right-0 text-white hover:text-gray-300 transition-colors"
        >
          <X className="w-6 h-6" />
        </button>

        {/* Image */}
        <img
          src={imageUrl(img, requestId)}
          alt={`Attempt ${currentIndex + 1}`}
          className="max-h-[80vh] rounded-md object-contain"
        />

        {/* Info bar */}
        <div className="flex items-center justify-between mt-3 text-white text-sm">
          <div className="flex items-center gap-2">
            <Badge variant="secondary">Attempt #{currentIndex + 1}</Badge>
            <Badge variant="outline" className="text-white border-white/40">
              {img.provider}
            </Badge>
            {img.validation_score != null && (
              <Badge variant={img.validation_score >= 70 ? "success" : "destructive"}>
                Score: {img.validation_score.toFixed(1)}
                {img.validation_score >= 70 ? " (passed)" : " (failed)"}
              </Badge>
            )}
          </div>
          <span className="text-white/60">
            {img.width}x{img.height}
          </span>
        </div>

        {/* Navigation arrows */}
        {hasPrev && (
          <button
            onClick={() => onNavigate(currentIndex - 1)}
            className="absolute left-0 top-1/2 -translate-y-1/2 -translate-x-12 text-white hover:text-gray-300 transition-colors"
          >
            <ChevronLeft className="w-8 h-8" />
          </button>
        )}
        {hasNext && (
          <button
            onClick={() => onNavigate(currentIndex + 1)}
            className="absolute right-0 top-1/2 -translate-y-1/2 translate-x-12 text-white hover:text-gray-300 transition-colors"
          >
            <ChevronRight className="w-8 h-8" />
          </button>
        )}
      </div>
    </div>
  );
}
