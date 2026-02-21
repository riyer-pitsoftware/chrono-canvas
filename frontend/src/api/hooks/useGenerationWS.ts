import { useEffect, useRef, useState } from "react";

export interface ImageProgress {
  step: number;
  total: number;
}

/**
 * Connect to the generation WebSocket and surface real-time progress.
 *
 * - Returns `imageProgress` with step/total during the image_generation phase.
 * - Returns `streamingText` + `streamingAgent` for live LLM token output.
 * - Automatically disconnects when the generation completes or fails.
 */
export function useGenerationWS(requestId: string | null, enabled: boolean) {
  const [imageProgress, setImageProgress] = useState<ImageProgress | null>(null);
  const [streamingText, setStreamingText] = useState<string>("");
  const [streamingAgent, setStreamingAgent] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!requestId || !enabled) return;

    setStreamingText("");
    setStreamingAgent(null);

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(
      `${protocol}//${window.location.host}/ws/generation/${requestId}`,
    );
    wsRef.current = ws;

    ws.onmessage = (event) => {
      let data: Record<string, unknown>;
      try {
        data = JSON.parse(event.data as string);
      } catch {
        return;
      }

      if (data.type === "llm_token") {
        const agent = data.agent as string;
        const token = data.token as string;
        setStreamingAgent(agent);
        setStreamingText((prev) => prev + token);
      } else if (data.type === "llm_stream_end") {
        // Keep text visible until the next agent starts
        setStreamingAgent(null);
      } else if (data.type === "image_progress") {
        setImageProgress({
          step: data.step as number,
          total: data.total as number,
        });
      } else {
        if (data.agent && data.agent !== "image_generation") {
          setImageProgress(null);
        }
        // New agent starting — clear previous streaming text
        if (data.agent) {
          setStreamingText("");
          setStreamingAgent(null);
        }
        if (data.status === "completed" || data.status === "failed") {
          setImageProgress(null);
          setStreamingText("");
          setStreamingAgent(null);
          ws.close();
        }
      }
    };

    ws.onerror = () => {
      // WS unavailable (e.g. Redis not running) — silently ignore
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [requestId, enabled]);

  return { imageProgress, streamingText, streamingAgent };
}
