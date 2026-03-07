import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import {
  useDeploymentMode,
  useServiceAvailability,
  validateConfig,
} from "@/api/hooks/useConfig";
import { useConfigStore, type Mode } from "@/stores/configStore";

const LLM_PROVIDERS = [
  { id: "gemini", label: "Gemini", cloud: true },
  { id: "claude", label: "Claude", cloud: true },
  { id: "openai", label: "OpenAI", cloud: true },
  { id: "ollama", label: "Ollama", cloud: false },
];

const LLM_MODELS: Record<string, string[]> = {
  gemini: ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"],
  claude: ["claude-sonnet-4-5-20250929", "claude-haiku-4-5-20251001"],
  openai: ["gpt-4o", "gpt-4o-mini"],
  ollama: ["llama3.1:8b"],
};

const IMAGE_PROVIDERS = [
  { id: "imagen", label: "Imagen", cloud: true },
  { id: "comfyui", label: "ComfyUI", cloud: false },
  { id: "stable_diffusion", label: "Stable Diffusion", cloud: false },
  { id: "mock", label: "Mock", cloud: false },
];

function StatusLed({ available }: { available: boolean | undefined }) {
  return (
    <span
      className={cn(
        "inline-block h-2 w-2 rounded-full",
        available === undefined
          ? "bg-gray-500"
          : available
            ? "bg-green-400 shadow-[0_0_4px_rgba(74,222,128,0.6)]"
            : "bg-red-400",
      )}
    />
  );
}

function ProviderButton({
  label,
  selected,
  available,
  disabled,
  onClick,
}: {
  label: string;
  selected: boolean;
  available: boolean | undefined;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "flex items-center gap-1.5 rounded px-2 py-1 text-xs font-mono transition-all",
        "border",
        selected
          ? "border-amber-500/60 bg-amber-500/20 text-amber-200 shadow-[0_0_8px_rgba(245,158,11,0.2)]"
          : "border-zinc-700 bg-zinc-900/50 text-zinc-400 hover:border-zinc-600 hover:text-zinc-300",
        disabled && "opacity-30 cursor-not-allowed",
      )}
    >
      <StatusLed available={available} />
      {label}
    </button>
  );
}

function Channel({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-zinc-800 bg-zinc-950/80 p-3 min-w-[140px]">
      <div className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">
        {title}
      </div>
      {children}
    </div>
  );
}

