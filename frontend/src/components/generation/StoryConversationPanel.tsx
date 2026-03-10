import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { VoiceInputButton } from '@/components/generation/VoiceInputButton';
import { api } from '@/api/client';

interface SceneSuggestion {
  scene_index: number;
  edit_instruction: string;
  reason: string;
}

interface ChatMessage {
  role: 'user' | 'assistant';
  text: string;
  action?: string;
  suggestions?: SceneSuggestion[];
}

interface StoryConversationPanelProps {
  requestId: string;
  onApplyEdit: (sceneIndex: number, instruction: string) => void;
}

export function StoryConversationPanel({ requestId, onApplyEdit }: StoryConversationPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isSending, setIsSending] = useState(false);

  const sendMessage = async (text: string) => {
    if (!text.trim()) return;
    const userMsg: ChatMessage = { role: 'user', text };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setIsSending(true);

    try {
      const result = await api.post<{
        action: string;
        message: string;
        scene_suggestions: SceneSuggestion[];
      }>(`/conversation/${requestId}/chat`, { message: text });

      const assistantMsg: ChatMessage = {
        role: 'assistant',
        text: result.message,
        action: result.action,
        suggestions: result.scene_suggestions,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', text: `Error: ${err instanceof Error ? err.message : 'Failed'}` },
      ]);
    }
    setIsSending(false);
  };

  return (
    <Card>
      <CardContent className="p-4">
        <p className="text-sm font-medium mb-3">Refine with Gemini</p>

        {/* Chat history */}
        <div className="space-y-3 max-h-80 overflow-y-auto mb-3">
          {messages.length === 0 && (
            <p className="text-sm text-[var(--muted-foreground)]">
              Ask Gemini to refine your storyboard — suggest scene changes, new scenes, or discuss
              the story.
            </p>
          )}
          {messages.map((msg, i) => (
            <div key={i} className={`text-sm ${msg.role === 'user' ? 'text-right' : ''}`}>
              <div
                className={`inline-block rounded-lg px-3 py-2 max-w-[85%] ${
                  msg.role === 'user'
                    ? 'bg-[var(--primary)] text-[var(--primary-foreground)]'
                    : 'bg-[var(--muted)]'
                }`}
              >
                {msg.text}
              </div>

              {/* Scene suggestion cards */}
              {msg.suggestions && msg.suggestions.length > 0 && (
                <div className="mt-2 space-y-2">
                  {msg.suggestions.map((s, si) => (
                    <div
                      key={si}
                      className="border border-[var(--border)] rounded-md p-2 text-left"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <Badge variant="outline" className="text-xs">
                          Scene {s.scene_index + 1}
                        </Badge>
                        <Button
                          size="sm"
                          variant="secondary"
                          className="h-6 text-xs"
                          onClick={() => onApplyEdit(s.scene_index, s.edit_instruction)}
                        >
                          Apply
                        </Button>
                      </div>
                      <p className="text-xs">{s.edit_instruction}</p>
                      <p className="text-xs text-[var(--muted-foreground)]">{s.reason}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
          {isSending && (
            <div className="text-sm">
              <div className="inline-block bg-[var(--muted)] rounded-lg px-3 py-2">
                <span className="animate-pulse">Thinking...</span>
              </div>
            </div>
          )}
        </div>

        {/* Input */}
        <div className="flex gap-2 items-center">
          <Input
            placeholder="Suggest a change..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && sendMessage(input)}
            disabled={isSending}
            className="flex-1 text-sm"
          />
          <VoiceInputButton onTranscript={(text) => sendMessage(text)} disabled={isSending} />
          <Button
            size="sm"
            onClick={() => sendMessage(input)}
            disabled={isSending || !input.trim()}
          >
            Send
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
