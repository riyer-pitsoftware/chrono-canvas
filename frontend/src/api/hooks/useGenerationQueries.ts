import { useQuery, type Query } from '@tanstack/react-query';
import { api } from '../client';
import type {
  GenerationRequest,
  GenerationListResponse,
  GeneratedImage,
} from '../types';

// ── Status helpers ───────────────────────────────────────────────────────

const TERMINAL_STATUSES = new Set(['completed', 'failed']);

export function isTerminalStatus(status: string | undefined): boolean {
  return status !== undefined && TERMINAL_STATUSES.has(status);
}

export function refetchUntilTerminal<T extends { status?: string }>(
  initialMs = 2000,
  maxMs = 10000,
) {
  return (query: Query<T>) => {
    const data = query.state.data;
    if (data && isTerminalStatus(data.status)) return false;
    // Progressive backoff: start at initialMs, grow by 1s per fetch, cap at maxMs
    const fetchCount = query.state.dataUpdateCount ?? 0;
    return Math.min(initialMs + fetchCount * 1000, maxMs);
  };
}

// ── Query hooks ──────────────────────────────────────────────────────────

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

export function useGenerationImages(requestId: string) {
  return useQuery({
    queryKey: ['generations', requestId, 'images'],
    queryFn: () => api.get<GeneratedImage[]>(`/generate/${requestId}/images`),
    enabled: !!requestId,
  });
}

/**
 * Convenience hook that fetches only completed generations.
 * Uses the server-side status filter so no client-side filtering is needed.
 */
export function useCompletedGenerations(limit = 50) {
  return useQuery({
    queryKey: ['generations', 0, limit, 'completed'],
    queryFn: () => {
      const params = new URLSearchParams({
        offset: '0',
        limit: String(limit),
        status: 'completed',
      });
      return api.get<GenerationListResponse>(`/generate?${params.toString()}`);
    },
  });
}
