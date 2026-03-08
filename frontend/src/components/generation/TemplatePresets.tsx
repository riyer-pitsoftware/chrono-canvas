import { useState, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useHackathonMode } from "@/api/hooks/useConfig";

export interface PresetTemplate {
  id: string;
  title: string;
  description: string;
  prompt: string;
  mood?: string;
  style?: string;
  icon: string;
  category: "story" | "portrait";
}

const STORY_PRESETS: PresetTemplate[] = [
  {
    id: "film-noir-mystery",
    title: "Film Noir Mystery",
    description: "A rain-soaked detective tale with shadowy intrigue",
    prompt:
      "A lone detective walks through rain-slicked streets at midnight, neon signs reflecting off puddles. She approaches a dimly lit jazz club where a mysterious informant waits in the back booth. The saxophone wails as secrets unfold about a missing heiress and a stolen diamond.",
    mood: "dark",
    style: "noir",
    icon: "\uD83D\uDD75\uFE0F",
    category: "story",
  },
  {
    id: "sci-fi-adventure",
    title: "Sci-Fi Adventure",
    description: "An interstellar journey through uncharted space",
    prompt:
      "The starship Meridian drops out of hyperspace near a dying star. Captain Yara spots an ancient alien structure orbiting the star\u2019s corona\u2014impossible architecture that predates the universe itself. The crew must explore the relic before the star goes supernova in six hours.",
    mood: "dramatic",
    style: "cinematic",
    icon: "\uD83D\uDE80",
    category: "story",
  },
  {
    id: "historical-epic",
    title: "Historical Epic",
    description: "A sweeping saga set against real historical events",
    prompt:
      "Constantinople, 1453. As Ottoman cannons breach the ancient walls, a Byzantine scribe races through the burning library to save irreplaceable manuscripts. She entrusts the scrolls to a Venetian merchant\u2019s ship, knowing these words must survive even if the empire falls.",
    mood: "dramatic",
    style: "painterly",
    icon: "\u2694\uFE0F",
    category: "story",
  },
  {
    id: "childrens-fable",
    title: "Children's Fable",
    description: "A whimsical tale with a gentle moral lesson",
    prompt:
      "In a forest where the trees whisper secrets, a small fox with a crooked tail discovers a glowing seed. Every creature says it\u2019s worthless, but the fox plants it anyway. By morning, a tree of silver bells grows, and its music heals the sick animals of the wood.",
    mood: "warm",
    style: "illustration",
    icon: "\uD83E\uDD8A",
    category: "story",
  },
  {
    id: "horror-short",
    title: "Horror Short",
    description: "A chilling tale of creeping dread",
    prompt:
      "The lighthouse keeper notices the beam has started attracting something from the deep. Each night, wet footprints appear one floor higher up the spiral staircase. Tonight they reach the lamp room door\u2014and something is knocking from the other side.",
    mood: "dark",
    style: "noir",
    icon: "\uD83D\uDC7B",
    category: "story",
  },
];

const PORTRAIT_PRESETS: PresetTemplate[] = [
  {
    id: "renaissance-portrait",
    title: "Renaissance Portrait",
    description: "A figure captured in the style of the Italian masters",
    prompt: "Leonardo da Vinci, the Renaissance polymath, seated in his workshop in Florence surrounded by sketches of flying machines and anatomical drawings",
    mood: "warm",
    style: "painterly",
    icon: "\uD83C\uDFA8",
    category: "portrait",
  },
  {
    id: "ancient-egypt",
    title: "Ancient Egypt",
    description: "Pharaohs and queens of the Nile",
    prompt: "Hatshepsut, the female pharaoh of Egypt, standing before her mortuary temple at Deir el-Bahari with the golden desert stretching behind her",
    mood: "dramatic",
    style: "cinematic",
    icon: "\uD83C\uDFDB\uFE0F",
    category: "portrait",
  },
  {
    id: "victorian-era",
    title: "Victorian Era",
    description: "Portraits from the age of industry and empire",
    prompt: "Ada Lovelace, mathematician and writer, posed beside Charles Babbage\u2019s Analytical Engine in a grand Victorian study with gaslight illumination",
    mood: "warm",
    style: "noir",
    icon: "\uD83C\uDFF0",
    category: "portrait",
  },
];

