import { useMemo, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useNavigation } from '@/stores/navigation';
import {
  useValidationQueue,
  useValidationReviewItem,
  useAcceptValidation,
  useRejectValidation,
  useFlagValidation,
} from '@/api/hooks/useValidationAdmin';
import { useAuditDetail } from '@/api/hooks/useGeneration';
import type { ValidationQueueItem } from '@/api/types';

function formatNotes(action: string, score: number | null, notes: string) {
  const parts = [];
  if (score !== null) parts.push(`human_score=${Math.round(score)}`);
  parts.push(`action=${action}`);
  if (notes.trim()) parts.push(`notes=${notes.trim()}`);
  return parts.join('; ');
}

function resolveOutputUrl(filePath: unknown): string | null {
  if (typeof filePath !== 'string' || !filePath.length) return null;
  const outputIndex = filePath.indexOf('/output/');
  if (outputIndex >= 0) {
    return filePath.slice(outputIndex);
  }
  if (filePath.startsWith('/')) {
    return filePath.replace(/^.*output\//, '/output/');
  }
  if (filePath.startsWith('http')) return filePath;
  return `/output/${filePath}`;
}

function CategoryList({ item }: { item: ValidationQueueItem }) {
  return (
    <div className="space-y-2">
      {item.categories.map((cat) => (
        <div
          key={cat.category}
          className="border border-[var(--border)] rounded-md p-3 flex items-center justify-between"
        >
          <div>
            <p className="text-sm font-medium capitalize">{cat.category.replace(/_/g, ' ')}</p>
            {cat.details && <p className="text-xs text-[var(--muted-foreground)]">{cat.details}</p>}
          </div>
          <div className="text-right">
            <p
              className={`text-xl font-bold ${cat.score >= 70 ? 'text-green-500' : cat.score >= 50 ? 'text-amber-500' : 'text-red-500'}`}
            >
              {Math.round(cat.score)}
            </p>
            <Badge variant={cat.passed ? 'success' : 'destructive'}>
              {cat.passed ? 'Pass' : 'Fail'}
            </Badge>
          </div>
        </div>
      ))}
    </div>
  );
}

export function Review({ requestId }: { requestId: string }) {
  const [notes, setNotes] = useState('');
  const [humanScore, setHumanScore] = useState<number | null>(null);
  const [sessionReviewed, setSessionReviewed] = useState(0);
  const [pendingAction, setPendingAction] = useState<'accept' | 'reject' | 'flag' | null>(null);

  const { navigate } = useNavigation();
  const queueQuery = useValidationQueue();
  const reviewItem = useValidationReviewItem(requestId);
  const auditDetail = useAuditDetail(requestId);
  const acceptMutation = useAcceptValidation();
  const rejectMutation = useRejectValidation();
  const flagMutation = useFlagValidation();

  const queueIds = queueQuery.data?.items.map((i) => i.request_id) ?? [];
  const currentIndex = queueIds.findIndex((id) => id === requestId);
  const previousId = currentIndex > 0 ? queueIds[currentIndex - 1] : undefined;
  const nextId =
    currentIndex >= 0 && currentIndex < queueIds.length - 1
      ? queueIds[currentIndex + 1]
      : undefined;

  const faceSearchUrl = useMemo(() => {
    const trace = auditDetail.data?.agent_trace?.find(
      (entry) => entry.agent === 'face_search' && entry.local_path,
    );
    if (!trace) return null;
    return resolveOutputUrl(trace.local_path);
  }, [auditDetail.data?.agent_trace]);

  const generationPrompt = auditDetail.data?.generated_prompt ?? auditDetail.data?.input_text ?? '';

  const overallScore = reviewItem.data?.overall_score ?? null;

  const handleNavigate = (target?: string) => {
    if (target) {
      navigate(`/review/${target}`);
    } else {
      navigate('/admin');
    }
  };

  const afterDecision = () => {
    setSessionReviewed((count) => count + 1);
    setNotes('');
    setHumanScore(null);
    if (nextId) {
      handleNavigate(nextId);
    } else {
      navigate('/admin');
    }
  };

  const performAction = (action: 'accept' | 'reject' | 'flag') => {
    if (!requestId) return;
    setPendingAction(action);
    const payload = {
      requestId,
      notes: formatNotes(action, humanScore, notes),
    };
    const onSettled = () => setPendingAction(null);
    const onSuccess = () => afterDecision();
    if (action === 'accept') {
      acceptMutation.mutate(payload, { onSuccess, onSettled });
    } else if (action === 'reject') {
      rejectMutation.mutate(payload, { onSuccess, onSettled });
    } else {
      flagMutation.mutate(payload, { onSuccess, onSettled });
    }
  };

  const isLoading = reviewItem.isLoading || auditDetail.isLoading;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold">Human Review</h2>
          {overallScore !== null && (
            <p className="text-sm text-[var(--muted-foreground)]">
              Model score: <span className="font-semibold">{overallScore}</span>
            </p>
          )}
          <p className="text-xs text-[var(--muted-foreground)]">
            Reviewed this session: {sessionReviewed} / 10 minimum
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate('/admin')}>
            Back to queue
          </Button>
          <Button
            variant="outline"
            disabled={!previousId}
            onClick={() => handleNavigate(previousId)}
          >
            Previous
          </Button>
          <Button variant="outline" disabled={!nextId} onClick={() => handleNavigate(nextId)}>
            Next
          </Button>
        </div>
      </div>

      {isLoading && <p className="text-sm text-[var(--muted-foreground)]">Loading review data…</p>}
      {!isLoading && reviewItem.data == null && (
        <p className="text-sm text-[var(--destructive)]">Unable to load review item.</p>
      )}

      {reviewItem.data && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          <Card className="xl:col-span-2">
            <CardHeader>
              <CardTitle>Image & Metadata</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {reviewItem.data.image_url ? (
                <img
                  src={reviewItem.data.image_url}
                  alt="Generated portrait"
                  className="w-full max-h-[480px] object-contain rounded-md border border-[var(--border)] bg-[var(--background)]"
                />
              ) : (
                <div className="h-64 border border-dashed border-[var(--border)] rounded-md flex items-center justify-center text-sm text-[var(--muted-foreground)]">
                  No generated image available
                </div>
              )}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-[var(--muted-foreground)] text-xs uppercase">Figure</p>
                  <p className="font-medium">{reviewItem.data.figure_name ?? 'Unknown'}</p>
                </div>
                <div>
                  <p className="text-[var(--muted-foreground)] text-xs uppercase">Requested</p>
                  <p className="line-clamp-2">{reviewItem.data.input_text}</p>
                </div>
                <div>
                  <p className="text-[var(--muted-foreground)] text-xs uppercase">Requested At</p>
                  <p>{new Date(reviewItem.data.created_at).toLocaleString()}</p>
                </div>
                {faceSearchUrl && (
                  <div>
                    <p className="text-[var(--muted-foreground)] text-xs uppercase">
                      Reference Face
                    </p>
                    <img
                      src={faceSearchUrl}
                      alt="Face search reference"
                      className="w-32 h-32 object-cover border border-[var(--border)] rounded-md mt-1"
                    />
                  </div>
                )}
              </div>
              <div>
                <p className="text-xs text-[var(--muted-foreground)] uppercase mb-1">LLM Prompt</p>
                <pre className="text-xs bg-[var(--muted)] rounded-md p-3 overflow-auto max-h-48 whitespace-pre-wrap">
                  {generationPrompt || 'Prompt unavailable'}
                </pre>
              </div>
              <div className="border-t border-[var(--border)] pt-4 space-y-3">
                <p className="text-sm font-medium">Human Feedback</p>
                <Input
                  type="number"
                  min={0}
                  max={100}
                  placeholder="Human score (0-100)"
                  value={humanScore ?? ''}
                  onChange={(e) => {
                    const val = e.target.value;
                    setHumanScore(val === '' ? null : Number(val));
                  }}
                />
                <textarea
                  rows={4}
                  className="w-full border border-[var(--border)] rounded-md bg-[var(--background)] p-3 text-sm"
                  placeholder="Add natural language feedback…"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                />
                <div className="flex flex-wrap gap-2">
                  <Button
                    className="bg-green-600 hover:bg-green-700 text-white"
                    disabled={pendingAction === 'accept'}
                    onClick={() => performAction('accept')}
                  >
                    {pendingAction === 'accept' ? 'Accepting…' : 'Accept'}
                  </Button>
                  <Button
                    variant="outline"
                    className="text-red-500 border-red-500 hover:bg-red-50"
                    disabled={pendingAction === 'reject'}
                    onClick={() => performAction('reject')}
                  >
                    {pendingAction === 'reject' ? 'Rejecting…' : 'Reject'}
                  </Button>
                  <Button
                    variant="secondary"
                    disabled={pendingAction === 'flag'}
                    onClick={() => performAction('flag')}
                  >
                    {pendingAction === 'flag' ? 'Flagging…' : 'Flag for follow-up'}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Validation Categories</CardTitle>
              </CardHeader>
              <CardContent>
                <CategoryList item={reviewItem.data} />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Audit Context</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <p>
                  Request ID: <code className="text-xs">{requestId}</code>
                </p>
                <Button variant="outline" size="sm" onClick={() => navigate(`/audit/${requestId}`)}>
                  Open full audit
                </Button>
                {auditDetail.data?.current_agent && (
                  <p className="text-xs text-[var(--muted-foreground)]">
                    Last agent:{' '}
                    <span className="font-medium">{auditDetail.data.current_agent}</span>
                  </p>
                )}
                {auditDetail.data?.total_cost && (
                  <p className="text-xs text-[var(--muted-foreground)]">
                    Cost: ${auditDetail.data.total_cost.toFixed(4)} · Duration:{' '}
                    {(auditDetail.data.total_duration_ms / 1000).toFixed(1)}s
                  </p>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
