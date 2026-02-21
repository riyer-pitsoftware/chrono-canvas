import { useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  useCreateGeneration,
  useGeneration,
  useGenerationImages,
  useUploadFace,
} from "@/api/hooks/useGeneration";
import { useGenerationWS } from "@/api/hooks/useGenerationWS";
import { PipelineStepper } from "@/components/generation/PipelineStepper";
import { DAGVisualizer } from "@/components/generation/DAGVisualizer";
import { StreamingText } from "@/components/generation/StreamingText";
import { useNavigation } from "@/stores/navigation";

export function Generate() {
  const [inputText, setInputText] = useState("");
  const [activeRequestId, setActiveRequestId] = useState<string | null>(null);
  const [faceId, setFaceId] = useState<string | null>(null);
  const [facePreview, setFacePreview] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { navigate } = useNavigation();
  const createGeneration = useCreateGeneration();
  const uploadFace = useUploadFace();
  const activeRequest = useGeneration(activeRequestId ?? "");
  const isRunning = !!activeRequest.data && activeRequest.data.status !== "completed" && activeRequest.data.status !== "failed";
  const { imageProgress, streamingText, streamingAgent } = useGenerationWS(activeRequestId, isRunning);
  const images = useGenerationImages(
    activeRequest.data?.status === "completed" ? (activeRequestId ?? "") : "",
  );

  const handleGenerate = () => {
    if (!inputText.trim()) return;
    createGeneration.mutate(
      { input_text: inputText, ...(faceId ? { face_id: faceId } : {}) },
      {
        onSuccess: (data) => {
          setActiveRequestId(data.id);
        },
      },
    );
  };

  const handleFaceUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setFacePreview(URL.createObjectURL(file));
    uploadFace.mutate(file, {
      onSuccess: (data) => setFaceId(data.face_id),
      onError: () => {
        setFacePreview(null);
        setFaceId(null);
      },
    });
  };

  const clearFace = () => {
    setFaceId(null);
    if (facePreview) URL.revokeObjectURL(facePreview);
    setFacePreview(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const statusColor = (status: string) => {
    switch (status) {
      case "completed": return "success" as const;
      case "failed": return "destructive" as const;
      default: return "secondary" as const;
    }
  };

  return (
    <div>
      <h2 className="text-3xl font-bold mb-6">Generate Portrait</h2>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>New Generation</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-3 mb-4">
            <Input
              placeholder="Describe a historical figure... (e.g., 'Cleopatra, Queen of Egypt')"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleGenerate()}
              className="flex-1"
            />
            <Button onClick={handleGenerate} disabled={createGeneration.isPending || !inputText.trim()}>
              {createGeneration.isPending ? "Starting..." : "Generate"}
            </Button>
          </div>

          <div className="flex items-center gap-3">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={handleFaceUpload}
              className="hidden"
            />
            <Button
              variant="outline"
              size="sm"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploadFace.isPending}
            >
              {uploadFace.isPending ? "Uploading..." : "Upload Face"}
            </Button>
            {facePreview && (
              <div className="flex items-center gap-2">
                <img
                  src={facePreview}
                  alt="Face preview"
                  className="w-8 h-8 rounded-full object-cover"
                />
                {faceId && <Badge variant="outline">Uploaded</Badge>}
                <Button variant="ghost" size="sm" onClick={clearFace}>
                  Remove
                </Button>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {activeRequest.data && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Generation Progress</CardTitle>
              <Badge variant={statusColor(activeRequest.data.status)}>
                {activeRequest.data.status}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <p className="text-sm text-[var(--muted-foreground)]">Input</p>
                <p>{activeRequest.data.input_text}</p>
              </div>

              {activeRequest.data.current_agent && (
                <div>
                  <p className="text-sm text-[var(--muted-foreground)]">Current Agent</p>
                  <p className="font-medium">{activeRequest.data.current_agent}</p>
                </div>
              )}

              {activeRequest.data.extracted_data && (
                <div>
                  <p className="text-sm text-[var(--muted-foreground)]">Extracted Data</p>
                  <pre className="text-xs bg-[var(--muted)] p-3 rounded-md overflow-auto">
                    {JSON.stringify(activeRequest.data.extracted_data, null, 2)}
                  </pre>
                </div>
              )}

              {activeRequest.data.generated_prompt && (
                <div>
                  <p className="text-sm text-[var(--muted-foreground)]">Generated Prompt</p>
                  <p className="text-sm">{activeRequest.data.generated_prompt}</p>
                </div>
              )}

              {activeRequest.data.error_message && (
                <div className="text-[var(--destructive)]">
                  <p className="text-sm font-medium">Error</p>
                  <p>{activeRequest.data.error_message}</p>
                </div>
              )}

              {(streamingText || streamingAgent) && (
                <StreamingText
                  agent={streamingAgent ?? activeRequest.data.current_agent ?? ""}
                  text={streamingText}
                  isStreaming={!!streamingAgent}
                />
              )}

              {activeRequest.data && (
                <div>
                  <p className="text-sm text-[var(--muted-foreground)] mb-2">Pipeline Graph</p>
                  <DAGVisualizer
                    currentAgent={activeRequest.data.current_agent}
                    status={activeRequest.data.status}
                    agentTrace={activeRequest.data.agent_trace ?? []}
                  />
                </div>
              )}

              {activeRequest.data.agent_trace && activeRequest.data.agent_trace.length > 0 && (
                <div>
                  <p className="text-sm text-[var(--muted-foreground)] mb-2">Pipeline Progress</p>
                  <PipelineStepper
                    currentAgent={activeRequest.data.current_agent}
                    status={activeRequest.data.status}
                    agentTrace={activeRequest.data.agent_trace}
                    llmCalls={activeRequest.data.llm_calls ?? undefined}
                    imageProgress={imageProgress}
                  />
                </div>
              )}

              {images.data && images.data.length > 0 && (
                <div>
                  <p className="text-sm text-[var(--muted-foreground)] mb-2">Generated Images</p>
                  <div className="grid grid-cols-2 gap-4">
                    {images.data.map((img) => (
                      <div key={img.id} className="relative">
                        <img
                          src={`/output/${activeRequestId}/${img.file_path.split("/").pop()}`}
                          alt={`Generated by ${img.provider}`}
                          className="rounded-md w-full"
                        />
                        <Badge
                          variant="secondary"
                          className="absolute top-2 left-2"
                        >
                          {img.provider}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {(activeRequest.data.status === "completed" || activeRequest.data.status === "failed") && (
                <Button
                  variant="outline"
                  onClick={() => navigate(`/audit/${activeRequest.data!.id}`)}
                >
                  View Full Audit
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
