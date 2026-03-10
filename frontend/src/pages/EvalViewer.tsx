import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  useEvalRuns,
  useEvalRun,
  useEvalCases,
  useEvalDashboard,
  useRejectEvalRun,
  useUnrejectEvalRun,
} from '@/api/hooks/useEval';
import type { EvalRunDetail, EvalRunSummary, DimensionAggregate } from '@/api/types';

// ── Tab navigation ──────────────────────────────────────────────────────────

type Tab = 'gallery' | 'comparison' | 'dashboard' | 'agreement';

const TABS: { id: Tab; label: string }[] = [
  { id: 'gallery', label: 'Gallery' },
  { id: 'comparison', label: 'Comparison' },
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'agreement', label: 'Agreement' },
];

// ── Score dimensions ────────────────────────────────────────────────────────

const SCORE_DIMENSIONS = [
  'prompt_adherence',
  'visual_coherence',
  'face_usability',
  'period_plausibility',
  'anachronism_avoidance',
  'narrative_image_consistency',
  'uncertainty_signaling_quality',
  'audit_trace_completeness',
];

function dimLabel(dim: string): string {
  return dim
    .split('_')
    .map((w) => w[0].toUpperCase() + w.slice(1))
    .join(' ');
}

// ── Condition colors ────────────────────────────────────────────────────────

const CONDITION_COLORS: Record<string, string> = {
  baselineA: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  baselineB: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  baselineC: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  baselineD: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
};

