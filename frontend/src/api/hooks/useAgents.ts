import { useQuery } from '@tanstack/react-query';
import { api } from '../client';
import type { AgentListResponse, LLMAvailability, CostSummary } from '../types';

export function useAgents() {
  return useQuery({
    queryKey: ['agents'],
    queryFn: () => api.get<AgentListResponse>('/agents'),
  });
}

export function useLLMStatus() {
  return useQuery({
    queryKey: ['agents', 'llm-status'],
    queryFn: () => api.get<LLMAvailability>('/agents/llm-status'),
  });
}

export function useCostSummary() {
  return useQuery({
    queryKey: ['agents', 'costs'],
    queryFn: () => api.get<CostSummary>('/agents/costs'),
  });
}
