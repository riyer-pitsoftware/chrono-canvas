import { AlertCircle, Trash2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useCacheEntries, useCacheStats, useClearCache } from "@/api/hooks/useMemory";

export function Memory() {
  const { data: statsData } = useCacheStats();
  const { data: entriesData, isLoading: entriesLoading, refetch } = useCacheEntries();
  const clearCacheMutation = useClearCache();

  const handleClearCache = async () => {
    if (window.confirm("Are you sure you want to clear all cached research entries?")) {
      await clearCacheMutation.mutateAsync();
      refetch();
    }
  };

  const stats = statsData || {
    total_entries: 0,
    total_hits: 0,
    estimated_cost_saved_usd: 0,
  };

  const entries = entriesData?.entries || [];

  return (
    <div>
      <h2 className="text-3xl font-bold mb-6">Research Memory</h2>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-gray-600">Total Cached</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total_entries}</div>
            <p className="text-xs text-gray-500">research queries</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-gray-600">Total Hits</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total_hits}</div>
            <p className="text-xs text-gray-500">cache lookups served</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-gray-600">Cost Saved</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">${stats.estimated_cost_saved_usd.toFixed(2)}</div>
            <p className="text-xs text-gray-500">by avoiding LLM calls</p>
          </CardContent>
        </Card>
      </div>

      {/* Cache Entries */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Cached Research Entries</CardTitle>
            <Button
              variant="destructive"
              size="sm"
              onClick={handleClearCache}
              disabled={entries.length === 0 || clearCacheMutation.isPending}
              className="gap-2"
            >
              <Trash2 className="w-4 h-4" />
              {clearCacheMutation.isPending ? "Clearing..." : "Clear All"}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {entriesLoading ? (
            <div className="text-center text-gray-500">Loading cache entries...</div>
          ) : entries.length === 0 ? (
            <div className="flex items-center gap-2 p-4 text-sm text-gray-600 border border-gray-200 rounded">
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
              <span>No cached research entries yet. Cache will populate as you generate portraits.</span>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-2 px-3 font-semibold">Figure</th>
                    <th className="text-left py-2 px-3 font-semibold">Period</th>
                    <th className="text-left py-2 px-3 font-semibold">Region</th>
                    <th className="text-right py-2 px-3 font-semibold">Hits</th>
                    <th className="text-right py-2 px-3 font-semibold">Cost Saved</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((entry) => (
                    <tr key={entry.id} className="border-b hover:bg-gray-50">
                      <td className="py-3 px-3 font-medium">{entry.figure_name}</td>
                      <td className="py-3 px-3 text-gray-600">{entry.time_period}</td>
                      <td className="py-3 px-3 text-gray-600">{entry.region}</td>
                      <td className="py-3 px-3 text-right">{entry.hit_count}</td>
                      <td className="py-3 px-3 text-right text-green-600 font-medium">
                        ${entry.cost_saved_usd.toFixed(4)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
