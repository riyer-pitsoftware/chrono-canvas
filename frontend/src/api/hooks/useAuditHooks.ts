import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../client';
import { refetchUntilTerminal } from './useGenerationQueries';
import type { AuditDetail, AuditFeedback, AuditFeedbackListResponse } from '../types';

export function useAuditDetail(id: string) {
  return useQuery({
    queryKey: ['audit', id],
    queryFn: () => api.get<AuditDetail>(`/generate/${id}/audit`),
    enabled: !!id,
    refetchInterval: refetchUntilTerminal(),
  });
}

export function useAuditFeedback(requestId: string) {
  return useQuery({
    queryKey: ['audit-feedback', requestId],
    queryFn: () => api.get<AuditFeedbackListResponse>(`/generate/${requestId}/feedback`),
    enabled: !!requestId,
  });
}

export function useCreateFeedback() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      requestId,
      step_name,
      comment,
      author,
    }: {
      requestId: string;
      step_name: string;
      comment: string;
      author: string;
    }) =>
      api.post<AuditFeedback>(`/generate/${requestId}/feedback`, {
        step_name,
        comment,
        author,
      }),
    onSuccess: (_data, { requestId }) => {
      qc.invalidateQueries({ queryKey: ['audit-feedback', requestId] });
    },
  });
}
