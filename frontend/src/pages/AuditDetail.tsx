import { useCallback, useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAuditDetail, useAuditFeedback, useCreateFeedback, useDeleteGeneration, useRetryGeneration } from "@/api/hooks/useGeneration";
import { useNavigation } from "@/stores/navigation";
import { PipelineStepper } from "@/components/generation/PipelineStepper";
import { StateInspector } from "@/components/generation/StateInspector";
import { CostTimeline } from "@/components/generation/CostTimeline";
import { DAGVisualizer } from "@/components/generation/DAGVisualizer";
import { StoryboardView } from "@/components/generation/StoryboardView";
import { BookOpen, ChevronDown, ChevronLeft, ChevronRight, Copy, Download, ExternalLink, RotateCcw, ShieldCheck, Trash2, X } from "lucide-react";
import type { AuditFeedback, GeneratedImage } from "@/api/types";
import { MessageSquare, Send } from "lucide-react";

const PIPELINE_STEPS = [
  { value: "orchestrator", label: "Orchestrator" },
  { value: "extraction", label: "Extraction" },
  { value: "research", label: "Research" },
  { value: "face_search", label: "Face Search" },
  { value: "prompt_generation", label: "Prompt Generation" },
  { value: "image_generation", label: "Image Generation" },
  { value: "validation", label: "Validation" },
  { value: "facial_compositing", label: "Facial Compositing" },
  { value: "export", label: "Export" },
];

