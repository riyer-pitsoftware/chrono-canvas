import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../client';
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

export function useEvalRun(runId: string | undefined) {
  return useQuery({
    queryKey: ['eval', 'run', runId],
    enabled: Boolean(runId),
    queryFn: () => api.get<EvalRunDetail>(`/eval/runs/${runId}`),
  });
}

export function useEvalCases() {
  return useQuery({
    queryKey: ['eval', 'cases'],
    queryFn: () => api.get<EvalCase[]>('/eval/cases'),
  });
}

export function useEvalCase(caseId: string | undefined) {
  return useQuery({
    queryKey: ['eval', 'case', caseId],
    enabled: Boolean(caseId),
    queryFn: () => api.get<EvalCase>(`/eval/cases/${caseId}`),
  });
}

export function useEvalDashboard() {
  return useQuery({
    queryKey: ['eval', 'dashboard'],
    queryFn: () => api.get<DashboardData>('/eval/dashboard'),
  });
}

export function useRejectEvalRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ runId, reason }: { runId: string; reason?: string }) =>
      api.post(`/eval/runs/${runId}/reject`, { reason }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['eval'] });
    },
  });
}

export function useUnrejectEvalRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (runId: string) => api.post(`/eval/runs/${runId}/unreject`, {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['eval'] });
    },
  });
}
