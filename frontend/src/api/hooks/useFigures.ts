import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../client';
import type { Figure, FigureListResponse } from '../types';

export function useFigures(search?: string, offset = 0, limit = 50) {
  return useQuery({
    queryKey: ['figures', search, offset, limit],
    queryFn: () => {
      const params = new URLSearchParams({ offset: String(offset), limit: String(limit) });
      if (search) params.set('search', search);
      return api.get<FigureListResponse>(`/figures?${params}`);
    },
  });
}

export function useFigure(id: string) {
  return useQuery({
    queryKey: ['figures', id],
    queryFn: () => api.get<Figure>(`/figures/${id}`),
    enabled: !!id,
  });
}

export function useCreateFigure() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<Figure>) => api.post<Figure>('/figures', data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['figures'] }),
  });
}
