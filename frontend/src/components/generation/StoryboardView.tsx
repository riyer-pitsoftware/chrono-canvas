import { useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { VoiceInputButton } from '@/components/generation/VoiceInputButton';
import { LiveVoiceNarration } from '@/components/generation/LiveVoiceNarration';
import { StoryConversationPanel } from '@/components/generation/StoryConversationPanel';
import { api } from '@/api/client';
import type { StoryboardData } from '@/api/types';
import type { ArtifactEvent, SceneImageEvent } from '@/api/hooks/useGenerationWS';

interface StoryboardViewProps {
  storyboard: StoryboardData;
  requestId: string;
  sceneImages?: SceneImageEvent[];
  artifacts?: ArtifactEvent[];
}

export function StoryboardView({
  storyboard,
  requestId,
  sceneImages = [],
  artifacts = [],
}: StoryboardViewProps) {
  const { characters, panels, total_scenes, completed_scenes, grounding_sources } = storyboard;
  const [showSources, setShowSources] = useState(false);
  const [showConversation, setShowConversation] = useState(false);
  const isComplete = completed_scenes === total_scenes && total_scenes > 0;

  const handleConversationEdit = async (sceneIndex: number, instruction: string) => {
    try {
      await api.post(`/generate/${requestId}/scenes/${sceneIndex}/edit`, { instruction });
    } catch (err) {
      console.error('Scene edit from conversation failed:', err);
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
    if (evt.artifact_type === 'audio' && evt.scene_index != null) {
      wsAudioMap.set(evt.scene_index, evt.url);
    }
  }

  // Build map of scene_index -> edited image URL from scene_edit artifacts
  const wsEditMap = new Map<number, string>();
  for (const evt of artifacts) {
    if (evt.artifact_type === 'scene_edit' && evt.scene_index != null) {
      wsEditMap.set(evt.scene_index, evt.url);
    }
  }

  // Check for video artifact
  const videoArtifact = artifacts.find((a) => a.artifact_type === 'video');

  return (
    <div className="space-y-6">
      {/* AI disclaimer — satisfies §3.2 Grounding & §7 Overclaiming */}
      {panels.length > 0 && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-md bg-amber-950/30 border border-amber-900/40 text-amber-200/80 text-xs">
          <span>⚠</span>
          <span>
            AI-generated content — not historically accurate. For creative entertainment only.
            <span className="ml-1 italic opacity-70">
              &ldquo;This ain&apos;t a history lesson, kid. It&apos;s a story.&rdquo;
            </span>
          </span>
        </div>
      )}

      {/* Characters summary */}
      {characters.length > 0 && (
        <div>
          <p className="text-sm text-[var(--muted-foreground)] mb-2">Characters</p>
          <div className="flex flex-wrap gap-2">
            {characters.map((char, i) => (
              <Badge key={i} variant="outline">
                {((char as Record<string, unknown>).name as string) ?? `Character ${i + 1}`}
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
          <video controls className="w-full rounded-md" src={videoArtifact.url}>
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

      {/* Filmstrip */}
      <div className="relative">
        {/* Sprocket holes top */}
        <div className="flex gap-3 px-4 py-1 bg-zinc-950 rounded-t-md overflow-hidden">
          {Array.from({ length: 24 }).map((_, i) => (
            <div
              key={i}
              className="w-3 h-2 rounded-sm bg-zinc-800 border border-zinc-700 shrink-0"
            />
          ))}
        </div>

        <div
          className="flex gap-4 overflow-x-auto snap-x snap-mandatory scroll-smooth px-4 py-4 bg-zinc-950"
          style={{ scrollbarWidth: 'thin', scrollbarColor: '#3f3f46 #09090b' }}
        >
          {panels.map((panel, i) => (
            <ScenePanel
              key={i}
              panel={panel}
              requestId={requestId}
              wsImageUrl={
                wsImageMap.has(panel.scene_index)
                  ? `/output/${requestId}/scene_${panel.scene_index}/${wsImageMap.get(panel.scene_index)!.split('/').pop()}`
                  : undefined
              }
              wsAudioUrl={wsAudioMap.get(panel.scene_index)}
              wsEditUrl={wsEditMap.get(panel.scene_index)}
              isCompleted={panel.status === 'completed' || wsImageMap.has(panel.scene_index)}
            />
          ))}
        </div>

        {/* Sprocket holes bottom */}
        <div className="flex gap-3 px-4 py-1 bg-zinc-950 rounded-b-md overflow-hidden">
          {Array.from({ length: 24 }).map((_, i) => (
            <div
              key={i}
              className="w-3 h-2 rounded-sm bg-zinc-800 border border-zinc-700 shrink-0"
            />
          ))}
        </div>
      </div>

      {/* Conversation refinement panel */}
      {isComplete && (
        <div>
          {!showConversation ? (
            <Button variant="outline" onClick={() => setShowConversation(true)} className="w-full">
              Refine with Gemini
            </Button>
          ) : (
            <StoryConversationPanel requestId={requestId} onApplyEdit={handleConversationEdit} />
          )}
        </div>
      )}

      {/* Historical Sources (Google Search grounding) */}
      {grounding_sources && grounding_sources.length > 0 && (
        <div className="border border-[var(--border)] rounded-md overflow-hidden">
          <button
            onClick={() => setShowSources(!showSources)}
            className="w-full flex items-center justify-between px-4 py-2 text-sm text-[var(--muted-foreground)] hover:bg-[var(--muted)]/50 transition-colors"
          >
            <span>Historical Sources ({grounding_sources.length})</span>
            <span className="text-xs">{showSources ? 'Hide' : 'Show'}</span>
          </button>
          {showSources && (
            <div className="px-4 pb-3 space-y-2 border-t border-[var(--border)]">
              {grounding_sources.map((source, i) => (
                <div key={i} className="flex items-start gap-2 py-1">
                  <span className="text-xs text-[var(--muted-foreground)] mt-0.5 shrink-0">
                    [{i + 1}]
                  </span>
                  <div className="min-w-0">
                    <a
                      href={source.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-[var(--primary)] hover:underline break-all"
                    >
                      {source.title || source.url}
                    </a>
                    {source.snippet && (
                      <p className="text-xs text-[var(--muted-foreground)] mt-0.5 line-clamp-2">
                        {source.snippet}
                      </p>
                    )}
                  </div>
                </div>
              ))}
              <p className="text-xs text-[var(--muted-foreground)] opacity-60 italic pt-1">
                Grounded with Google Search
              </p>
            </div>
          )}
        </div>
      )}

      {/* Powered by Gemini badge */}
      <div className="flex justify-end pt-2">
        <span className="text-xs text-[var(--muted-foreground)] opacity-70">
          ✦ Powered by Gemini
        </span>
      </div>
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
  panel: StoryboardData['panels'][0];
  requestId: string;
  wsImageUrl?: string;
  wsAudioUrl?: string;
  wsEditUrl?: string;
  isCompleted: boolean;
}) {
  const [editMode, setEditMode] = useState(false);
  const [editInstruction, setEditInstruction] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [showOriginal, setShowOriginal] = useState(false);

  const isFailed = panel.status === 'failed';
  const imagePath = panel.image_path;
  const displayImageUrl =
    wsEditUrl ??
    wsImageUrl ??
    (isCompleted && imagePath
      ? `/output/${requestId}/scene_${panel.scene_index}/${imagePath.split('/').pop()}`
      : undefined);

  const originalImageUrl =
    wsEditUrl && imagePath
      ? `/output/${requestId}/scene_${panel.scene_index}/${imagePath.split('/').pop()}`
      : undefined;

  const handleEdit = async () => {
    if (!editInstruction.trim()) return;
    setIsEditing(true);
    try {
      await api.post(`/generate/${requestId}/scenes/${panel.scene_index}/edit`, {
        instruction: editInstruction,
      });
      // The scene_edit artifact will arrive via WebSocket
      setEditInstruction('');
      setEditMode(false);
    } catch (err) {
      console.error('Scene edit failed:', err);
    }
    setIsEditing(false);
  };

  return (
    <div className="w-[28rem] min-w-[28rem] snap-center shrink-0">
      <Card
        className={`bg-zinc-900 border-zinc-800 overflow-hidden ${isFailed ? 'border-[var(--destructive)]' : ''}`}
      >
        <CardContent className="p-0">
          {/* Image area — 16:9 with narration overlay */}
          <div className="relative aspect-square bg-zinc-800">
            {isCompleted && displayImageUrl ? (
              <>
                <img
                  src={showOriginal && originalImageUrl ? originalImageUrl : displayImageUrl}
                  alt={`Scene ${panel.scene_index + 1}`}
                  className="absolute inset-0 w-full h-full object-cover"
                />
                {/* Before/after toggle when edit exists */}
                {wsEditUrl && originalImageUrl && (
                  <Button
                    variant="secondary"
                    size="sm"
                    className="absolute top-2 right-2 text-xs h-6 opacity-80 hover:opacity-100"
                    onClick={() => setShowOriginal(!showOriginal)}
                  >
                    {showOriginal ? 'Edited' : 'Original'}
                  </Button>
                )}
              </>
            ) : (
              <div className="absolute inset-0 flex items-center justify-center">
                {isFailed ? (
                  <span className="text-sm text-[var(--destructive)]">Generation failed</span>
                ) : (
                  <div className="animate-pulse text-sm text-zinc-500">Generating image...</div>
                )}
              </div>
            )}

            {/* Narration text overlay — subtitle style */}
            {panel.narration_text && (
              <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/90 via-black/60 to-transparent px-4 pt-8 pb-3">
                <div className="flex items-end gap-2">
                  <p className="font-serif italic text-sm text-zinc-100 leading-relaxed flex-1 drop-shadow-lg">
                    &ldquo;{panel.narration_text}&rdquo;
                  </p>
                  <LiveVoiceNarration text={panel.narration_text} />
                </div>
              </div>
            )}

            {/* Scene number + status badge overlay */}
            <div className="absolute top-2 left-2 flex items-center gap-2">
              <span className="text-xs font-mono font-bold text-white bg-black/60 px-2 py-0.5 rounded">
                {panel.scene_index + 1}
              </span>
              {isCompleted && !editMode && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 w-6 p-0 text-white bg-black/40 hover:bg-black/60"
                  onClick={() => setEditMode(true)}
                  title="Edit this scene"
                >
                  <PencilIcon className="w-3 h-3" />
                </Button>
              )}
            </div>
            <div className="absolute top-2 right-2">
              {!isCompleted && (
                <Badge
                  variant={isFailed ? 'destructive' : 'outline'}
                  className="text-xs bg-black/50 border-zinc-600"
                >
                  {isFailed ? 'Failed' : 'Generating...'}
                </Badge>
              )}
            </div>
          </div>

          {/* Below-image content area */}
          <div className="p-3 space-y-2">
            {/* Scene edit input */}
            {editMode && (
              <div className="space-y-2">
                <div className="flex gap-2 items-center">
                  <Input
                    placeholder="Describe the change..."
                    value={editInstruction}
                    onChange={(e) => setEditInstruction(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleEdit()}
                    disabled={isEditing}
                    className="flex-1 text-sm bg-zinc-800 border-zinc-700"
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
                    {isEditing ? 'Editing...' : 'Apply Edit'}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setEditMode(false);
                      setEditInstruction('');
                    }}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            )}

            {/* Narration audio player */}
            {wsAudioUrl || panel.narration_audio_path ? (
              <audio
                controls
                className="w-full h-8"
                src={wsAudioUrl ?? `/api/export/${requestId}/audio/${panel.scene_index}`}
              >
                Your browser does not support audio playback.
              </audio>
            ) : isCompleted && panel.narration_text ? (
              <div className="text-xs text-zinc-500 animate-pulse">Generating audio...</div>
            ) : null}

            {/* Scene description */}
            <p className="text-xs text-zinc-400 leading-relaxed">{panel.description}</p>

            {/* Metadata badges */}
            <div className="flex flex-wrap gap-1">
              {panel.mood && (
                <Badge variant="outline" className="text-xs border-zinc-700 text-zinc-400">
                  {panel.mood}
                </Badge>
              )}
              {panel.setting && (
                <Badge variant="outline" className="text-xs border-zinc-700 text-zinc-400">
                  {panel.setting}
                </Badge>
              )}
              {panel.characters?.map((name, ci) => (
                <Badge key={ci} variant="secondary" className="text-xs">
                  {name}
                </Badge>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function PencilIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
      <path d="m15 5 4 4" />
    </svg>
  );
}
