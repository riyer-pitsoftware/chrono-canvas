import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useGenerations, useDeleteGeneration } from '@/api/hooks/useGeneration';
import { useNavigation } from '@/stores/navigation';
import { Trash2 } from 'lucide-react';

export function AuditList() {
  const { data, isLoading, error } = useGenerations(0, 50);
  const { navigate } = useNavigation();
  const deleteGeneration = useDeleteGeneration();

  if (isLoading) return <div>Loading generations...</div>;
  if (error) return <div className="text-[var(--destructive)]">Error: {error.message}</div>;

  const items = data?.items ?? [];

  const statusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'success' as const;
      case 'failed':
        return 'destructive' as const;
      default:
        return 'secondary' as const;
    }
  };

  return (
    <div>
      <h2 className="text-3xl font-bold mb-6">Audit Trail</h2>

      <Card>
        <CardHeader>
          <CardTitle>Recent Generations</CardTitle>
        </CardHeader>
        <CardContent>
          {items.length === 0 ? (
            <p className="text-sm text-[var(--muted-foreground)]">No generations yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left">
                    <th className="pb-2 font-medium">Input</th>
                    <th className="pb-2 font-medium">Status</th>
                    <th className="pb-2 font-medium">Date</th>
                    <th className="pb-2 font-medium">Cost</th>
                    <th className="pb-2 font-medium w-12"></th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => {
                    const totalCost =
                      item.agent_trace?.reduce((sum, t) => sum + (Number(t.llm_cost) || 0), 0) ?? 0;
                    return (
                      <tr
                        key={item.id}
                        onClick={() => navigate(`/audit/${item.id}`)}
                        className="border-b cursor-pointer hover:bg-[var(--accent)] transition-colors"
                      >
                        <td className="py-2 pr-4 max-w-xs truncate">
                          {item.input_text.length > 60
                            ? item.input_text.slice(0, 60) + '...'
                            : item.input_text}
                        </td>
                        <td className="py-2 pr-4">
                          <Badge variant={statusColor(item.status)}>{item.status}</Badge>
                        </td>
                        <td className="py-2 pr-4 text-[var(--muted-foreground)]">
                          {new Date(item.created_at).toLocaleDateString()}
                        </td>
                        <td className="py-2 pr-4 text-[var(--muted-foreground)]">
                          {totalCost > 0 ? `$${totalCost.toFixed(6)}` : '—'}
                        </td>
                        <td className="py-2">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-[var(--muted-foreground)] hover:text-[var(--destructive)]"
                            onClick={(e) => {
                              e.stopPropagation();
                              if (
                                window.confirm('Delete this generation? This cannot be undone.')
                              ) {
                                deleteGeneration.mutate(item.id);
                              }
                            }}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
