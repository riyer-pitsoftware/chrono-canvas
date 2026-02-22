import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useFigures } from "@/api/hooks/useFigures";
import { useNavigation } from "@/stores/navigation";
import { cn } from "@/lib/utils";

export function FigureLibrary() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [selectedFigure, setSelectedFigure] = useState<{ id: string; name: string } | null>(null);
  const limit = 12;
  const offset = page * limit;
  const { data, isLoading } = useFigures(search || undefined, offset, limit);
  const { navigate } = useNavigation();

  useEffect(() => {
    setPage(0);
  }, [search]);

  useEffect(() => {
    if (!data) return;
    if (data.total === 0 && page !== 0) {
      setPage(0);
      return;
    }
    if (data.total > 0 && offset >= data.total) {
      setPage(0);
    }
  }, [data, offset, page]);

  const figures = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = data ? Math.ceil(data.total / data.limit) : 1;
  const showingFrom = total === 0 ? 0 : offset + 1;
  const showingTo = total === 0 ? 0 : offset + figures.length;

  const handleSelect = (figureId: string, figureName: string) => {
    setSelectedFigure({ id: figureId, name: figureName });
  };

  const handleGenerate = () => {
    if (!selectedFigure) return;
    navigate(`/generate?figure_id=${selectedFigure.id}`);
  };

  const selectedName = selectedFigure?.name ?? null;

  return (
    <div>
      <div className="flex flex-wrap items-center gap-4 justify-between mb-6">
        <div className="space-y-1">
          <h2 className="text-3xl font-bold">Figure Library</h2>
          {selectedName && (
            <p className="text-sm text-[var(--muted-foreground)]">
              Selected: <span className="font-medium text-[var(--foreground)]">{selectedName}</span>
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-3 items-center">
          <Input
            placeholder="Search figures..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-64"
          />
          <Button
            variant="ghost"
            size="sm"
            disabled={!selectedFigure}
            onClick={() => setSelectedFigure(null)}
          >
            Clear selection
          </Button>
          <Button
            size="sm"
            disabled={!selectedFigure}
            onClick={handleGenerate}
          >
            Generate portrait
          </Button>
        </div>
      </div>

      {isLoading && <p>Loading...</p>}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {figures.map((figure) => {
          const isSelected = selectedFigure?.id === figure.id;
          return (
            <Card
              key={figure.id}
              className={cn(
                "flex flex-col border transition-colors cursor-pointer",
                isSelected ? "border-[var(--primary)] ring-1 ring-[var(--primary)]" : "",
              )}
              onClick={() => handleSelect(figure.id, figure.name)}
            >
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
                variant={isSelected ? "default" : "outline"}
                size="sm"
                className="mt-3 w-full"
                onClick={(e) => {
                  e.stopPropagation();
                  handleSelect(figure.id, figure.name);
                }}
              >
                {isSelected ? "Selected" : "Select figure"}
              </Button>
            </CardContent>
            </Card>
          );
        })}
      </div>

      {data && (
        <div className="mt-6 flex flex-wrap items-center justify-between gap-3 text-sm text-[var(--muted-foreground)]">
          <span>
            Showing {total === 0 ? 0 : `${showingFrom}–${showingTo}`} of {total} figures
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page === 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
            >
              Previous
            </Button>
            <span className="text-xs text-[var(--muted-foreground)]">
              Page {totalPages === 0 ? 0 : page + 1} / {totalPages || 1}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={data.total === 0 || page >= totalPages - 1}
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
