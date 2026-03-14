import { createGetQueryHook, createMutationHook } from './shared';
import { api } from '../client';
import type { CacheListResponse, CacheStats } from '../types';

export const useCacheStats = createGetQueryHook<CacheStats>(['memory', 'stats'], '/memory/stats');
export const useCacheEntries = createGetQueryHook<CacheListResponse>(['memory', 'entries'], '/memory/entries');
export const useClearCache = createMutationHook(() => api.delete('/memory/entries'), ['memory']);
