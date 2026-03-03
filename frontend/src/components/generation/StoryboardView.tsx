import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { VoiceInputButton } from "@/components/generation/VoiceInputButton";
import { StoryConversationPanel } from "@/components/generation/StoryConversationPanel";
import { api } from "@/api/client";
import type { StoryboardData } from "@/api/types";
import type { ArtifactEvent, SceneImageEvent } from "@/api/hooks/useGenerationWS";

interface StoryboardViewProps {
  storyboard: StoryboardData;
  requestId: string;
  sceneImages?: SceneImageEvent[];
  artifacts?: ArtifactEvent[];
}

export function StoryboardView({ storyboard, requestId, sceneImages = [], artifacts = [] }: StoryboardViewProps) {
  const { characters, panels, total_scenes, completed_scenes } = storyboard;
  const [showConversation, setShowConversation] = useState(false);
  const isComplete = completed_scenes === total_scenes && total_scenes > 0;

  const handleConversationEdit = async (sceneIndex: number, instruction: string) => {
    try {
      await api.post(`/generate/${requestId}/scenes/${sceneIndex}/edit`, { instruction });
    } catch (err) {
      console.error("Scene edit from conversation failed:", err);
    }
  };

  // Build a map of scene_index -> image_path from WS events (for live updates)
  const wsImageMap = new Map<number, string>();
  for (const evt of sceneImages) {
    wsImageMap.set(evt.scene_index, evt.image_path);
  }

  // Build a map of scene_index -> audio URL from artifact events
  const wsAudioMap = new Map<number, string>();
  for (const evt of artifacts) {
    if (evt.artifact_type === "audio" && evt.scene_index != null) {
      wsAudioMap.set(evt.scene_index, evt.url);
    }
  }

  // Build map of scene_index -> edited image URL from scene_edit artifacts
  const wsEditMap = new Map<number, string>();
  for (const evt of artifacts) {
    if (evt.artifact_type === "scene_edit" && evt.scene_index != null) {
      wsEditMap.set(evt.scene_index, evt.url);
    }
  }

  // Check for video artifact
  const videoArtifact = artifacts.find((a) => a.artifact_type === "video");

  return (
    <div className="space-y-6">
      {/* Characters summary */}
      {characters.length > 0 && (
        <div>
          <p className="text-sm text-[var(--muted-foreground)] mb-2">Characters</p>
          <div className="flex flex-wrap gap-2">
            {characters.map((char, i) => (
              <Badge key={i} variant="outline">
                {(char as Record<string, unknown>).name as string ?? `Character ${i + 1}`}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Progress bar */}
      <div>
        <p className="text-sm text-[var(--muted-foreground)] mb-1">
          Scenes: {completed_scenes} / {total_scenes} completed
        </p>
        <div className="w-full bg-[var(--muted)] rounded-full h-2">
          <div
            className="bg-[var(--primary)] h-2 rounded-full transition-all"
            style={{ width: `${total_scenes > 0 ? (completed_scenes / total_scenes) * 100 : 0}%` }}
          />
        </div>
      </div>

      {/* Video player */}
      {videoArtifact && (
        <div>
          <p className="text-sm text-[var(--muted-foreground)] mb-2">Storyboard Video</p>
          <video
            controls
            className="w-full rounded-md"
            src={videoArtifact.url}
          >
            Your browser does not support video playback.
          </video>
          <div className="mt-2">
            <a
              href={`/api/export/${requestId}/video`}
              download={`storyboard_${requestId}.mp4`}
              className="inline-flex"
            >
              <Button variant="outline" size="sm">
                Download Video
              </Button>
            </a>
          </div>
        </div>
      )}

      {/* Panel grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {panels.map((panel, i) => (
          <ScenePanel
            key={i}
            panel={panel}
            requestId={requestId}
            wsImageUrl={wsImageMap.has(panel.scene_index)
              ? `/output/${requestId}/scene_${panel.scene_index}/${wsImageMap.get(panel.scene_index)!.split("/").pop()}`
              : undefined
            }
            wsAudioUrl={wsAudioMap.get(panel.scene_index)}
            wsEditUrl={wsEditMap.get(panel.scene_index)}
            isCompleted={panel.status === "completed" || wsImageMap.has(panel.scene_index)}
          />
        ))}
      </div>

      {/* Conversation refinement panel */}
      {isComplete && (
        <div>
          {!showConversation ? (
            <Button
              variant="outline"
              onClick={() => setShowConversation(true)}
              className="w-full"
            >
              Refine with Gemini
            </Button>
          ) : (
            <StoryConversationPanel
              requestId={requestId}
              onApplyEdit={handleConversationEdit}
            />
          )}
        </div>
      )}
    </div>
  );
}

function ScenePanel({
  panel,
  requestId,
  wsImageUrl,
  wsAudioUrl,
  wsEditUrl,
  isCompleted,
}: {
  panel: StoryboardData["panels"][0];
  requestId: string;
  wsImageUrl?: string;
  wsAudioUrl?: string;
  wsEditUrl?: string;
  isCompleted: boolean;
}) {
  const [editMode, setEditMode] = useState(false);
  const [editInstruction, setEditInstruction] = useState("");
  const [isEditing, setIsEditing] = useState(false);
  const [showOriginal, setShowOriginal] = useState(false);

  const isFailed = panel.status === "failed";
  const imagePath = panel.image_path;
  const displayImageUrl = wsEditUrl
    ?? wsImageUrl
    ?? (isCompleted && imagePath
      ? `/output/${requestId}/scene_${panel.scene_index}/${imagePath.split("/").pop()}`
      : undefined);

  const originalImageUrl = (wsEditUrl && imagePath)
    ? `/output/${requestId}/scene_${panel.scene_index}/${imagePath.split("/").pop()}`
    : undefined;

  const handleEdit = async () => {
    if (!editInstruction.trim()) return;
    setIsEditing(true);
    try {
      await api.post(`/generate/${requestId}/scenes/${panel.scene_index}/edit`, {
        instruction: editInstruction,
      });
      // The scene_edit artifact will arrive via WebSocket
      setEditInstruction("");
      setEditMode(false);
    } catch (err) {
      console.error("Scene edit failed:", err);
    }
    setIsEditing(false);
  };

  return (
    <Card className={isFailed ? "border-[var(--destructive)]" : ""}>
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium">
            Scene {panel.scene_index + 1}
          </span>
          <div className="flex items-center gap-1">
            {isCompleted && !editMode && (
              <Button
                variant="ghost"
                size="sm"
                className="h-6 px-2 text-xs"
                onClick={() => setEditMode(true)}
                title="Edit this scene"
              >
                <PencilIcon className="w-3 h-3" />
              </Button>
            )}
            <Badge
              variant={isCompleted ? "secondary" : isFailed ? "destructive" : "outline"}
            >
              {isCompleted ? "Done" : isFailed ? "Failed" : "Generating..."}
            </Badge>
          </div>
        </div>

        {/* Image or placeholder */}
        {isCompleted && displayImageUrl ? (
          <div className="relative">
            <img
              src={showOriginal && originalImageUrl ? originalImageUrl : displayImageUrl}
              alt={`Scene ${panel.scene_index + 1}`}
              className="rounded-md w-full mb-3"
            />
            {/* Before/after toggle when edit exists */}
            {wsEditUrl && originalImageUrl && (
              <Button
                variant="secondary"
                size="sm"
                className="absolute bottom-4 right-2 text-xs h-6"
                onClick={() => setShowOriginal(!showOriginal)}
              >
                {showOriginal ? "Edited" : "Original"}
              </Button>
            )}
          </div>
        ) : (
          <div className="w-full aspect-square bg-[var(--muted)] rounded-md mb-3 flex items-center justify-center">
            {isFailed ? (
              <span className="text-sm text-[var(--destructive)]">Generation failed</span>
            ) : (
              <div className="animate-pulse text-sm text-[var(--muted-foreground)]">
                Generating image...
              </div>
            )}
          </div>
        )}

        {/* Scene edit input */}
        {editMode && (
          <div className="mb-3 space-y-2">
            <div className="flex gap-2 items-center">
              <Input
                placeholder="Describe the change... (e.g., 'make the lighting more dramatic')"
                value={editInstruction}
                onChange={(e) => setEditInstruction(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleEdit()}
                disabled={isEditing}
                className="flex-1 text-sm"
              />
              <VoiceInputButton
                onTranscript={(text) => setEditInstruction(text)}
                disabled={isEditing}
              />
            </div>
            <div className="flex gap-2">
              <Button
                size="sm"
                onClick={handleEdit}
                disabled={isEditing || !editInstruction.trim()}
              >
                {isEditing ? "Editing..." : "Apply Edit"}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => { setEditMode(false); setEditInstruction(""); }}
              >
                Cancel
              </Button>
            </div>
          </div>
        )}

        {/* Narration audio player */}
        {(wsAudioUrl || panel.narration_audio_path) ? (
          <div className="mb-2">
            <audio
              controls
              className="w-full h-8"
              src={wsAudioUrl ?? `/api/export/${requestId}/audio/${panel.scene_index}`}
            >
              Your browser does not support audio playback.
            </audio>
          </div>
        ) : isCompleted && panel.narration_text ? (
          <div className="mb-2 text-xs text-[var(--muted-foreground)] animate-pulse">
            Generating audio...
          </div>
        ) : null}

        {/* Narration text */}
        {panel.narration_text && (
          <p className="text-sm italic text-[var(--muted-foreground)] mb-2">
            &ldquo;{panel.narration_text}&rdquo;
          </p>
        )}

        {/* Scene description */}
        <p className="text-sm mb-2">{panel.description}</p>

        {/* Metadata */}
        <div className="flex flex-wrap gap-1">
          {panel.mood && (
            <Badge variant="outline" className="text-xs">{panel.mood}</Badge>
          )}
          {panel.setting && (
            <Badge variant="outline" className="text-xs">{panel.setting}</Badge>
          )}
          {panel.characters?.map((name, ci) => (
            <Badge key={ci} variant="secondary" className="text-xs">{name}</Badge>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function PencilIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
      <path d="m15 5 4 4" />
    </svg>
  );
}
