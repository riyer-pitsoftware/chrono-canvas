import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../client";
import type { CacheListResponse, CacheStats } from "../types";

export function useCacheStats() {
  return useQuery({
    queryKey: ["memory", "stats"],
    queryFn: () => api.get<CacheStats>("/memory/stats"),
  });
}

export function useCacheEntries() {
  return useQuery({
    queryKey: ["memory", "entries"],
    queryFn: () => api.get<CacheListResponse>("/memory/entries"),
  });
}

export function useClearCache() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => api.delete("/memory/entries"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["memory"] });
    },
  });
}
