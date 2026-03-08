import { useEffect, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  useCreateGeneration,
  useGeneration,
  useGenerationImages,
  useUploadFace,
  useUploadReferenceImage,
} from "@/api/hooks/useGeneration";
import { useFigure } from "@/api/hooks/useFigures";
import { useGenerationWS } from "@/api/hooks/useGenerationWS";
import { Textarea } from "@/components/ui/textarea";
import { PipelineStepper } from "@/components/generation/PipelineStepper";
import { DAGVisualizer } from "@/components/generation/DAGVisualizer";
import { StreamingText } from "@/components/generation/StreamingText";
import { StoryboardView } from "@/components/generation/StoryboardView";
import { TrustCard } from "@/components/generation/TrustCard";
import { VoiceInputButton } from "@/components/generation/VoiceInputButton";
import { TemplatePresets, type PresetTemplate } from "@/components/generation/TemplatePresets";
import { useNavigation } from "@/stores/navigation";
import { ConfigHUD } from "@/components/config/ConfigHUD";
import { useConfigStore } from "@/stores/configStore";
import { validateConfig } from "@/api/hooks/useConfig";

const MODE_LABELS: Record<string, string> = {
  creative_story: "Story Director",
  portrait: "Historical Lens",
};

export function Generate({ figureId, mode }: { figureId?: string; mode?: string }) {
  const [inputText, setInputText] = useState("");
  const [activeRequestId, setActiveRequestId] = useState<string | null>(null);
  const [faceId, setFaceId] = useState<string | null>(null);
  const [facePreview, setFacePreview] = useState<string | null>(null);
  const [refImageId, setRefImageId] = useState<string | null>(null);
  const [refImagePreview, setRefImagePreview] = useState<string | null>(null);
  const [showInputOptions, setShowInputOptions] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const refImageInputRef = useRef<HTMLInputElement>(null);
  const autoTriggered = useRef(false);
  const { navigate } = useNavigation();
  const { mutate: startGeneration, isPending: isCreating } = useCreateGeneration();
  const uploadFace = useUploadFace();
  const uploadRefImage = useUploadReferenceImage();
  const { data: figure } = useFigure(figureId ?? "");
  const activeRequest = useGeneration(activeRequestId ?? "");
  const isRunning = !!activeRequest.data && activeRequest.data.status !== "completed" && activeRequest.data.status !== "failed";
  const { imageProgress, streamingText, streamingAgent, sceneImages, artifacts } = useGenerationWS(activeRequestId, isRunning);
  const isStoryMode = mode === "creative_story";
  const images = useGenerationImages(
    activeRequest.data?.status === "completed" ? (activeRequestId ?? "") : "",
  );

  // When navigated from the Timeline with a figureId, pre-fill and auto-trigger
  useEffect(() => {
    if (!figure || autoTriggered.current || activeRequestId) return;
    autoTriggered.current = true;
    const text = figure.name;
    setInputText(text);
    startGeneration(
      { input_text: text, figure_id: figure.id },
      { onSuccess: (data) => setActiveRequestId(data.id) },
    );
  }, [figure, activeRequestId, startGeneration]);

  const configPayload = useConfigStore((s) => s.toPayload);

  const handlePresetSelect = (preset: PresetTemplate) => {
    setInputText(preset.prompt);
  };

  const handleGenerate = async () => {
    // For image-to-story: text is optional when image is provided
    if (!inputText.trim() && !refImageId) return;

    const config = configPayload();

    // Validate config before submitting
    try {
      const validation = await validateConfig(config);
      if (validation.errors?.length) {
        console.warn("Config validation warnings:", validation.errors);
      }
    } catch {
      // Config validation is non-blocking — proceed even if endpoint fails
    }

    startGeneration(
      {
        input_text: inputText,
        ...(figureId ? { figure_id: figureId } : {}),
        ...(faceId ? { face_id: faceId } : {}),
        ...(isStoryMode ? { run_type: "creative_story" } : {}),
        ...(refImageId ? { ref_image_id: refImageId } : {}),
        config,
      },
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

  const handleRefImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setRefImagePreview(URL.createObjectURL(file));
    uploadRefImage.mutate(
      { file, refType: "story_source" },
      {
        onSuccess: (data) => setRefImageId(data.ref_id),
        onError: () => {
          setRefImagePreview(null);
          setRefImageId(null);
        },
      },
    );
  };

  const clearFace = () => {
    setFaceId(null);
    if (facePreview) URL.revokeObjectURL(facePreview);
    setFacePreview(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const clearRefImage = () => {
    setRefImageId(null);
    if (refImagePreview) URL.revokeObjectURL(refImagePreview);
    setRefImagePreview(null);
    if (refImageInputRef.current) refImageInputRef.current.value = "";
  };

  const handleVoiceTranscript = (text: string) => {
    setInputText((prev) => (prev ? `${prev} ${text}` : text));
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
      <div className="flex items-center gap-3 mb-6">
        <h2 className="text-3xl font-bold">
          {mode ? MODE_LABELS[mode] ?? "Generate" : "Generate Portrait"}
        </h2>
        {mode && (
          <Badge variant="secondary">
            {mode === "creative_story" ? "Creative" : "Portrait"}
          </Badge>
        )}
      </div>

      <ConfigHUD className="mb-4" />

      {!activeRequestId && mode && (
        <TemplatePresets
          mode={mode}
          onSelect={handlePresetSelect}
          disabled={isCreating}
        />
      )}

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>New Generation</CardTitle>
        </CardHeader>
        <CardContent>
          <div className={isStoryMode ? "mb-4 space-y-3" : "flex gap-3 mb-4"}>
            {isStoryMode ? (
              <>
                <div className="relative">
                  <Textarea
                    placeholder={refImageId
                      ? "Optional: add guidance for the image-based story..."
                      : "Paste or write your story here..."
                    }
                    value={inputText}
                    onChange={(e) => setInputText(e.target.value)}
                    rows={6}
                    className="w-full pr-16"
                  />
                  <div className="absolute top-2 right-2">
                    <VoiceInputButton
                      onTranscript={handleVoiceTranscript}
                      disabled={isCreating}
                    />
                  </div>
                </div>

                {/* Collapsible Input Options */}
                <div className="border border-[var(--border)] rounded-md">
                  <button
                    type="button"
                    className="w-full px-3 py-2 text-sm text-[var(--muted-foreground)] text-left flex items-center justify-between hover:bg-[var(--muted)] rounded-md transition-colors"
                    onClick={() => setShowInputOptions(!showInputOptions)}
                  >
                    <span>Input Options</span>
                    <span className="text-xs">{showInputOptions ? "▲" : "▼"}</span>
                  </button>
                  {showInputOptions && (
                    <div className="px-3 pb-3 flex flex-wrap gap-3">
                      {/* Upload Image for Image-to-Story */}
                      <div>
                        <input
                          ref={refImageInputRef}
                          type="file"
                          accept="image/jpeg,image/png,image/webp"
                          onChange={handleRefImageUpload}
                          className="hidden"
                        />
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => refImageInputRef.current?.click()}
                          disabled={uploadRefImage.isPending}
                        >
                          {uploadRefImage.isPending ? "Uploading..." : "Upload Image"}
                        </Button>
                        {refImagePreview && (
                          <div className="flex items-center gap-2 mt-2">
                            <img
                              src={refImagePreview}
                              alt="Reference preview"
                              className="w-16 h-16 rounded-md object-cover"
                            />
                            {refImageId && <Badge variant="outline">Ready</Badge>}
                            <Button variant="ghost" size="sm" onClick={clearRefImage}>
                              Remove
                            </Button>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>

                <Button
                  onClick={handleGenerate}
                  disabled={isCreating || (!inputText.trim() && !refImageId)}
                  className="w-full"
                >
                  {isCreating ? "Starting..." :
                    refImageId ? "Generate Storyboard from Image" : "Generate Storyboard"}
                </Button>
              </>
            ) : (
              <>
                <Input
                  placeholder="Describe a historical figure... (e.g., 'Cleopatra, Queen of Egypt')"
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleGenerate()}
                  className="flex-1"
                />
                <Button onClick={handleGenerate} disabled={isCreating || !inputText.trim()}>
                  {isCreating ? "Starting..." : "Generate"}
                </Button>
              </>
            )}
          </div>

          {!isStoryMode && (
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
          )}
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
                    runType={activeRequest.data.run_type}
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
                    runType={activeRequest.data.run_type}
                  />
                </div>
              )}

              {/* Storyboard view for story mode */}
              {activeRequest.data.run_type === "creative_story" && activeRequest.data.storyboard_data && (
                <div>
                  <p className="text-sm text-[var(--muted-foreground)] mb-2">Storyboard</p>
                  <StoryboardView
                    storyboard={activeRequest.data.storyboard_data}
                    requestId={activeRequestId!}
                    sceneImages={sceneImages}
                    artifacts={artifacts}
                  />
                </div>
              )}

              {/* Portrait mode images — show via artifact event (early) or REST poll (final) */}
              {activeRequest.data.run_type !== "creative_story" && (() => {
                const portraitArtifact = artifacts.find(
                  (a) => a.artifact_type === "image" && a.scene_index == null,
                );
                const hasRestImages = images.data && images.data.length > 0;
                if (!portraitArtifact && !hasRestImages) return null;
                return (
                  <div>
                    <p className="text-sm text-[var(--muted-foreground)] mb-2">Generated Images</p>
                    <div className="grid grid-cols-2 gap-4">
                      {/* Show WS artifact image immediately if REST data hasn't loaded yet */}
                      {portraitArtifact && !hasRestImages && (
                        <div className="relative">
                          <img
                            src={portraitArtifact.url}
                            alt="Generated portrait"
                            className="rounded-md w-full"
                          />
                        </div>
                      )}
                      {images.data?.map((img) => (
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
                );
              })()}

              {/* TrustCard — pipeline transparency after completion */}
              {(activeRequest.data.status === "completed" || activeRequest.data.status === "failed") &&
                activeRequest.data.agent_trace &&
                activeRequest.data.agent_trace.length > 0 && (
                <TrustCard
                  agentTrace={activeRequest.data.agent_trace}
                  llmCalls={activeRequest.data.llm_calls ?? []}
                  runType={activeRequest.data.run_type}
                  status={activeRequest.data.status}
                  defaultCollapsed={false}
                />
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
