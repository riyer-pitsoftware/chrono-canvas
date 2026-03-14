import { useQuery } from '@tanstack/react-query';
import { api } from '../client';
import { createDetailQueryHook, createGetQueryHook, createMutationHook } from './shared';
import type { DashboardData, EvalCase, EvalRunDetail, EvalRunSummary } from '../types';

export function useEvalRuns(condition?: string, caseId?: string, includeRejected?: boolean) {
  const params = new URLSearchParams();
  if (condition) params.set('condition', condition);
  if (caseId) params.set('case_id', caseId);
  if (includeRejected) params.set('include_rejected', 'true');
  const qs = params.toString();
  return useQuery({
    queryKey: ['eval', 'runs', condition, caseId, includeRejected],
    queryFn: () => api.get<EvalRunSummary[]>(`/eval/runs${qs ? `?${qs}` : ''}`),
  });
}

export const useEvalRun = createDetailQueryHook<EvalRunDetail>('eval', 'run', '/eval/runs');
export const useEvalCases = createGetQueryHook<EvalCase[]>(['eval', 'cases'], '/eval/cases');
export const useEvalCase = createDetailQueryHook<EvalCase>('eval', 'case', '/eval/cases');
export const useEvalDashboard = createGetQueryHook<DashboardData>(['eval', 'dashboard'], '/eval/dashboard');

export const useRejectEvalRun = createMutationHook(
  ({ runId, reason }: { runId: string; reason?: string }) =>
    api.post(`/eval/runs/${runId}/reject`, { reason }),
  ['eval'],
);

export const useUnrejectEvalRun = createMutationHook(
  (runId: string) => api.post(`/eval/runs/${runId}/unreject`, {}),
  ['eval'],
);
