import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useFigures } from "@/api/hooks/useFigures";
import { useGenerations } from "@/api/hooks/useGeneration";
import { useCostSummary } from "@/api/hooks/useAgents";
import { useNavigation } from "@/stores/navigation";

export function Dashboard() {
  const figures = useFigures();
  const generations = useGenerations();
  const costs = useCostSummary();
  const { navigate } = useNavigation();

  return (
    <div>
      <h2 className="text-3xl font-bold mb-6">Dashboard</h2>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <Card>
          <CardHeader>
            <CardDescription>Total Figures</CardDescription>
            <CardTitle>{figures.data?.total ?? "..."}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Generations</CardDescription>
            <CardTitle>{generations.data?.total ?? "..."}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>LLM Costs</CardDescription>
            <CardTitle>${costs.data?.total_cost.toFixed(4) ?? "..."}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent Generations</CardTitle>
        </CardHeader>
        <CardContent>
          {generations.data?.items.length === 0 && (
            <p className="text-[var(--muted-foreground)]">No generations yet. Start one from the Generate page.</p>
          )}
          <div className="space-y-3">
            {generations.data?.items.slice(0, 5).map((gen) => (
              <div
                key={gen.id}
                onClick={() => navigate(`/audit/${gen.id}`)}
                className="flex items-center justify-between p-3 rounded-md border border-[var(--border)] cursor-pointer hover:bg-[var(--accent)] transition-colors"
              >
                <div>
                  <p className="font-medium">{gen.input_text.slice(0, 60)}</p>
                  <p className="text-sm text-[var(--muted-foreground)]">
                    {new Date(gen.created_at).toLocaleDateString()}
                  </p>
                </div>
                <Badge variant={gen.status === "completed" ? "success" : gen.status === "failed" ? "destructive" : "secondary"}>
                  {gen.status}
                </Badge>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
