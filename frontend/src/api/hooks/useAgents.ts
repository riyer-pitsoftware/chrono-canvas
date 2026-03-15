import { createGetQueryHook } from './shared';
import type { AgentListResponse, LLMAvailability, CostSummary } from '../types';

export const useAgents = createGetQueryHook<AgentListResponse>(['agents'], '/agents');
export const useLLMStatus = createGetQueryHook<LLMAvailability>(
  ['agents', 'llm-status'],
  '/agents/llm-status',
);
export const useCostSummary = createGetQueryHook<CostSummary>(['agents', 'costs'], '/agents/costs');
