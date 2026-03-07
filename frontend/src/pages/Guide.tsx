import { useEffect, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  ArrowRight,
  LayoutDashboard,
  Users,
  Image,
  Shield,
  Download,
  Settings,
  Terminal,
  Cpu,
  BookOpen,
  Sparkles,
  Activity,
  ChevronDown,
  ChevronRight,
  Lightbulb,
} from "lucide-react";

const tocItems = [
  { id: "getting-started", label: "Getting Started" },
  { id: "pipeline", label: "The Pipeline" },
  { id: "agent-deep-dive", label: "Agent Deep Dive" },
  { id: "using-ui", label: "Using the UI" },
  { id: "configuration", label: "Configuration" },
  { id: "cli-reference", label: "CLI Reference" },
];

const pipelineSteps = [
  { name: "Orchestrator", provider: "Ollama", description: "Receives request and creates an execution plan" },
  { name: "Extraction", provider: "Ollama", description: "Parses text into structured figure data" },
  { name: "Research", provider: "Claude", description: "Enriches data with historical context and facts" },
  { name: "Face Search", provider: "SerpAPI", description: "Fetches reference portrait images from the web" },
  { name: "Prompt Gen", provider: "Claude", description: "Creates period-informed image generation prompts" },
  { name: "Image Gen", provider: "—", description: "Produces portrait via Stable Diffusion or ComfyUI" },
  { name: "Validation", provider: "Ollama", description: "Scores historical plausibility (0–100, LLM-judged) and flags issues" },
  { name: "Facial Compositing", provider: "FaceFusion", description: "Blends uploaded face into the generated portrait" },
  { name: "Export", provider: "—", description: "Packages portrait as PNG with JSON metadata" },
];

const uiPages = [
  {
    name: "Dashboard",
    icon: LayoutDashboard,
    items: [
      "View recent generations and their status",
      "See total figures, generation count, and LLM costs",
      "Quick access to start a new generation",
    ],
  },
  {
    name: "Figures",
    icon: Users,
    items: [
      "Browse and search 100 pre-loaded historical figures",
      "Filter by time period, nationality, or occupation",
      "Add custom figures with text descriptions",
    ],
  },
  {
    name: "Generate",
    icon: Image,
    items: [
      "Enter a text description or select an existing figure",
      "Watch real-time progress through each pipeline stage",
      "Preview the generated portrait when complete",
    ],
  },
  {
    name: "Validate",
    icon: Shield,
    items: [
      "Review heuristic plausibility scores (0–100, LLM-judged)",
      "See flagged anachronisms and validation notes",
      "Figures scoring 70+ pass automatically",
    ],
  },
  {
    name: "Export",
    icon: Download,
    items: [
      "Download portraits as PNG files",
      "Get JSON metadata (figure data, prompt, score)",
      "Access all completed generations",
    ],
  },
  {
    name: "Admin",
    icon: Settings,
    items: [
      "Monitor agent health and status",
      "View LLM provider availability",
      "Track generation costs and usage metrics",
    ],
  },
];

const cliCommands = [
  { command: "chronocanvas add figure", description: "Add a historical figure to the database" },
  { command: "chronocanvas generate", description: "Generate a portrait from a text description" },
  { command: "chronocanvas batch", description: "Run batch generation from a JSON file" },
  { command: "chronocanvas status", description: "Check the status of a generation request" },
  { command: "chronocanvas download", description: "Download the generated image" },
  { command: "chronocanvas list figures", description: "List historical figures with search/filter" },
  { command: "chronocanvas list generations", description: "List generation requests" },
  { command: "chronocanvas validate", description: "Show validation results for a generation" },
  { command: "chronocanvas agents list", description: "List all available agents" },
  { command: "chronocanvas agents llm-status", description: "Check LLM provider availability" },
  { command: "chronocanvas agents costs", description: "Show LLM cost summary" },
];

const routingTable = [
  { task: "Extraction", provider: "Ollama", reason: "Fast, free, sufficient for structured parsing" },
  { task: "Research", provider: "Claude", reason: "Best reasoning for historical enrichment" },
  { task: "Prompt Generation", provider: "Claude", reason: "Strong creative + accurate prompt crafting" },
  { task: "Validation", provider: "Ollama", reason: "Cost-effective for scoring checks" },
  { task: "Orchestration", provider: "Ollama", reason: "Lightweight coordination logic" },
  { task: "General", provider: "Ollama", reason: "Default fallback, no API cost" },
];