const ONBOARDING_KEY = "chrononoir-presets-dismissed";

interface OnboardingBannerProps {
  mode: "story" | "portrait";
  onDismiss: () => void;
}

function OnboardingBanner({ mode, onDismiss }: OnboardingBannerProps) {
  const storyText =
    "Story Director transforms your narrative into a multi-scene visual storyboard. " +
    "Pick a template below or write your own story \u2014 AI handles the rest.";
  const portraitText =
    "Historical Lens generates historically-accurate portraits of real figures. " +
    "Choose a preset or describe a historical figure to get started.";

  return (
    <div className="relative mb-4 rounded-lg border border-[var(--primary)]/30 bg-[var(--primary)]/5 px-4 py-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          <p className="text-sm font-medium text-[var(--primary)] mb-1">
            {mode === "story" ? "Welcome to Story Director" : "Welcome to Historical Lens"}
          </p>
          <p className="text-sm text-[var(--muted-foreground)]">
            {mode === "story" ? storyText : portraitText}
          </p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="shrink-0 text-[var(--muted-foreground)] hover:text-[var(--foreground)] -mt-1 -mr-2"
          onClick={onDismiss}
        >
          Dismiss
        </Button>
      </div>
    </div>
  );
}

interface TemplatePresetsProps {
  mode: string;
  onSelect: (preset: PresetTemplate) => void;
  disabled?: boolean;
}

export function TemplatePresets({ mode, onSelect, disabled }: TemplatePresetsProps) {
  const hackathonMode = useHackathonMode();
  const isStory = mode === "creative_story";
  const category = isStory ? "story" : "portrait";

  const [showOnboarding, setShowOnboarding] = useState(false);

  useEffect(() => {
    const key = `${ONBOARDING_KEY}-${category}`;
    const dismissed = localStorage.getItem(key);
    if (!dismissed) {
      setShowOnboarding(true);
    }
  }, [category]);

  const dismissOnboarding = () => {
    const key = `${ONBOARDING_KEY}-${category}`;
    localStorage.setItem(key, "true");
    setShowOnboarding(false);
  };

  // In hackathon mode, only show story presets
  let presets: PresetTemplate[];
  if (isStory) {
    presets = STORY_PRESETS;
  } else if (hackathonMode) {
    return null; // Portrait mode hidden in hackathon
  } else {
    presets = PORTRAIT_PRESETS;
  }

  return (
    <div className="mb-4">
      {showOnboarding && (
        <OnboardingBanner mode={category} onDismiss={dismissOnboarding} />
      )}

      <div className="mb-3 flex items-center gap-2">
        <p className="text-sm font-medium text-[var(--muted-foreground)]">
          Quick Start Templates
        </p>
        <Badge variant="secondary" className="text-xs">
          Click to fill
        </Badge>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {presets.map((preset) => (
          <Card
            key={preset.id}
            className={`cursor-pointer transition-all duration-200 border-[var(--border)] hover:border-[var(--primary)] hover:shadow-md hover:shadow-[var(--primary)]/10 group ${
              disabled ? "opacity-50 pointer-events-none" : ""
            }`}
            onClick={() => !disabled && onSelect(preset)}
          >
            <CardContent className="p-3">
              <div className="flex items-start gap-2">
                <span className="text-lg leading-none mt-0.5">{preset.icon}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-[var(--foreground)] group-hover:text-[var(--primary)] transition-colors">
                    {preset.title}
                  </p>
                  <p className="text-xs text-[var(--muted-foreground)] mt-0.5 line-clamp-2">
                    {preset.description}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