export function ConfigHUD({ className }: { className?: string }) {
  const services = useServiceAvailability();
  const deploymentMode = useDeploymentMode();
  const store = useConfigStore();
  const [errors, setErrors] = useState<
    Array<{ channel: string; error: string }>
  >([]);
  const [validating, setValidating] = useState(false);

  // Lock mode to match server deployment_mode (gcp or local locks the toggle)
  const modeLocked = deploymentMode !== "hybrid";
  useEffect(() => {
    if (modeLocked && store.mode !== deploymentMode) {
      store.setMode(deploymentMode as Mode);
    }
  }, [deploymentMode, modeLocked, store]);

  const isGcp = store.mode === "gcp";

  const handleValidate = async () => {
    setValidating(true);
    try {
      const result = await validateConfig(store.toPayload());
      setErrors(result.errors);
    } catch {
      setErrors([{ channel: "system", error: "Validation request failed" }]);
    } finally {
      setValidating(false);
    }
  };

  return (
    <div
      className={cn(
        "rounded-xl border border-zinc-800 bg-zinc-950 p-4 shadow-2xl",
        className,
      )}
    >
      {/* Header: mode toggle */}
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-xs font-bold uppercase tracking-widest text-zinc-400">
          Signal Chain
        </h3>
        {modeLocked ? (
          <span className="rounded bg-amber-500/20 px-3 py-1 text-xs font-mono uppercase text-amber-300">
            {store.mode}
          </span>
        ) : (
          <div className="flex gap-1 rounded-md border border-zinc-800 bg-zinc-900 p-0.5">
            {(["gcp", "local"] as Mode[]).map((m) => (
              <button
                key={m}
                onClick={() => store.setMode(m)}
                className={cn(
                  "rounded px-3 py-1 text-xs font-mono uppercase transition-all",
                  store.mode === m
                    ? "bg-amber-500/20 text-amber-300 shadow-inner"
                    : "text-zinc-500 hover:text-zinc-300",
                )}
              >
                {m}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Channels */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
        {/* LLM Engine */}
        <Channel title="LLM Engine">
          <div className="flex flex-col gap-1">
            {LLM_PROVIDERS.map((p) => (
              <ProviderButton
                key={p.id}
                label={p.label}
                selected={store.llmProvider === p.id}
                available={services?.llm[p.id]}
                disabled={isGcp && !p.cloud}
                onClick={() => {
                  store.setLlmProvider(p.id);
                  const models = LLM_MODELS[p.id];
                  if (models?.[0]) store.setLlmModel(models[0]);
                }}
              />
            ))}
          </div>
          <select
            value={store.llmModel}
            onChange={(e) => store.setLlmModel(e.target.value)}
            className="mt-1 rounded border border-zinc-800 bg-zinc-900 px-1.5 py-0.5 text-[10px] text-zinc-300"
          >
            {(LLM_MODELS[store.llmProvider] || []).map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </Channel>

        {/* Image Gen */}
        <Channel title="Image Gen">
          <div className="flex flex-col gap-1">
            {IMAGE_PROVIDERS.map((p) => (
              <ProviderButton
                key={p.id}
                label={p.label}
                selected={store.imageProvider === p.id}
                available={services?.image[p.id]}
                disabled={isGcp && !p.cloud}
                onClick={() => store.setImageProvider(p.id)}
              />
            ))}
          </div>
        </Channel>

        {/* Search & Ref */}
        <Channel title="Search & Ref">
          <div className="flex flex-col gap-1.5 text-xs text-zinc-400">
            <div className="flex items-center gap-1.5">
              <StatusLed available={services?.search.serpapi} />
              <span>SerpAPI</span>
            </div>
            <div className="flex items-center gap-1.5">
              <StatusLed available={services?.search.pexels} />
              <span>Pexels</span>
            </div>
            <div className="flex items-center gap-1.5">
              <StatusLed available={services?.search.unsplash} />
              <span>Unsplash</span>
            </div>
          </div>
          <label className="mt-2 flex items-center gap-1.5 text-[10px] text-zinc-500">
            <input
              type="checkbox"
              checked={store.researchCacheEnabled}
              onChange={(e) => store.setResearchCacheEnabled(e.target.checked)}
              className="accent-amber-500"
            />
            Research Cache
          </label>
        </Channel>

        {/* Voice & TTS */}
        <Channel title="Voice & TTS">
          <ProviderButton
            label="Gemini TTS"
            selected={store.ttsEnabled}
            available={services?.tts}
            disabled={!isGcp && !services?.tts}
            onClick={() => store.setTtsEnabled(true)}
          />
          <ProviderButton
            label="Off"
            selected={!store.ttsEnabled}
            available={true}
            onClick={() => store.setTtsEnabled(false)}
          />
        </Channel>

        {/* Vision & Multimodal */}
        <Channel title="Vision & MML">
          <div className="flex flex-col gap-1.5 text-xs text-zinc-400">
            <div className="flex items-center gap-1.5">
              <StatusLed available={services?.llm.gemini} />
              <span>Gemini MML</span>
            </div>
          </div>
          <span className="mt-1 text-[9px] text-zinc-600">
            Uses LLM provider
          </span>
        </Channel>

        {/* Compositing & Post */}
        <Channel title="Compositing">
          <ProviderButton
            label="FaceFusion"
            selected={store.facefusionEnabled}
            available={services?.facefusion}
            disabled={isGcp}
            onClick={() => store.setFacefusionEnabled(!store.facefusionEnabled)}
          />
          <ProviderButton
            label="Off"
            selected={!store.facefusionEnabled}
            available={true}
            onClick={() => store.setFacefusionEnabled(false)}
          />
          <label className="mt-1 flex items-center gap-1.5 text-[10px] text-zinc-500">
            <input
              type="checkbox"
              checked={store.validationRetryEnabled}
              onChange={(e) =>
                store.setValidationRetryEnabled(e.target.checked)
              }
              className="accent-amber-500"
            />
            Validation Retry
          </label>
        </Channel>
      </div>

      {/* Validation / errors */}
      <div className="mt-3 flex items-center gap-3">
        <button
          onClick={handleValidate}
          disabled={validating}
          className={cn(
            "rounded border border-zinc-700 px-3 py-1 text-xs font-mono text-zinc-400 transition-all",
            "hover:border-amber-600 hover:text-amber-300",
            validating && "animate-pulse",
          )}
        >
          {validating ? "Checking..." : "Validate Config"}
        </button>
        {errors.length > 0 && (
          <div className="flex flex-col gap-0.5">
            {errors.map((e, i) => (
              <span key={i} className="text-[10px] text-red-400">
                [{e.channel}] {e.error}
              </span>
            ))}
          </div>
        )}
        {errors.length === 0 && !validating && (
          <span className="text-[10px] text-zinc-600">
            Config saved to localStorage
          </span>
        )}
      </div>
    </div>
  );
}
