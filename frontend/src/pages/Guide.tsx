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
} from "lucide-react";

const tocItems = [
  { id: "getting-started", label: "Getting Started" },
  { id: "pipeline", label: "The Pipeline" },
  { id: "using-ui", label: "Using the UI" },
  { id: "configuration", label: "Configuration" },
  { id: "cli-reference", label: "CLI Reference" },
];

const pipelineSteps = [
  { name: "Orchestrator", provider: "Ollama", description: "Receives request and creates an execution plan" },
  { name: "Extraction", provider: "Ollama", description: "Parses text into structured figure data" },
  { name: "Research", provider: "Claude", description: "Enriches data with historical context and facts" },
  { name: "Prompt Gen", provider: "Claude", description: "Creates period-accurate image generation prompts" },
  { name: "Image Gen", provider: "—", description: "Produces portrait via Stable Diffusion or FaceFusion" },
  { name: "Validation", provider: "Ollama", description: "Scores historical accuracy (0–100) and flags issues" },
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
      "Review historical accuracy scores (0–100)",
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
  { command: "historylens add figure", description: "Add a historical figure to the database" },
  { command: "historylens generate", description: "Generate a portrait from a text description" },
  { command: "historylens batch", description: "Run batch generation from a JSON file" },
  { command: "historylens status", description: "Check the status of a generation request" },
  { command: "historylens download", description: "Download the generated image" },
  { command: "historylens list figures", description: "List historical figures with search/filter" },
  { command: "historylens list generations", description: "List generation requests" },
  { command: "historylens validate", description: "Show validation results for a generation" },
  { command: "historylens agents list", description: "List all available agents" },
  { command: "historylens agents llm-status", description: "Check LLM provider availability" },
  { command: "historylens agents costs", description: "Show LLM cost summary" },
];

const routingTable = [
  { task: "Extraction", provider: "Ollama", reason: "Fast, free, sufficient for structured parsing" },
  { task: "Research", provider: "Claude", reason: "Best reasoning for historical enrichment" },
  { task: "Prompt Generation", provider: "Claude", reason: "Strong creative + accurate prompt crafting" },
  { task: "Validation", provider: "Ollama", reason: "Cost-effective for scoring checks" },
  { task: "Orchestration", provider: "Ollama", reason: "Lightweight coordination logic" },
  { task: "General", provider: "Ollama", reason: "Default fallback, no API cost" },
];

export function Guide() {
  const [activeSection, setActiveSection] = useState(tocItems[0].id);
  const sectionRefs = useRef<Record<string, HTMLElement | null>>({});

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

  function scrollTo(id: string) {
    const el = sectionRefs.current[id];
    if (el) el.scrollIntoView({ behavior: "smooth" });
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
            Everything you need to know about using HistoryLens.
          </p>
        </div>

        {/* Getting Started */}
        <section id="getting-started" ref={(el) => { sectionRefs.current["getting-started"] = el; }}>
          <h3 className="text-xl font-semibold mb-4">Getting Started</h3>
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Sparkles className="w-5 h-5" />
                What is HistoryLens?
              </CardTitle>
              <CardDescription>
                HistoryLens is an open-source toolkit that generates historically-accurate portraits using a 7-agent AI pipeline.
                It's built for educators, historians, and content creators who need period-accurate character depictions.
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
              <CardTitle className="text-lg">7-Agent Flow</CardTitle>
              <CardDescription>
                Each generation passes through seven autonomous agents in sequence.
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
                  Default task-to-provider mapping. Override by changing <code className="text-xs px-1 py-0.5 rounded bg-[var(--secondary)]">DEFAULT_LLM_PROVIDER</code> in your .env file.
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