function conditionBadge(condition: string) {
  const cls = CONDITION_COLORS[condition] ?? 'bg-gray-500/20 text-gray-400 border-gray-500/30';
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${cls}`}
    >
      {condition}
    </span>
  );
}

// ── Score bar (0–3 scale) ───────────────────────────────────────────────────

function ScoreBar({ value, max = 3 }: { value: number; max?: number }) {
  const pct = (value / max) * 100;
  const color = value >= 2.5 ? 'bg-emerald-500' : value >= 1.5 ? 'bg-amber-500' : 'bg-red-500';
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-2 rounded-full bg-[var(--border)] overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-[var(--muted-foreground)] w-8">{value.toFixed(1)}</span>
    </div>
  );
}

// ── Gallery Tab ─────────────────────────────────────────────────────────────

function GalleryTab() {
  const [conditionFilter, setConditionFilter] = useState<string>('');
  const [caseFilter, setCaseFilter] = useState<string>('');
  const [showRejected, setShowRejected] = useState(false);
  const [selectedRun, setSelectedRun] = useState<string | undefined>();

  const { data: runs, isLoading } = useEvalRuns(
    conditionFilter || undefined,
    caseFilter || undefined,
    showRejected,
  );
  const { data: runDetail } = useEvalRun(selectedRun);
  const { data: cases } = useEvalCases();

  // Extract unique conditions and case IDs for filters
  const conditions = [...new Set(runs?.map((r) => r.condition) ?? [])].sort();
  const caseIds = [...new Set(cases?.map((c) => c.case_id) ?? [])].sort();

  if (selectedRun && runDetail) {
    return (
      <div className="space-y-4">
        <Button variant="outline" size="sm" onClick={() => setSelectedRun(undefined)}>
          &larr; Back to Gallery
        </Button>
        <RunDetailView run={runDetail} />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex gap-3 flex-wrap items-center">
        <select
          value={conditionFilter}
          onChange={(e) => setConditionFilter(e.target.value)}
          className="rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-1.5 text-sm"
        >
          <option value="">All Conditions</option>
          {conditions.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <select
          value={caseFilter}
          onChange={(e) => setCaseFilter(e.target.value)}
          className="rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-1.5 text-sm"
        >
          <option value="">All Cases</option>
          {caseIds.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-1.5 text-sm cursor-pointer">
          <input
            type="checkbox"
            checked={showRejected}
            onChange={(e) => setShowRejected(e.target.checked)}
            className="rounded border-[var(--border)]"
          />
          Show rejected
        </label>
        {(conditionFilter || caseFilter) && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setConditionFilter('');
              setCaseFilter('');
            }}
          >
            Clear Filters
          </Button>
        )}
      </div>

      {isLoading && <p className="text-sm text-[var(--muted-foreground)]">Loading runs...</p>}

      {/* Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
        {runs?.map((run) => (
          <RunCard key={run.run_id} run={run} onClick={() => setSelectedRun(run.run_id)} />
        ))}
      </div>

      {runs && runs.length === 0 && (
        <p className="text-sm text-[var(--muted-foreground)]">No runs found.</p>
      )}
    </div>
  );
}

function RunCard({ run, onClick }: { run: EvalRunSummary; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`text-left rounded-lg border border-[var(--border)] bg-[var(--card)] overflow-hidden hover:border-[var(--primary)] transition-colors ${
        run.rejected ? 'opacity-50' : ''
      }`}
    >
      {run.image_url ? (
        <img src={run.image_url} alt={run.title} className="w-full aspect-square object-cover" />
      ) : (
        <div className="w-full aspect-square bg-[var(--accent)] flex items-center justify-center text-[var(--muted-foreground)] text-xs">
          No image
        </div>
      )}
      <div className="p-2 space-y-1">
        <p className="text-xs font-medium truncate">{run.title}</p>
        <div className="flex items-center gap-1.5 flex-wrap">
          {conditionBadge(run.condition)}
          {run.rejected && (
            <Badge
              variant="outline"
              className="text-red-400 border-red-500/30 bg-red-500/10 text-[10px]"
            >
              Rejected
            </Badge>
          )}
          {run.success ? (
            <Badge variant="outline" className="text-emerald-400 border-emerald-500/30 text-[10px]">
              OK
            </Badge>
          ) : (
            <Badge variant="outline" className="text-red-400 border-red-500/30 text-[10px]">
              FAIL
            </Badge>
          )}
          {run.has_rating && (
            <Badge variant="outline" className="text-[10px]">
              Rated
            </Badge>
          )}
        </div>
        <p className="text-[10px] text-[var(--muted-foreground)] truncate">{run.case_id}</p>
      </div>
    </button>
  );
}

function RunDetailView({ run }: { run: EvalRunDetail }) {
  const manifest = (run.manifest ?? {}) as Record<string, unknown>;
  const rating = run.rating as Record<string, unknown> | null;
  const outputText = run.output_text as string | null;
  const [rejectReason, setRejectReason] = useState('');
  const [showRejectForm, setShowRejectForm] = useState(false);
  const rejectMutation = useRejectEvalRun();
  const unrejectMutation = useUnrejectEvalRun();

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Image */}
      <div>
        {run.image_url ? (
          <img
            src={run.image_url}
            alt={run.title}
            className="w-full rounded-lg border border-[var(--border)]"
          />
        ) : (
          <div className="w-full aspect-square bg-[var(--accent)] rounded-lg flex items-center justify-center text-[var(--muted-foreground)]">
            No image available
          </div>
        )}
      </div>

      {/* Details */}
      <div className="space-y-4">
        <div>
          <h3 className="text-lg font-semibold">{run.title}</h3>
          <div className="flex items-center gap-2 mt-1">
            {conditionBadge(run.condition)}
            <span className="text-sm text-[var(--muted-foreground)]">{run.case_id}</span>
            {run.rejected && (
              <Badge variant="outline" className="text-red-400 border-red-500/30 bg-red-500/10">
                Rejected
              </Badge>
            )}
          </div>
        </div>

        {/* Reject / Unreject actions */}
        {run.rejected ? (
          <Button
            variant="outline"
            size="sm"
            onClick={() => unrejectMutation.mutate(run.run_id)}
            disabled={unrejectMutation.isPending}
          >
            {unrejectMutation.isPending ? 'Unrejecting...' : 'Unreject'}
          </Button>
        ) : showRejectForm ? (
          <div className="space-y-2 p-3 rounded-md border border-red-500/30 bg-red-500/5">
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Reason for rejection (optional)"
              className="w-full rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm resize-none"
              rows={2}
            />
            <div className="flex gap-2">
              <Button
                variant="destructive"
                size="sm"
                onClick={() => {
                  rejectMutation.mutate(
                    { runId: run.run_id, reason: rejectReason || undefined },
                    { onSuccess: () => setShowRejectForm(false) },
                  );
                }}
                disabled={rejectMutation.isPending}
              >
                {rejectMutation.isPending ? 'Rejecting...' : 'Confirm Reject'}
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setShowRejectForm(false)}>
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <Button
            variant="outline"
            size="sm"
            className="text-red-400 border-red-500/30 hover:bg-red-500/10"
            onClick={() => setShowRejectForm(true)}
          >
            Reject Run
          </Button>
        )}

        {/* Manifest highlights */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Run Metadata</CardTitle>
          </CardHeader>
          <CardContent className="text-xs space-y-1">
            <div className="grid grid-cols-2 gap-x-4 gap-y-1">
              <span className="text-[var(--muted-foreground)]">Image Provider</span>
              <span>{String(manifest.image_provider ?? '—')}</span>
              <span className="text-[var(--muted-foreground)]">Image Model</span>
              <span className="truncate">{String(manifest.image_model ?? '—')}</span>
              <span className="text-[var(--muted-foreground)]">Latency</span>
              <span>
                {manifest.total_latency_ms
                  ? `${(Number(manifest.total_latency_ms) / 1000).toFixed(1)}s`
                  : '—'}
              </span>
              <span className="text-[var(--muted-foreground)]">Cost</span>
              <span>
                {manifest.total_cost_usd != null
                  ? `$${Number(manifest.total_cost_usd).toFixed(4)}`
                  : '—'}
              </span>
              <span className="text-[var(--muted-foreground)]">Retries</span>
              <span>{String(manifest.total_retries ?? 0)}</span>
              <span className="text-[var(--muted-foreground)]">Git Commit</span>
              <span className="font-mono">{String(manifest.git_commit ?? '—')}</span>
            </div>
          </CardContent>
        </Card>

        {/* Rating scores */}
        {rating && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Rating Scores</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {SCORE_DIMENSIONS.map((dim) => {
                const val = rating[dim];
                if (val == null) return null;
                return (
                  <div key={dim} className="flex items-center justify-between">
                    <span className="text-xs text-[var(--muted-foreground)]">{dimLabel(dim)}</span>
                    <ScoreBar value={Number(val)} />
                  </div>
                );
              })}
              {Boolean(rating.freeform_notes) && (
                <div className="mt-3 pt-3 border-t border-[var(--border)]">
                  <p className="text-xs text-[var(--muted-foreground)] mb-1">Notes</p>
                  <p className="text-xs">{String(rating.freeform_notes)}</p>
                </div>
              )}
              {Boolean(rating.failure_tags) && (
                <div className="flex gap-1 flex-wrap mt-2">
                  {String(rating.failure_tags)
                    .split(';')
                    .filter(Boolean)
                    .map((tag) => (
                      <Badge
                        key={tag}
                        variant="outline"
                        className="text-[10px] text-red-400 border-red-500/30"
                      >
                        {tag.trim()}
                      </Badge>
                    ))}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Output text */}
        {outputText && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Output Text</CardTitle>
            </CardHeader>
            <CardContent>
              <pre className="text-xs whitespace-pre-wrap max-h-64 overflow-y-auto">
                {outputText}
              </pre>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

// ── Comparison Tab ──────────────────────────────────────────────────────────

function ComparisonTab() {
  const { data: cases, isLoading } = useEvalCases();
  const [selectedCaseId, setSelectedCaseId] = useState<string>('');

  const selectedCase = cases?.find((c) => c.case_id === selectedCaseId);

  // Group runs by condition, skip rejected (keep latest non-rejected per condition)
  const runsByCondition: Record<string, EvalRunSummary> = {};
  if (selectedCase) {
    for (const run of selectedCase.runs) {
      if (run.rejected) continue;
      runsByCondition[run.condition] = run;
    }
  }
  const conditions = Object.keys(runsByCondition).sort();

  return (
    <div className="space-y-4">
      <select
        value={selectedCaseId}
        onChange={(e) => setSelectedCaseId(e.target.value)}
        className="rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-1.5 text-sm min-w-64"
      >
        <option value="">Select a case to compare...</option>
        {cases?.map((c) => (
          <option key={c.case_id} value={c.case_id}>
            {c.case_id} — {c.title}
          </option>
        ))}
      </select>

      {isLoading && <p className="text-sm text-[var(--muted-foreground)]">Loading cases...</p>}

      {selectedCase && conditions.length === 0 && (
        <p className="text-sm text-[var(--muted-foreground)]">No runs found for this case.</p>
      )}

      {conditions.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {conditions.map((cond) => {
            const run = runsByCondition[cond];
            return <ComparisonCard key={cond} run={run} />;
          })}
        </div>
      )}
    </div>
  );
}

function ComparisonCard({ run }: { run: EvalRunSummary }) {
  const { data: detail } = useEvalRun(run.run_id);
  const rating = detail?.rating as Record<string, unknown> | null;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          {conditionBadge(run.condition)}
          {run.success ? (
            <Badge variant="outline" className="text-emerald-400 border-emerald-500/30 text-[10px]">
              OK
            </Badge>
          ) : (
            <Badge variant="outline" className="text-red-400 border-red-500/30 text-[10px]">
              FAIL
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {run.image_url ? (
          <img
            src={run.image_url}
            alt={`${run.condition} — ${run.title}`}
            className="w-full aspect-square object-cover rounded-md border border-[var(--border)]"
          />
        ) : (
          <div className="w-full aspect-square bg-[var(--accent)] rounded-md flex items-center justify-center text-xs text-[var(--muted-foreground)]">
            No image
          </div>
        )}

        {/* Score bars */}
        {rating && (
          <div className="space-y-1.5">
            {SCORE_DIMENSIONS.map((dim) => {
              const val = rating[dim];
              if (val == null) return null;
              return (
                <div key={dim} className="flex items-center justify-between">
                  <span className="text-[10px] text-[var(--muted-foreground)] truncate mr-2">
                    {dimLabel(dim)}
                  </span>
                  <ScoreBar value={Number(val)} />
                </div>
              );
            })}
          </div>
        )}
        {!rating && run.has_rating && (
          <p className="text-xs text-[var(--muted-foreground)]">Loading scores...</p>
        )}
        {!run.has_rating && <p className="text-xs text-[var(--muted-foreground)]">Not yet rated</p>}
      </CardContent>
    </Card>
  );
}

// ── Dashboard Tab ───────────────────────────────────────────────────────────

function DashboardTab() {
  const { data, isLoading } = useEvalDashboard();

  if (isLoading) {
    return <p className="text-sm text-[var(--muted-foreground)]">Loading dashboard...</p>;
  }
  if (!data) {
    return <p className="text-sm text-[var(--muted-foreground)]">No eval data available.</p>;
  }

  // Group dimension scores by dimension for display
  const dimByDimension: Record<string, DimensionAggregate[]> = {};
  for (const ds of data.dimension_scores) {
    dimByDimension[ds.dimension] = dimByDimension[ds.dimension] ?? [];
    dimByDimension[ds.dimension].push(ds);
  }

  return (
    <div className="space-y-6">
      {/* Overview stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-4">
            <p className="text-2xl font-bold">{data.total_runs}</p>
            <p className="text-xs text-[var(--muted-foreground)]">Total Runs</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <p className="text-2xl font-bold">{data.total_rated}</p>
            <p className="text-xs text-[var(--muted-foreground)]">Total Rated</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <p className="text-2xl font-bold">{data.conditions.length}</p>
            <p className="text-xs text-[var(--muted-foreground)]">Conditions</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <p className="text-2xl font-bold">{data.dimension_scores.length > 0 ? '8' : '0'}</p>
            <p className="text-xs text-[var(--muted-foreground)]">Dimensions</p>
          </CardContent>
        </Card>
      </div>

      {/* Condition summary table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Condition Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-[var(--border)]">
                  <th className="text-left py-2 pr-4">Condition</th>
                  <th className="text-right py-2 px-2">Runs</th>
                  <th className="text-right py-2 px-2">Rated</th>
                  <th className="text-right py-2 px-2">Success Rate</th>
                  <th className="text-right py-2 px-2">Mean Cost</th>
                  <th className="text-right py-2 px-2">Mean Latency</th>
                </tr>
              </thead>
              <tbody>
                {data.conditions.map((c) => (
                  <tr key={String(c.condition)} className="border-b border-[var(--border)]">
                    <td className="py-2 pr-4">{conditionBadge(String(c.condition))}</td>
                    <td className="text-right py-2 px-2">{String(c.n_runs)}</td>
                    <td className="text-right py-2 px-2">{String(c.n_ratings)}</td>
                    <td className="text-right py-2 px-2">
                      {c.success_rate != null
                        ? `${(Number(c.success_rate) * 100).toFixed(0)}%`
                        : '—'}
                    </td>
                    <td className="text-right py-2 px-2">
                      {c.mean_cost_usd != null ? `$${Number(c.mean_cost_usd).toFixed(4)}` : '—'}
                    </td>
                    <td className="text-right py-2 px-2">
                      {c.mean_latency_ms != null
                        ? `${(Number(c.mean_latency_ms) / 1000).toFixed(1)}s`
                        : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Dimension scores by condition */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Dimension Scores by Condition</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {SCORE_DIMENSIONS.map((dim) => {
            const scores = dimByDimension[dim];
            if (!scores || scores.length === 0) return null;
            return (
              <div key={dim}>
                <p className="text-xs font-medium mb-2">{dimLabel(dim)}</p>
                <div className="space-y-1">
                  {scores.map((s) => (
                    <div key={s.condition} className="flex items-center gap-2">
                      <span className="text-[10px] w-24 truncate">{s.condition}</span>
                      <div className="flex-1 h-4 rounded bg-[var(--border)] overflow-hidden relative">
                        <div
                          className={`h-full rounded ${
                            s.mean >= 2.5
                              ? 'bg-emerald-500'
                              : s.mean >= 1.5
                                ? 'bg-amber-500'
                                : 'bg-red-500'
                          }`}
                          style={{ width: `${(s.mean / 3) * 100}%` }}
                        />
                      </div>
                      <span className="text-[10px] w-8 text-right">{s.mean.toFixed(1)}</span>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </CardContent>
      </Card>

      {/* Failure tags */}
      {data.failure_tags.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Failure Tags</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-[var(--border)]">
                    <th className="text-left py-2 pr-4">Tag</th>
                    <th className="text-left py-2 px-2">Category</th>
                    <th className="text-right py-2 px-2">Count</th>
                  </tr>
                </thead>
                <tbody>
                  {data.failure_tags.map((ft) => (
                    <tr key={ft.tag} className="border-b border-[var(--border)]">
                      <td className="py-2 pr-4 font-mono">{ft.tag}</td>
                      <td className="py-2 px-2">
                        <Badge variant="outline" className="text-[10px]">
                          {ft.category}
                        </Badge>
                      </td>
                      <td className="text-right py-2 px-2">{ft.count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ── Agreement Tab (placeholder) ─────────────────────────────────────────────

function AgreementTab() {
  return (
    <Card>
      <CardContent className="py-12 text-center">
        <p className="text-[var(--muted-foreground)]">No multi-rater data available yet.</p>
        <p className="text-xs text-[var(--muted-foreground)] mt-2">
          When multiple raters score the same runs, inter-rater agreement analysis will appear here.
        </p>
      </CardContent>
    </Card>
  );
}

// ── Main Page ───────────────────────────────────────────────────────────────

export function EvalViewer() {
  const [activeTab, setActiveTab] = useState<Tab>('gallery');

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Eval Viewer</h1>
        <p className="text-sm text-[var(--muted-foreground)]">
          Browse evaluation runs, compare conditions, and review aggregate metrics.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-[var(--border)]">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.id
                ? 'border-[var(--primary)] text-[var(--foreground)]'
                : 'border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'gallery' && <GalleryTab />}
      {activeTab === 'comparison' && <ComparisonTab />}
      {activeTab === 'dashboard' && <DashboardTab />}
      {activeTab === 'agreement' && <AgreementTab />}
    </div>
  );
}
