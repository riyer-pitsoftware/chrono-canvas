import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useFigures } from "@/api/hooks/useFigures";
import { useNavigation } from "@/stores/navigation";

export function FigureLibrary() {
  const [search, setSearch] = useState("");
  const { data, isLoading } = useFigures(search || undefined);
  const { navigate } = useNavigation();

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-3xl font-bold">Figure Library</h2>
        <div className="flex gap-3">
          <Input
            placeholder="Search figures..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-64"
          />
        </div>
      </div>

      {isLoading && <p>Loading...</p>}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {data?.items.map((figure) => (
          <Card key={figure.id} className="flex flex-col">
            <CardHeader>
              <CardTitle className="text-lg">{figure.name}</CardTitle>
            </CardHeader>
            <CardContent className="flex-1 flex flex-col">
              <div className="space-y-2 text-sm flex-1">
                {figure.birth_year && (
                  <p>
                    <span className="text-[var(--muted-foreground)]">Period:</span>{" "}
                    {figure.birth_year}–{figure.death_year ?? "?"}
                  </p>
                )}
                {figure.nationality && (
                  <p>
                    <span className="text-[var(--muted-foreground)]">Nationality:</span>{" "}
                    {figure.nationality}
                  </p>
                )}
                {figure.occupation && <Badge variant="secondary">{figure.occupation}</Badge>}
                {figure.description && (
                  <p className="text-[var(--muted-foreground)] line-clamp-2">{figure.description}</p>
                )}
              </div>
              <Button
                variant="outline"
                size="sm"
                className="mt-3 w-full"
                onClick={() => navigate(`/generate?figure_id=${figure.id}`)}
              >
                Generate Portrait
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>

      {data && data.total > data.limit && (
        <p className="mt-4 text-sm text-[var(--muted-foreground)]">
          Showing {data.items.length} of {data.total} figures
        </p>
      )}
    </div>
  );
}