export function AuditDetail({ requestId }: { requestId: string }) {
  const { data, isLoading, error } = useAuditDetail(requestId);
  const { data: feedbackData } = useAuditFeedback(requestId);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [retryStep, setRetryStep] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const deleteGeneration = useDeleteGeneration();
  const retryGeneration = useRetryGeneration();
  const { navigate } = useNavigation();

  const effectiveRetryStep = retryStep ?? data?.current_agent ?? "image_generation";

  const toggle = (key: string) =>
    setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));

  useEffect(() => {
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(false), 1500);
    return () => window.clearTimeout(timer);
  }, [copied]);

  if (isLoading) return <div>Loading audit details...</div>;
  if (error) return <div className="text-[var(--destructive)]">Error: {error.message}</div>;
  if (!data) return <div>No audit data found.</div>;

  const statusColor = data.status === "completed" ? "success" as const
    : data.status === "failed" ? "destructive" as const
    : "secondary" as const;

  const handleCopyId = async () => {
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(data.id);
      } else {
        const textarea = document.createElement("textarea");
        textarea.value = data.id;
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.appendChild(textarea);
        textarea.focus();
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
      }
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex flex-wrap items-center gap-3 mb-2">
          <h2 className="text-3xl font-bold">Audit Detail</h2>
          <Badge variant={statusColor}>{data.status}</Badge>
          <div className="flex items-center gap-2 ml-auto">
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate(`/validate?request_id=${data.id}`)}
            >
              <ShieldCheck className="h-4 w-4 mr-1" />
              Validate
            </Button>
            <Button
              variant="destructive"
              size="sm"
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
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs text-[var(--muted-foreground)] mb-2">
          <span className="uppercase tracking-wide">Request ID</span>
          <code className="rounded bg-[var(--muted)] px-2 py-1 text-[var(--foreground)] text-xs">{data.id}</code>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2"
            onClick={handleCopyId}
          >
            <Copy className="h-3.5 w-3.5 mr-1" />
            {copied ? "Copied" : "Copy"}
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
            agentTrace={data.agent_trace ?? data.llm_calls.map((c) => ({ agent: c.agent, timestamp: c.timestamp }))}
            llmCalls={data.llm_calls}
          />
        </CardContent>
      </Card>

      {/* DAG + Cost & Latency — tabbed card */}
      <DAGCostCard
        currentAgent={data.current_agent ?? null}
        status={data.status}
        agentTrace={data.agent_trace ?? []}
        llmCalls={data.llm_calls}
      />

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
                      <StepFeedback
                        requestId={requestId}
                        stepName={call.agent}
                        feedback={feedbackData?.items?.filter((f) => f.step_name === call.agent) ?? []}
                      />
                    </div>
                  )}
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}

      {/* Agent Steps (non-LLM nodes: face_search, facial_compositing) */}
      <AgentStepsCard agentTrace={data.agent_trace ?? []} requestId={requestId} feedback={feedbackData?.items ?? []} />

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

      {/* Storyboard (story mode) */}
      {data.storyboard_data && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">
              Storyboard ({data.storyboard_data.completed_scenes} / {data.storyboard_data.total_scenes} scenes)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <StoryboardView
              storyboard={data.storyboard_data}
              requestId={requestId}
            />
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

// Agents that produce trace entries but no LLM calls
const NON_LLM_AGENTS = ["face_search", "facial_compositing"];

function AgentStepsCard({ agentTrace, requestId, feedback }: { agentTrace: Array<Record<string, unknown>>; requestId: string; feedback: AuditFeedback[] }) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const toggle = (key: string) => setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));

  const steps = agentTrace.filter((t) => NON_LLM_AGENTS.includes(String(t.agent)));
  if (steps.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Agent Steps ({steps.length})</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {steps.map((entry, i) => {
          const key = `step-${i}`;
          const isExpanded = expanded[key] ?? false;
          const agent = String(entry.agent);
          const skipped = Boolean(entry.skipped);

          return (
            <div key={key} className="border rounded-md">
              <button
                onClick={() => toggle(key)}
                className="w-full flex items-center gap-3 p-3 text-left hover:bg-[var(--accent)] transition-colors"
              >
                {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                <span className="font-medium text-sm">{agent}</span>
                {skipped ? (
                  <Badge variant="secondary" className="text-xs">skipped</Badge>
                ) : (
                  <Badge variant="outline" className="text-xs text-green-700 border-green-300">completed</Badge>
                )}
                {!!entry.reason && (
                  <span className="text-xs text-[var(--muted-foreground)]">{String(entry.reason)}</span>
                )}
                {agent === "face_search" && !skipped && !!entry.source_url && (
                  <a
                    href={String(entry.source_url)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-blue-600 underline truncate max-w-xs ml-auto"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {(() => { try { return new URL(String(entry.source_url)).hostname; } catch { return "source"; } })()}
                  </a>
                )}
              </button>

              {isExpanded && (
                <div className="px-3 pb-3 border-t space-y-3 mt-3">
                  {/* face_search details */}
                  {agent === "face_search" && (
                    <>
                      {entry.face_search_query || entry.query ? (
                        <div>
                          <p className="text-xs font-medium text-[var(--muted-foreground)] mb-1">Search Query</p>
                          <p className="text-xs bg-[var(--muted)] p-2 rounded">{String(entry.face_search_query ?? entry.query ?? "")}</p>
                        </div>
                      ) : null}
                      {!skipped && entry.source_url && (
                        <>
                          <div>
                            <p className="text-xs font-medium text-[var(--muted-foreground)] mb-1">Source URL</p>
                            <a
                              href={String(entry.source_url)}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-xs text-blue-600 underline break-all"
                            >
                              {String(entry.source_url)}
                            </a>
                          </div>
                          <div>
                            <p className="text-xs font-medium text-[var(--muted-foreground)] mb-1">Downloaded Face</p>
                            <img
                              src={`/output/${requestId}/${String(entry.local_path ?? "").split("/").pop()}`}
                              alt="sourced face"
                              className="h-32 w-32 object-cover rounded border"
                              onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                            />
                          </div>
                        </>
                      )}
                      {entry.candidates_tried != null && (
                        <p className="text-xs text-[var(--muted-foreground)]">
                          Tried {String(entry.candidates_tried)} candidate{Number(entry.candidates_tried) !== 1 ? "s" : ""}
                        </p>
                      )}
                    </>
                  )}

                  {/* facial_compositing details */}
                  {agent === "facial_compositing" && !skipped && (
                    <>
                      {entry.source_face && (
                        <div>
                          <p className="text-xs font-medium text-[var(--muted-foreground)] mb-1">Source Face</p>
                          <p className="text-xs text-[var(--muted-foreground)] break-all">{String(entry.source_face)}</p>
                        </div>
                      )}
                      {entry.swapped_path && (
                        <div>
                          <p className="text-xs font-medium text-[var(--muted-foreground)] mb-1">Output</p>
                          <p className="text-xs text-[var(--muted-foreground)] break-all">{String(entry.swapped_path)}</p>
                        </div>
                      )}
                    </>
                  )}

                  {/* Raw trace JSON fallback */}
                  <details className="text-xs">
                    <summary className="cursor-pointer text-[var(--muted-foreground)] hover:text-[var(--foreground)]">Raw trace entry</summary>
                    <pre className="mt-2 bg-[var(--muted)] p-2 rounded overflow-auto max-h-48 whitespace-pre-wrap">
                      {JSON.stringify(entry, null, 2)}
                    </pre>
                  </details>
                  <StepFeedback
                    requestId={requestId}
                    stepName={agent}
                    feedback={feedback.filter((f) => f.step_name === agent)}
                  />
                </div>
              )}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

// ── Step Feedback ─────────────────────────────────────────────────────────────

function StepFeedback({
  requestId,
  stepName,
  feedback,
}: {
  requestId: string;
  stepName: string;
  feedback: AuditFeedback[];
}) {
  const [open, setOpen] = useState(false);
  const [author, setAuthor] = useState("");
  const [comment, setComment] = useState("");
  const createFeedback = useCreateFeedback();

  const handleSubmit = () => {
    if (!comment.trim() || !author.trim()) return;
    createFeedback.mutate(
      { requestId, step_name: stepName, comment: comment.trim(), author: author.trim() },
      {
        onSuccess: () => {
          setComment("");
          setOpen(false);
        },
      },
    );
  };

  return (
    <div className="mt-3 pt-3 border-t border-dashed">
      {/* Existing comments */}
      {feedback.length > 0 && (
        <div className="space-y-2 mb-3">
          {feedback.map((f) => (
            <div key={f.id} className="flex items-start gap-2 text-xs">
              <MessageSquare className="w-3.5 h-3.5 mt-0.5 text-[var(--muted-foreground)] flex-shrink-0" />
              <div>
                <span className="font-medium">{f.author}</span>
                <span className="text-[var(--muted-foreground)] ml-2">
                  {new Date(f.created_at).toLocaleString()}
                </span>
                <p className="mt-0.5">{f.comment}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add comment toggle */}
      {!open ? (
        <button
          onClick={() => setOpen(true)}
          className="flex items-center gap-1.5 text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
        >
          <MessageSquare className="w-3.5 h-3.5" />
          Add comment
        </button>
      ) : (
        <div className="space-y-2">
          <input
            type="text"
            placeholder="Your name"
            value={author}
            onChange={(e) => setAuthor(e.target.value)}
            className="w-full text-xs rounded border border-[var(--border)] bg-[var(--background)] px-2 py-1.5"
          />
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Add a comment on this step..."
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
              className="flex-1 text-xs rounded border border-[var(--border)] bg-[var(--background)] px-2 py-1.5"
            />
            <Button
              variant="outline"
              size="sm"
              className="h-7 px-2"
              disabled={!comment.trim() || !author.trim() || createFeedback.isPending}
              onClick={handleSubmit}
            >
              <Send className="w-3.5 h-3.5" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── DAG + Cost tabbed card ────────────────────────────────────────────────────

type DAGCostTab = "dag" | "cost";

function DAGCostCard({
  currentAgent,
  status,
  agentTrace,
  llmCalls,
}: {
  currentAgent: string | null;
  status: string;
  agentTrace: Array<Record<string, unknown>>;
  llmCalls: import("@/api/types").LLMCallDetail[];
}) {
  const [activeTab, setActiveTab] = useState<DAGCostTab>("dag");
  const hasCost = llmCalls.length > 0;

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">
            {activeTab === "dag" ? "Pipeline DAG" : "Cost & Latency Breakdown"}
          </CardTitle>
          <div className="flex rounded-md border border-[var(--border)] overflow-hidden text-sm">
            <button
              onClick={() => setActiveTab("dag")}
              className={`px-3 py-1 transition-colors ${
                activeTab === "dag"
                  ? "bg-[var(--foreground)] text-[var(--background)]"
                  : "hover:bg-[var(--accent)] text-[var(--muted-foreground)]"
              }`}
            >
              DAG
            </button>
            <button
              onClick={() => setActiveTab("cost")}
              disabled={!hasCost}
              className={`px-3 py-1 transition-colors border-l border-[var(--border)] ${
                activeTab === "cost"
                  ? "bg-[var(--foreground)] text-[var(--background)]"
                  : hasCost
                  ? "hover:bg-[var(--accent)] text-[var(--muted-foreground)]"
                  : "opacity-40 cursor-not-allowed text-[var(--muted-foreground)]"
              }`}
            >
              Cost &amp; Latency
            </button>
          </div>
        </div>
        <p className="text-sm text-[var(--muted-foreground)]">
          {activeTab === "dag"
            ? "Nodes completed this run are highlighted green; conditional edges show the path taken"
            : "Bar width = wall-clock duration · Hover a segment to highlight the row"}
        </p>
      </CardHeader>
      <CardContent>
        {activeTab === "dag" ? (
          <DAGVisualizer
            currentAgent={currentAgent}
            status={status}
            agentTrace={agentTrace}
          />
        ) : (
          <CostTimeline llmCalls={llmCalls} />
        )}
      </CardContent>
    </Card>
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
            {/* Hover overlay */}
            <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-colors flex items-center justify-center gap-3">
              <span className="text-white opacity-0 group-hover:opacity-100 text-sm font-medium drop-shadow-md transition-opacity">
                Enlarge
              </span>
              <a
                href={imageUrl(img, requestId)}
                download
                className="opacity-0 group-hover:opacity-100 text-white hover:text-gray-200 transition-opacity drop-shadow-md"
                title="Download"
                onClick={(e) => e.stopPropagation()}
              >
                <Download className="w-5 h-5" />
              </a>
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
          <div className="flex items-center gap-3">
            <span className="text-white/60">{img.width}x{img.height}</span>
            <a
              href={imageUrl(img, requestId)}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-white/80 hover:text-white transition-colors"
              title="Open in new tab"
              onClick={(e) => e.stopPropagation()}
            >
              <ExternalLink className="w-4 h-4" />
            </a>
            <a
              href={imageUrl(img, requestId)}
              download
              className="flex items-center gap-1 text-white/80 hover:text-white transition-colors"
              title="Download image"
              onClick={(e) => e.stopPropagation()}
            >
              <Download className="w-4 h-4" />
            </a>
          </div>
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
