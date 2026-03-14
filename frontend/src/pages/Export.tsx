import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useCompletedGenerations } from '@/api/hooks/useGeneration';

export function Export() {
  const { data } = useCompletedGenerations(50);
  const completed = data?.items ?? [];

  return (
    <div>
      <h2 className="text-3xl font-bold mb-6">Export</h2>

      <Card>
        <CardHeader>
          <CardTitle>Completed Generations</CardTitle>
        </CardHeader>
        <CardContent>
          {completed.length === 0 && (
            <p className="text-[var(--muted-foreground)]">No completed generations to export.</p>
          )}
          <div className="space-y-3">
            {completed.map((gen) => (
              <div
                key={gen.id}
                className="flex items-center justify-between p-3 border border-[var(--border)] rounded-md"
              >
                <div>
                  <p className="font-medium">{gen.input_text.slice(0, 60)}</p>
                  <p className="text-xs text-[var(--muted-foreground)]">{gen.id}</p>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" asChild>
                    <a href={`/api/export/${gen.id}/download`} download>
                      Download Image
                    </a>
                  </Button>
                  <Button variant="outline" size="sm" asChild>
                    <a href={`/api/export/${gen.id}/metadata`} target="_blank" rel="noreferrer">
                      Metadata
                    </a>
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
