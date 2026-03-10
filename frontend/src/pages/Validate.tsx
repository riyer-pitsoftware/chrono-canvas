import { useCallback, useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { api } from '@/api/client';
import { useGenerations } from '@/api/hooks/useGeneration';
import { useNavigation } from '@/stores/navigation';
import type { ValidationSummary } from '@/api/types';

interface ValidateProps {
  initialRequestId?: string;
}

export function Validate({ initialRequestId }: ValidateProps) {
  const [requestId, setRequestId] = useState(initialRequestId ?? '');
  const [results, setResults] = useState<ValidationSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [recentPage, setRecentPage] = useState(0);
  const [statusFilter, setStatusFilter] = useState('all');
  const RECENT_LIMIT = 10;
  const recentOffset = recentPage * RECENT_LIMIT;
  const statusParam = statusFilter === 'all' ? undefined : statusFilter;
  const {
    data: recentGenerations,
    isLoading: loadingGenerations,
    error: recentError,
  } = useGenerations(recentOffset, RECENT_LIMIT, statusParam);
  const { navigate } = useNavigation();
  const handleValidate = useCallback(
    async (overrideId?: string) => {
      const idToValidate = (overrideId ?? requestId).trim();
      if (!idToValidate) return;
      setLoading(true);
      try {
        const data = await api.get<ValidationSummary>(`/validation/${idToValidate}`);
        setResults(data);
      } catch {
        setResults(null);
      } finally {
        setLoading(false);
      }
    },
    [requestId],
  );

  useEffect(() => {
    if (!initialRequestId) return;
    setRequestId(initialRequestId);
    const fetchInitial = async () => {
      setLoading(true);
      try {
        const data = await api.get<ValidationSummary>(`/validation/${initialRequestId}`);
        setResults(data);
      } catch {
        setResults(null);
      } finally {
        setLoading(false);
      }
    };
    fetchInitial();
  }, [initialRequestId]);

  useEffect(() => {
    setRecentPage(0);
  }, [statusFilter]);

  useEffect(() => {
    if (!recentGenerations) return;
    const total = recentGenerations.total;
    if (total === 0 && recentPage !== 0) {
      setRecentPage(0);
      return;
    }
    if (total > 0 && recentOffset >= total) {
      const lastPage = Math.max(0, Math.ceil(total / RECENT_LIMIT) - 1);
      if (recentPage !== lastPage) {
        setRecentPage(lastPage);
      }
    }
  }, [recentGenerations, recentOffset, recentPage]);

  const recentItems = recentGenerations?.items ?? [];
  const recentTotal = recentGenerations?.total ?? 0;
  const recentTotalPages = recentTotal === 0 ? 1 : Math.ceil(recentTotal / RECENT_LIMIT);
  const showingFrom = recentTotal === 0 ? 0 : recentOffset + 1;
  const showingTo = recentTotal === 0 ? 0 : recentOffset + recentItems.length;

  const getStatusVariant = (status: string) => {
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
      <h2 className="text-3xl font-bold mb-6">Validation</h2>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Check Validation</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-3">
            <Input
              placeholder="Enter generation request ID..."
              value={requestId}
              onChange={(e) => setRequestId(e.target.value)}
              className="flex-1"
            />
            <Button onClick={() => handleValidate()} disabled={loading}>
              {loading ? 'Checking...' : 'Check'}
            </Button>
          </div>
        </CardContent>
      </Card>

      {results && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Results</CardTitle>
              <Badge variant={results.passed ? 'success' : 'destructive'}>
                Score: {results.overall_score.toFixed(1)}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {results.results.map((r) => (
                <div
                  key={r.id}
                  className="flex items-center justify-between p-3 border border-[var(--border)] rounded-md"
                >
                  <div>
                    <p className="font-medium">
                      {r.category}: {r.rule_name}
                    </p>
                    {r.details && (
                      <p className="text-sm text-[var(--muted-foreground)]">{r.details}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm">{r.score.toFixed(1)}</span>
                    <Badge variant={r.passed ? 'success' : 'destructive'}>
                      {r.passed ? 'Pass' : 'Fail'}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <CardTitle>Recent Generations</CardTitle>
            <div className="flex items-center gap-2 text-xs text-[var(--muted-foreground)]">
              <label htmlFor="statusFilter" className="font-medium text-[var(--foreground)]">
                Status
              </label>
              <select
                id="statusFilter"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="rounded border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-xs"
              >
                <option value="all">All</option>
                <option value="pending">Pending</option>
                <option value="extracting">Extracting</option>
                <option value="researching">Researching</option>
                <option value="generating_prompt">Generating Prompt</option>
                <option value="generating_image">Generating Image</option>
                <option value="validating">Validating</option>
                <option value="swapping_face">Swapping Face</option>
                <option value="completed">Completed</option>
                <option value="failed">Failed</option>
              </select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {loadingGenerations ? (
            <p className="text-sm text-[var(--muted-foreground)]">Loading recent generations…</p>
          ) : recentError ? (
            <p className="text-sm text-[var(--destructive)]">Failed to load recent generations.</p>
          ) : recentItems.length === 0 ? (
            <p className="text-sm text-[var(--muted-foreground)]">No generations yet.</p>
          ) : (
            <>
              <div className="space-y-3">
                {recentItems.map((item) => (
                  <div
                    key={item.id}
                    className="border rounded-md p-3 flex flex-wrap items-center gap-3"
                  >
                    <div className="flex-1 min-w-[200px]">
                      <p className="text-sm font-medium text-[var(--foreground)]">
                        {item.figure_id ? item.figure_id : 'Custom request'}
                      </p>
                      <p className="text-xs text-[var(--muted-foreground)] break-all">
                        {item.input_text.length > 120
                          ? `${item.input_text.slice(0, 120)}…`
                          : item.input_text}
                      </p>
                      <p className="text-xs text-[var(--muted-foreground)] mt-1">
                        {new Date(item.created_at).toLocaleString()}
                      </p>
                    </div>
                    <Badge variant={getStatusVariant(item.status)}>{item.status}</Badge>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setRequestId(item.id);
                          handleValidate(item.id);
                        }}
                      >
                        Validate
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => navigate(`/audit/${item.id}`)}
                      >
                        View Audit
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-xs text-[var(--muted-foreground)]">
                <span>
                  Showing {recentTotal === 0 ? 0 : `${showingFrom}–${showingTo}`} of {recentTotal}{' '}
                  generations
                </span>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={recentPage === 0}
                    onClick={() => setRecentPage((p) => Math.max(0, p - 1))}
                  >
                    Previous
                  </Button>
                  <span>
                    Page {recentTotal === 0 ? 0 : recentPage + 1} / {recentTotalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={recentTotal === 0 || recentPage >= recentTotalPages - 1}
                    onClick={() => setRecentPage((p) => Math.min(recentTotalPages - 1, p + 1))}
                  >
                    Next
                  </Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
