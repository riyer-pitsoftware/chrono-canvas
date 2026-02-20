import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAuditDetail, useDeleteGeneration, useRetryGeneration } from "@/api/hooks/useGeneration";
import { useNavigation } from "@/stores/navigation";
import { PipelineStepper } from "@/components/generation/PipelineStepper";
import { ChevronDown, ChevronRight, RotateCcw, Trash2 } from "lucide-react";

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

      {/* Generated Image */}
      {data.images.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Generated Images</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {data.images.map((img) => (
              <div key={img.id} className="space-y-2">
                <img
                  src={`/api/files/${img.file_path}`}
                  alt="Generated portrait"
                  className="rounded-md max-w-md"
                />
                <div className="text-xs text-[var(--muted-foreground)] space-y-1">
                  <p>Provider: {img.provider} | {img.width}x{img.height}</p>
                  {img.prompt_used && <p>Prompt: {img.prompt_used}</p>}
                </div>
              </div>
            ))}
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
    </div>
  );
}
