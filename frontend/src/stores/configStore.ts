import { create } from "zustand";
import { persist } from "zustand/middleware";

export type Mode = "gcp" | "local";

export interface ConfigState {
  mode: Mode;

  // LLM
  llmProvider: string;
  llmModel: string;
  strictGemini: boolean;
  agentRouting: Record<string, string>;

  // Image
  imageProvider: string;

  // Toggles
  ttsEnabled: boolean;
  facefusionEnabled: boolean;
  validationRetryEnabled: boolean;
  researchCacheEnabled: boolean;

  // Actions
  setMode: (mode: Mode) => void;
  setLlmProvider: (provider: string) => void;
  setLlmModel: (model: string) => void;
  setStrictGemini: (v: boolean) => void;
  setAgentRouting: (routing: Record<string, string>) => void;
  setImageProvider: (provider: string) => void;
  setTtsEnabled: (v: boolean) => void;
  setFacefusionEnabled: (v: boolean) => void;
  setValidationRetryEnabled: (v: boolean) => void;
  setResearchCacheEnabled: (v: boolean) => void;

  /** Build the config payload for the generation API */
  toPayload: () => Record<string, unknown>;
}

const GCP_DEFAULTS = {
  llmProvider: "gemini",
  llmModel: "gemini-2.5-flash",
  imageProvider: "imagen",
  strictGemini: true,
  ttsEnabled: true,
  facefusionEnabled: false,
};

const LOCAL_DEFAULTS = {
  llmProvider: "ollama",
  llmModel: "llama3.1:8b",
  imageProvider: "comfyui",
  strictGemini: false,
  ttsEnabled: false,
  facefusionEnabled: false,
};

export const useConfigStore = create<ConfigState>()(
  persist(
    (set, get) => ({
      mode: "gcp",
      llmProvider: "gemini",
      llmModel: "gemini-2.5-flash",
      strictGemini: true,
      agentRouting: {},
      imageProvider: "imagen",
      ttsEnabled: true,
      facefusionEnabled: false,
      validationRetryEnabled: true,
      researchCacheEnabled: true,

      setMode: (mode) => {
        const defaults = mode === "gcp" ? GCP_DEFAULTS : LOCAL_DEFAULTS;
        set({ mode, ...defaults });
      },
      setLlmProvider: (llmProvider) => set({ llmProvider }),
      setLlmModel: (llmModel) => set({ llmModel }),
      setStrictGemini: (strictGemini) => set({ strictGemini }),
      setAgentRouting: (agentRouting) => set({ agentRouting }),
      setImageProvider: (imageProvider) => set({ imageProvider }),
      setTtsEnabled: (ttsEnabled) => set({ ttsEnabled }),
      setFacefusionEnabled: (facefusionEnabled) => set({ facefusionEnabled }),
      setValidationRetryEnabled: (validationRetryEnabled) =>
        set({ validationRetryEnabled }),
      setResearchCacheEnabled: (researchCacheEnabled) =>
        set({ researchCacheEnabled }),

      toPayload: () => {
        const s = get();
        return {
          mode: s.mode,
          llm: {
            provider: s.llmProvider,
            model: s.llmModel,
            strict_gemini: s.strictGemini,
            agent_routing: s.agentRouting,
          },
          image: { provider: s.imageProvider },
          voice: { tts_enabled: s.ttsEnabled },
          post: {
            facefusion: s.facefusionEnabled,
            validation_retry: s.validationRetryEnabled,
          },
          search: { research_cache: s.researchCacheEnabled },
        };
      },
    }),
    { name: "chrono-config-hud" },
  ),
);
