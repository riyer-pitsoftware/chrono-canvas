import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../client';

/**
 * Factory for simple GET query hooks (no params).
 * Usage: export const useAgents = createGetQueryHook<AgentListResponse>(['agents'], '/agents');
 */
export function createGetQueryHook<T>(queryKey: string[], path: string) {
  return function useGetQuery() {
    return useQuery({
      queryKey,
      queryFn: () => api.get<T>(path),
    });
  };
}

/**
 * Factory for detail query hooks that take an optional ID.
 * Usage: export const useEvalRun = createDetailQueryHook<EvalRunDetail>('eval', 'run', '/eval/runs');
 */
export function createDetailQueryHook<T>(keyPrefix: string, keyName: string, pathPrefix: string) {
  return function useDetailQuery(id: string | undefined) {
    return useQuery({
      queryKey: [keyPrefix, keyName, id],
      enabled: Boolean(id),
      queryFn: () => api.get<T>(`${pathPrefix}/${id}`),
    });
  };
}

/**
 * Factory for mutation hooks that invalidate a query key on success.
 * Usage: export const useClearCache = createMutationHook(() => api.delete('/memory/entries'), ['memory']);
 */
export function createMutationHook<TArgs = void, TResult = unknown>(
  mutationFn: (args: TArgs) => Promise<TResult>,
  invalidateKey: string[],
) {
  return function useMutationHook() {
    const queryClient = useQueryClient();
    return useMutation({
      mutationFn,
      onSuccess: () => {
        void queryClient.invalidateQueries({ queryKey: invalidateKey });
      },
    });
  };
}
