import { useQuery, useMutation, useQueryClient, type Query } from '@tanstack/react-query';
import { api } from '../client';
import type {
  GenerationRequest,
  GenerationListResponse,
  GeneratedImage,
  AuditDetail,
  FaceUploadResponse,
  AuditFeedback,
  AuditFeedbackListResponse,
} from '../types';

const TERMINAL_STATUSES = new Set(['completed', 'failed']);

export function isTerminalStatus(status: string | undefined): boolean {
  return status !== undefined && TERMINAL_STATUSES.has(status);
}

function refetchUntilTerminal<T extends { status?: string }>(intervalMs = 2000) {
  return (query: Query<T>) => {
    const data = query.state.data;
    if (data && isTerminalStatus(data.status)) return false;
    return intervalMs;
  };
}

export function useGenerations(offset = 0, limit = 20, status?: string) {
  return useQuery({
    queryKey: ['generations', offset, limit, status],
    queryFn: () => {
      const params = new URLSearchParams({
        offset: String(offset),
        limit: String(limit),
      });
      if (status && status !== 'all') {
        params.set('status', status);
      }
      return api.get<GenerationListResponse>(`/generate?${params.toString()}`);
    },
  });
}

export function useGeneration(id: string) {
  return useQuery({
    queryKey: ['generations', id],
    queryFn: () => api.get<GenerationRequest>(`/generate/${id}`),
    enabled: !!id,
    refetchInterval: refetchUntilTerminal(),
  });
}

export function useCreateGeneration() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      input_text: string;
      figure_id?: string;
      face_id?: string;
      run_type?: string;
      ref_image_id?: string;
      ref_image_ids?: string[];
      config?: Record<string, unknown>;
    }) => api.post<GenerationRequest>('/generate', data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['generations'] }),
  });
}

export function useUploadReferenceImage() {
  return useMutation({
    mutationFn: (params: { file: File; refType?: string; description?: string }) => {
      const formData = new FormData();
      formData.append('file', params.file);
      const queryParams = new URLSearchParams();
      if (params.refType) queryParams.set('ref_type', params.refType);
      if (params.description) queryParams.set('description', params.description);
      const qs = queryParams.toString();
      return api.upload<{ ref_id: string; file_path: string; mime_type: string }>(
        `/reference-images/upload${qs ? `?${qs}` : ''}`,
        formData,
      );
    },
  });
}

export function useUploadFace() {
  return useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      return api.upload<FaceUploadResponse>('/faces/upload', formData);
    },
  });
}

export function useDeleteGeneration() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`/generate/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['generations'] }),
  });
}

export function useGenerationImages(requestId: string) {
  return useQuery({
    queryKey: ['generations', requestId, 'images'],
    queryFn: () => api.get<GeneratedImage[]>(`/generate/${requestId}/images`),
    enabled: !!requestId,
  });
}

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

export function useRetryGeneration() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, fromStep }: { id: string; fromStep: string }) =>
      api.post<GenerationRequest>(
        `/generate/${id}/retry?from_step=${encodeURIComponent(fromStep)}`,
        {},
      ),
    onSuccess: (_data, { id }) => {
      qc.invalidateQueries({ queryKey: ['generations'] });
      qc.invalidateQueries({ queryKey: ['audit', id] });
    },
  });
}
