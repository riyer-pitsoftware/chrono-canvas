import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../client';
import type { GenerationRequest } from '../types';

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

export function useDeleteGeneration() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`/generate/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['generations'] }),
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
