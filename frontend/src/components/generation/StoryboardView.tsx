import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type { StoryboardData } from "@/api/types";
import type { ArtifactEvent, SceneImageEvent } from "@/api/hooks/useGenerationWS";

interface StoryboardViewProps {
  storyboard: StoryboardData;
  requestId: string;
  /** Incremental scene images arriving via WebSocket */
  sceneImages?: SceneImageEvent[];
  /** Uniform artifact events (images + audio) arriving via WebSocket */
  artifacts?: ArtifactEvent[];
}

export function StoryboardView({ storyboard, requestId, sceneImages = [], artifacts = [] }: StoryboardViewProps) {
  const { characters, panels, total_scenes, completed_scenes } = storyboard;

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

      {/* Panel grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {panels.map((panel, i) => {
          // Use WS image if available, otherwise fall back to storyboard data
          const imagePath = wsImageMap.get(panel.scene_index) ?? panel.image_path;
          const isCompleted = panel.status === "completed" || wsImageMap.has(panel.scene_index);
          const isFailed = panel.status === "failed";

          return (
            <Card key={i} className={isFailed ? "border-[var(--destructive)]" : ""}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium">
                    Scene {panel.scene_index + 1}
                  </span>
                  <Badge
                    variant={isCompleted ? "secondary" : isFailed ? "destructive" : "outline"}
                  >
                    {isCompleted ? "Done" : isFailed ? "Failed" : "Generating..."}
                  </Badge>
                </div>

                {/* Image or placeholder */}
                {isCompleted && imagePath ? (
                  <img
                    src={`/output/${requestId}/scene_${panel.scene_index}/${imagePath.split("/").pop()}`}
                    alt={`Scene ${panel.scene_index + 1}`}
                    className="rounded-md w-full mb-3"
                  />
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

                {/* Narration audio player — use WS artifact URL if available, else REST */}
                {(wsAudioMap.has(panel.scene_index) || panel.narration_audio_path) ? (
                  <div className="mb-2">
                    <audio
                      controls
                      className="w-full h-8"
                      src={wsAudioMap.get(panel.scene_index) ?? `/api/export/${requestId}/audio/${panel.scene_index}`}
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
        })}
      </div>
    </div>
  );
}
