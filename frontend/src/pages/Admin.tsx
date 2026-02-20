import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useAgents, useLLMStatus, useCostSummary } from "@/api/hooks/useAgents";

export function Admin() {
  const agents = useAgents();
  const llmStatus = useLLMStatus();
  const costs = useCostSummary();

  return (
    <div>
      <h2 className="text-3xl font-bold mb-6">Admin</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Agents</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {agents.data?.agents.map((agent) => (
                <div key={agent.name} className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">{agent.name}</p>
                    <p className="text-xs text-[var(--muted-foreground)]">{agent.description}</p>
                  </div>
                  <Badge variant="success">{agent.status}</Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>LLM Providers</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {llmStatus.data &&
                Object.entries(llmStatus.data.providers).map(([name, available]) => (
                  <div key={name} className="flex items-center justify-between">
                    <p className="font-medium">{name}</p>
                    <Badge variant={available ? "success" : "destructive"}>
                      {available ? "Available" : "Unavailable"}
                    </Badge>
                  </div>
                ))}
            </div>
          </CardContent>
        </Card>

        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle>Cost Summary</CardTitle>
          </CardHeader>
          <CardContent>
            {costs.data && (
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <p className="text-sm text-[var(--muted-foreground)]">Total Cost</p>
                  <p className="text-2xl font-bold">${costs.data.total_cost.toFixed(4)}</p>
                </div>
                <div>
                  <p className="text-sm text-[var(--muted-foreground)]">Total Tokens</p>
                  <p className="text-2xl font-bold">{costs.data.total_tokens.toLocaleString()}</p>
                </div>
                <div>
                  <p className="text-sm text-[var(--muted-foreground)]">API Calls</p>
                  <p className="text-2xl font-bold">{costs.data.num_calls}</p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
