import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { BookOpen, Camera } from "lucide-react";
import { useNavigation } from "@/stores/navigation";

const modes = [
  {
    id: "creative_story",
    title: "Story Director",
    description:
      "Create multi-scene visual storyboards from your narrative. AI extracts characters, finds references, and generates a complete storyboard.",
    badge: "Creative",
    cta: "Start Creating",
    icon: BookOpen,
  },
  {
    id: "portrait",
    title: "Historical Lens",
    description:
      "Generate historically-accurate portraits of real figures. AI researches the period, crafts prompts, and produces validated artwork.",
    badge: "Portrait",
    cta: "Start Generating",
    icon: Camera,
  },
] as const;

export function ModeSelector() {
  const { navigate } = useNavigation();

  return (
    <div className="flex flex-col items-center justify-center min-h-[80vh] gap-8">
      <div className="text-center space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">
          ChronoNoir Studio
        </h1>
        <p className="text-[var(--muted-foreground)]">
          Choose your creative mode
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-3xl w-full">
        {modes.map((mode) => {
          const Icon = mode.icon;
          return (
            <Card
              key={mode.id}
              className="cursor-pointer hover:border-[var(--primary)] transition-colors group"
              onClick={() => navigate(`/generate?mode=${mode.id}`)}
            >
              <CardHeader>
                <div className="flex items-center justify-between">
                  <Icon className="h-8 w-8 text-[var(--primary)]" />
                  <Badge variant="secondary">{mode.badge}</Badge>
                </div>
                <CardTitle className="text-xl">{mode.title}</CardTitle>
                <CardDescription>{mode.description}</CardDescription>
              </CardHeader>
              <CardContent>
                <Button className="w-full">{mode.cta}</Button>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