interface AgentGuideEntry {
  id: string;
  label: string;
  provider: string;
  why: string;
  promptTemplate: string | null;
  promptNote?: string;
  tips: { title: string; detail: string }[];
}

const PIPELINE_GUIDE: AgentGuideEntry[] = [
  {
    id: "extraction",
    label: "Extraction",
    provider: "Ollama",
    why: "The user's input is free-form text—\"Cleopatra, Queen of Egypt\" could mean many things. This agent parses that into structured fields (name, time period, region, occupation) that every downstream agent can reliably use. Without it, each agent would have to re-interpret the raw input and risk disagreeing with each other.",
    promptTemplate: `Extract historical figure information from the following text.
Return a JSON object with these fields:
- figure_name: string (full name of the historical figure)
- time_period: string (era or century)
- region: string (geographic region/country)
- occupation: string (primary role or title)
- attributes: object (any additional attributes mentioned)

Text: {input_text}

Respond with valid JSON only.`,
    tips: [
      {
        title: "Add a context field",
        detail: "Append `- context: string (notable qualifier, e.g. \"early career\" or \"in exile\")` to capture life-phase nuance that affects clothing and setting.",
      },
      {
        title: "Lower temperature for reliability",
        detail: "This call uses temperature=0.3. Try 0.1 for more deterministic JSON output, especially if you see occasional parse failures.",
      },
    ],
  },
  {
    id: "research",
    label: "Research",
    provider: "Claude",
    why: "Knowing who someone was isn't enough to paint them. This agent adds the rich sensory detail—what fabrics they wore, their known physical features, the art style of their era—that turns a name into a portrait prompt. It's why Claude is used here: historical enrichment requires real reasoning, not just retrieval.",
    promptTemplate: `You are a historical research expert. Research the following historical figure
for the purpose of generating an accurate portrait.

Figure: {figure_name}
Time Period: {time_period}
Region: {region}
Occupation: {occupation}

Provide detailed information as JSON with these fields:
- historical_context: string (2-3 sentences about their life and significance)
- clothing_details: string (accurate period clothing, fabrics, colors)
- physical_description: string (known physical features, build, hair, complexion)
- art_style_reference: string (art style of their era, e.g. "Renaissance oil painting")
- sources: list of strings (reference descriptions)

Respond with valid JSON only.`,
    tips: [
      {
        title: "Add notable_accessories",
        detail: "Add `- notable_accessories: string` to capture crowns, weapons, or jewelry that define the figure's iconography—these often matter more than clothing.",
      },
      {
        title: "Request a color palette",
        detail: "Add `- color_palette: string (3-4 hex codes or named colors typical of their portrait tradition)` for even more precise prompt grounding.",
      },
    ],
  },
  {
    id: "face_search",
    label: "Face Search",
    provider: "SerpAPI",
    why: "Stable Diffusion alone can't know what a historical figure looked like. By fetching real portrait images from the web, this agent provides reference material that can anchor the generation. It also supplies the pool of face images used by the Facial Compositing step if the user didn't upload their own.",
    promptTemplate: `{figure_name} historical portrait photograph`,
    promptNote: "This is a search query template, not an LLM prompt. Results are fetched from Google Images via SerpAPI.",
    tips: [
      {
        title: "Bias toward a specific medium",
        detail: "Append \" oil painting\" or \" engraving\" to the query to prefer a particular visual style in the reference images.",
      },
      {
        title: "Prefer public domain",
        detail: "Appending \" site:commons.wikimedia.org\" biases results toward freely licensed images, useful if you're building on top of the reference.",
      },
    ],
  },
  {
    id: "prompt_generation",
    label: "Prompt Generation",
    provider: "Claude",
    why: "Stable Diffusion XL speaks a very specific dialect: comma-separated tags with emphasis weights like `(sharp facial features:1.2)`. This agent translates the research text—which is rich but prose-form—into that syntax. The system prompt teaches Claude the SDXL grammar so you don't have to.",
    promptTemplate: `You are an expert at crafting Stable Diffusion XL prompts for photorealistic historical portraits.

Based on the following research, create a detailed SDXL prompt for generating a highly realistic portrait photograph.

Figure: {figure_name}
Historical Context: {historical_context}
Clothing: {clothing_details}
Physical Description: {physical_description}
Art Style: {art_style_reference}

Requirements:
1. Use comma-separated tag style (SDXL responds best to this format)
2. Start with: "photorealistic portrait, (masterpiece:1.2), (best quality:1.2), (ultra detailed face:1.3)"
3. Describe facial features precisely: skin texture, facial bone structure, eye color and shape
4. Include period-appropriate clothing, hairstyle, and accessories with specific detail
5. Add lighting tags: Rembrandt lighting, soft key light, (catchlights in eyes:1.1)
6. Add camera tags: 85mm lens, shallow depth of field, sharp focus on eyes, bokeh background
7. Add quality tags: RAW photo, 8K, DSLR, (detailed skin texture:1.2), film grain
8. Use emphasis syntax for important elements: (sharp facial features:1.2), (realistic skin:1.3)
9. Keep it under 200 words — SDXL works better with concise, weighted prompts

Return ONLY the prompt text, no explanations.`,
    tips: [
      {
        title: "Shift to a painterly style",
        detail: "Add `(oil painting texture:1.2), impasto brushwork` to the requirements list to make the output look like a period painting rather than a photograph.",
      },
      {
        title: "Boost face sharpness",
        detail: "Increase the weight on `(ultra detailed face:1.3)` to `(ultra detailed face:1.5)` — but watch for over-sharpening artifacts at very high weights.",
      },
    ],
  },
  {
    id: "image_generation",
    label: "Image Generation",
    provider: "Stable Diffusion / ComfyUI",
    why: "The actual diffusion step. No LLM is involved here—the prompt from the previous agent is sent directly to the image provider. This is intentionally the only non-LLM step: image quality is the provider's job, and keeping it separate makes it easy to swap providers.",
    promptTemplate: null,
    promptNote: "No LLM prompt. The output of Prompt Generation is sent directly to the configured image provider (Stable Diffusion API or ComfyUI). Configure IMAGE_PROVIDER in .env.",
    tips: [
      {
        title: "Use a real provider",
        detail: "Set `IMAGE_PROVIDER=stable_diffusion` and `SD_API_URL=http://localhost:7860` in .env. The mock provider returns placeholder images—useful for testing the pipeline without a GPU.",
      },
      {
        title: "Increase generation steps",
        detail: "Edit `generation_params.steps` in the image generation node to increase from the default 20 to 30–40 for higher quality, at the cost of generation time.",
      },
    ],
  },
  {
    id: "validation",
    label: "Validation",
    provider: "Ollama",
    why: "Image generation is non-deterministic—the model might produce something anachronistic or wrong. Validation catches this before the user sees it. Scores below 70 trigger automatic regeneration (up to 2 retries) with a corrected prompt. Ollama is used here because scoring doesn't need frontier reasoning—it needs consistency and cost efficiency.",
    promptTemplate: `You are a historical plausibility evaluator. Assess the following image generation
prompt for historical plausibility. Note: these are heuristic, LLM-judged scores — not ground-truth fact-checking.

Figure: {figure_name}
Time Period: {time_period}
Region: {region}
Image Prompt: {image_prompt}

Score each category 0-100 and provide details:
1. clothing_plausibility: Are the clothes period-appropriate?
2. cultural_plausibility: Are cultural elements plausible for the setting?
3. temporal_plausibility: Are there anachronistic elements?
4. artistic_plausibility: Does the art style match the period?

Return JSON with:
- results: list of objects with (category, rule_name, passed, score, details, reasoning)
- overall_score: float 0-100
- overall_reasoning: 2-4 sentences summarizing the overall assessment
- passed: boolean (true if overall_score >= 70)

Respond with valid JSON only.`,
    tips: [
      {
        title: "Adjust the pass threshold",
        detail: "The 70-point threshold is set in `validation_node`. Lower it to 50 for more lenient acceptance, or raise it to 85 for stricter plausibility filtering. Remember: these are LLM-judged heuristic scores, not objective fact-checking.",
      },
      {
        title: "Add a costume_era_match rule",
        detail: "Add `5. costume_era_match: Does the overall costume match a single coherent time period?` to catch mixed-era outfits that slip past the individual category checks.",
      },
    ],
  },
  {
    id: "facial_compositing",
    label: "Facial Compositing",
    provider: "FaceFusion",
    why: "If the user uploads a reference face, this step blends their likeness into the generated portrait using FaceFusion. The entire step is skipped if no face was uploaded, making it an optional layer of personalization on top of the core pipeline.",
    promptTemplate: null,
    promptNote: "No LLM prompt. FaceFusion performs face detection and blending purely with computer vision. Configure FACEFUSION_API_URL in .env.",
    tips: [
      {
        title: "Use a front-facing reference photo",
        detail: "Facial compositing quality drops significantly with profile or angled shots. Ask users to upload a well-lit, front-facing portrait for best results.",
      },
      {
        title: "Match pose in the generated portrait",
        detail: "Add `front-facing portrait, looking directly at viewer` to the prompt generation requirements so the generated pose is compatible with facial compositing.",
      },
    ],
  },
  {
    id: "export",
    label: "Export",
    provider: "—",
    why: "Packages the final result—image file, metadata JSON (figure data, prompt used, validation score, LLM costs)—so it can be downloaded or referenced later. This is the only step that writes to permanent storage outside the generation's working directory.",
    promptTemplate: null,
    promptNote: "No LLM prompt. Pure file I/O: copies the output image to the export path and writes a JSON sidecar with generation metadata.",
    tips: [
      {
        title: "Switch to JPEG for smaller files",
        detail: "Set `EXPORT_FORMAT=jpeg` in .env to get significantly smaller files. PNG is the default for lossless archival quality.",
      },
      {
        title: "Read the JSON sidecar",
        detail: "Every export writes a `.json` file alongside the image with the full prompt, validation scores, and LLM costs—useful for reproducing or comparing generations.",
      },
    ],
  },
];

interface GuideProps {
  section?: string;
}

export function Guide({ section }: GuideProps) {
  const [activeSection, setActiveSection] = useState(tocItems[0].id);
  const [expandedAgents, setExpandedAgents] = useState<Record<string, boolean>>(() => {
    if (section) return { [section]: true };
    return {};
  });
  const sectionRefs = useRef<Record<string, HTMLElement | null>>({});
  const agentRefs = useRef<Record<string, HTMLElement | null>>({});

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveSection(entry.target.id);
          }
        }
      },
      { rootMargin: "-20% 0px -60% 0px" },
    );

    for (const item of tocItems) {
      const el = sectionRefs.current[item.id];
      if (el) observer.observe(el);
    }

    return () => observer.disconnect();
  }, []);

  // Deep-link: scroll to agent section when section prop changes
  useEffect(() => {
    if (!section) return;
    setExpandedAgents((prev) => ({ ...prev, [section]: true }));
    // Small delay to let expand animation settle
    const timer = setTimeout(() => {
      const el = agentRefs.current[section];
      if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 80);
    return () => clearTimeout(timer);
  }, [section]);

  function scrollTo(id: string) {
    const el = sectionRefs.current[id];
    if (el) el.scrollIntoView({ behavior: "smooth" });
  }

  function toggleAgent(id: string) {
    setExpandedAgents((prev) => ({ ...prev, [id]: !prev[id] }));
  }

  return (
    <div className="flex gap-8">
      {/* Sticky TOC sidebar */}
      <nav className="hidden lg:block w-48 shrink-0">
        <div className="sticky top-6 space-y-1">
          <p className="text-sm font-semibold mb-3 text-[var(--muted-foreground)]">On this page</p>
          {tocItems.map((item) => (
            <button
              key={item.id}
              onClick={() => scrollTo(item.id)}
              className={`block w-full text-left text-sm px-3 py-1.5 rounded-md transition-colors ${
                activeSection === item.id
                  ? "bg-[var(--accent)] text-[var(--accent-foreground)] font-medium"
                  : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </nav>

      {/* Content */}
      <div className="flex-1 min-w-0 space-y-12 pb-24">
        <div>
          <h2 className="text-3xl font-bold mb-2 flex items-center gap-2">
            <BookOpen className="w-7 h-7" />
            Guide
          </h2>
          <p className="text-[var(--muted-foreground)]">
            Everything you need to know about using ChronoCanvas.
          </p>
        </div>

        {/* Getting Started */}
        <section id="getting-started" ref={(el) => { sectionRefs.current["getting-started"] = el; }}>
          <h3 className="text-xl font-semibold mb-4">Getting Started</h3>
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Sparkles className="w-5 h-5" />
                What is ChronoCanvas?
              </CardTitle>
              <CardDescription>
                ChronoCanvas is an open-source toolkit that generates historically informed portraits using a 9-node AI pipeline.
                It's built for educators, historians, and content creators who need period-plausible character depictions.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm font-medium mb-3">Quick start:</p>
              <ol className="list-decimal list-inside space-y-2 text-sm text-[var(--muted-foreground)]">
                <li>Copy <code className="px-1 py-0.5 rounded bg-[var(--secondary)] text-[var(--secondary-foreground)] text-xs">.env.example</code> to <code className="px-1 py-0.5 rounded bg-[var(--secondary)] text-[var(--secondary-foreground)] text-xs">.env</code> and configure your API keys</li>
                <li>Run <code className="px-1 py-0.5 rounded bg-[var(--secondary)] text-[var(--secondary-foreground)] text-xs">make dev</code> to start all services via Docker Compose</li>
                <li>Open <code className="px-1 py-0.5 rounded bg-[var(--secondary)] text-[var(--secondary-foreground)] text-xs">http://localhost:3000</code> in your browser</li>
                <li>Go to <strong>Generate</strong> and enter a historical figure description to create your first portrait</li>
              </ol>
            </CardContent>
          </Card>
        </section>

        {/* Pipeline */}
        <section id="pipeline" ref={(el) => { sectionRefs.current["pipeline"] = el; }}>
          <h3 className="text-xl font-semibold mb-4">The Pipeline</h3>
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">9-Agent Flow</CardTitle>
              <CardDescription>
                Each generation passes through nine autonomous agents in sequence.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Badge flow diagram */}
              <div className="flex flex-wrap items-center gap-2">
                {pipelineSteps.map((step, i) => (
                  <span key={step.name} className="flex items-center gap-2">
                    <Badge variant="secondary">{step.name}</Badge>
                    {i < pipelineSteps.length - 1 && (
                      <ArrowRight className="w-4 h-4 text-[var(--muted-foreground)]" />
                    )}
                  </span>
                ))}
              </div>

              {/* Agent details */}
              <div className="space-y-3 mt-4">
                {pipelineSteps.map((step) => (
                  <div key={step.name} className="flex items-start gap-3 text-sm">
                    <Badge variant="secondary" className="shrink-0 mt-0.5">{step.name}</Badge>
                    <span className="text-[var(--muted-foreground)]">{step.description}</span>
                    <Badge variant="outline" className="shrink-0 ml-auto">{step.provider}</Badge>
                  </div>
                ))}
              </div>

              {/* Regeneration callout */}
              <div className="mt-4 p-3 rounded-md border border-yellow-200 bg-yellow-50 dark:border-yellow-900 dark:bg-yellow-950">
                <p className="text-sm flex items-center gap-2">
                  <Badge variant="warning">Retry</Badge>
                  If validation scores below 70, the pipeline regenerates with a corrected prompt (max 2 retries).
                </p>
              </div>
            </CardContent>
          </Card>
        </section>

        {/* Agent Deep Dive */}
        <section id="agent-deep-dive" ref={(el) => { sectionRefs.current["agent-deep-dive"] = el; }}>
          <h3 className="text-xl font-semibold mb-2">Agent Deep Dive</h3>
          <p className="text-sm text-[var(--muted-foreground)] mb-4">
            Why each agent exists, the prompt it uses, and how to change its behavior.
          </p>
          <div className="space-y-2">
            {PIPELINE_GUIDE.map((agent) => {
              const isOpen = expandedAgents[agent.id] ?? false;
              return (
                <div
                  key={agent.id}
                  ref={(el) => { agentRefs.current[agent.id] = el; }}
                  className="border border-[var(--border)] rounded-lg overflow-hidden"
                >
                  <button
                    onClick={() => toggleAgent(agent.id)}
                    className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-[var(--accent)] transition-colors"
                  >
                    {isOpen
                      ? <ChevronDown className="w-4 h-4 shrink-0 text-[var(--muted-foreground)]" />
                      : <ChevronRight className="w-4 h-4 shrink-0 text-[var(--muted-foreground)]" />
                    }
                    <span className="font-medium">{agent.label}</span>
                    <Badge variant="outline" className="text-xs ml-1">{agent.provider}</Badge>
                  </button>

                  {isOpen && (
                    <div className="px-4 pb-5 space-y-5 border-t border-[var(--border)]">
                      {/* Why */}
                      <div className="mt-4">
                        <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted-foreground)] mb-1.5">Why this agent exists</p>
                        <p className="text-sm text-[var(--foreground)] leading-relaxed">{agent.why}</p>
                      </div>

                      {/* Prompt */}
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted-foreground)] mb-1.5">
                          {agent.promptTemplate ? "Prompt template" : "No LLM prompt"}
                        </p>
                        {agent.promptNote && (
                          <p className="text-xs text-[var(--muted-foreground)] mb-2 italic">{agent.promptNote}</p>
                        )}
                        {agent.promptTemplate && (
                          <pre className="text-xs bg-[var(--muted)] p-3 rounded-md overflow-auto whitespace-pre-wrap leading-relaxed border border-[var(--border)]">
                            {agent.promptTemplate}
                          </pre>
                        )}
                      </div>

                      {/* Tips */}
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted-foreground)] mb-2">Try changing this</p>
                        <div className="space-y-2">
                          {agent.tips.map((tip) => (
                            <div key={tip.title} className="flex gap-2.5 text-sm p-3 rounded-md bg-yellow-50 border border-yellow-200 dark:bg-yellow-950 dark:border-yellow-900">
                              <Lightbulb className="w-4 h-4 shrink-0 text-yellow-600 dark:text-yellow-400 mt-0.5" />
                              <div>
                                <p className="font-medium text-yellow-900 dark:text-yellow-200">{tip.title}</p>
                                <p className="text-yellow-800 dark:text-yellow-300 mt-0.5">{tip.detail}</p>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </section>

        {/* Using the UI */}
        <section id="using-ui" ref={(el) => { sectionRefs.current["using-ui"] = el; }}>
          <h3 className="text-xl font-semibold mb-4">Using the UI</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {uiPages.map((page) => {
              const Icon = page.icon;
              return (
                <Card key={page.name}>
                  <CardHeader>
                    <CardTitle className="text-lg flex items-center gap-2">
                      <Icon className="w-5 h-5" />
                      {page.name}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="list-disc list-inside space-y-1 text-sm text-[var(--muted-foreground)]">
                      {page.items.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </section>

        {/* Configuration */}
        <section id="configuration" ref={(el) => { sectionRefs.current["configuration"] = el; }}>
          <h3 className="text-xl font-semibold mb-4">Configuration</h3>
          <div className="space-y-4">
            {/* LLM Providers */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Cpu className="w-5 h-5" />
                  LLM Providers
                </CardTitle>
                <CardDescription>
                  Configure one or more LLM providers. Ollama works out of the box with no API key.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3 text-sm">
                  <div className="flex items-center justify-between p-2 rounded border border-[var(--border)]">
                    <div>
                      <p className="font-medium">Ollama (Local)</p>
                      <p className="text-[var(--muted-foreground)]">Free, runs locally, no API key needed</p>
                    </div>
                    <code className="text-xs px-2 py-1 rounded bg-[var(--secondary)]">OLLAMA_BASE_URL</code>
                  </div>
                  <div className="flex items-center justify-between p-2 rounded border border-[var(--border)]">
                    <div>
                      <p className="font-medium">Claude (Anthropic)</p>
                      <p className="text-[var(--muted-foreground)]">Best reasoning, used for research and prompt generation</p>
                    </div>
                    <code className="text-xs px-2 py-1 rounded bg-[var(--secondary)]">ANTHROPIC_API_KEY</code>
                  </div>
                  <div className="flex items-center justify-between p-2 rounded border border-[var(--border)]">
                    <div>
                      <p className="font-medium">OpenAI</p>
                      <p className="text-[var(--muted-foreground)]">Optional alternative provider</p>
                    </div>
                    <code className="text-xs px-2 py-1 rounded bg-[var(--secondary)]">OPENAI_API_KEY</code>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* LLM Routing */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Activity className="w-5 h-5" />
                  LLM Routing
                </CardTitle>
                <CardDescription>
                  LLM provider selection is controlled by the ConfigHUD. The <code className="text-xs px-1 py-0.5 rounded bg-[var(--secondary)]">DEPLOYMENT_MODE</code> env var determines which providers are available.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-[var(--border)]">
                        <th className="text-left py-2 pr-4 font-medium">Task</th>
                        <th className="text-left py-2 pr-4 font-medium">Provider</th>
                        <th className="text-left py-2 font-medium">Reason</th>
                      </tr>
                    </thead>
                    <tbody>
                      {routingTable.map((row) => (
                        <tr key={row.task} className="border-b border-[var(--border)] last:border-0">
                          <td className="py-2 pr-4">
                            <Badge variant="secondary">{row.task}</Badge>
                          </td>
                          <td className="py-2 pr-4">
                            <Badge variant="outline">{row.provider}</Badge>
                          </td>
                          <td className="py-2 text-[var(--muted-foreground)]">{row.reason}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>

            {/* Image Providers */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Image className="w-5 h-5" />
                  Image Providers
                </CardTitle>
                <CardDescription>
                  Set <code className="text-xs px-1 py-0.5 rounded bg-[var(--secondary)]">IMAGE_PROVIDER</code> in your .env file.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3 text-sm">
                  <div className="flex items-center justify-between p-2 rounded border border-[var(--border)]">
                    <div>
                      <p className="font-medium">Mock</p>
                      <p className="text-[var(--muted-foreground)]">Placeholder images for development and testing</p>
                    </div>
                    <Badge variant="success">Default</Badge>
                  </div>
                  <div className="flex items-center justify-between p-2 rounded border border-[var(--border)]">
                    <div>
                      <p className="font-medium">Stable Diffusion</p>
                      <p className="text-[var(--muted-foreground)]">Local SD instance for portrait generation</p>
                    </div>
                    <code className="text-xs px-2 py-1 rounded bg-[var(--secondary)]">SD_API_URL</code>
                  </div>
                  <div className="flex items-center justify-between p-2 rounded border border-[var(--border)]">
                    <div>
                      <p className="font-medium">FaceFusion</p>
                      <p className="text-[var(--muted-foreground)]">Face consistency across multiple generations</p>
                    </div>
                    <code className="text-xs px-2 py-1 rounded bg-[var(--secondary)]">FACEFUSION_API_URL</code>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </section>

        {/* CLI Reference */}
        <section id="cli-reference" ref={(el) => { sectionRefs.current["cli-reference"] = el; }}>
          <h3 className="text-xl font-semibold mb-4">CLI Reference</h3>
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Terminal className="w-5 h-5" />
                Commands
              </CardTitle>
              <CardDescription>
                All commands accept <code className="text-xs px-1 py-0.5 rounded bg-[var(--secondary)]">--base-url</code> to
                specify the API endpoint (default: <code className="text-xs px-1 py-0.5 rounded bg-[var(--secondary)]">http://localhost:8000/api</code>).
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[var(--border)]">
                      <th className="text-left py-2 pr-4 font-medium">Command</th>
                      <th className="text-left py-2 font-medium">Description</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cliCommands.map((row) => (
                      <tr key={row.command} className="border-b border-[var(--border)] last:border-0">
                        <td className="py-2 pr-4">
                          <code className="text-xs px-2 py-1 rounded bg-[var(--secondary)]">{row.command}</code>
                        </td>
                        <td className="py-2 text-[var(--muted-foreground)]">{row.description}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </section>
      </div>
    </div>
  );
}
