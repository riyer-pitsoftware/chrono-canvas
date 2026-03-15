/**
 * Barrel re-export — all generation-related hooks.
 *
 * Consumers can keep importing from '@/api/hooks/useGeneration'
 * or import directly from the focused modules:
 *   useGenerationQueries, useGenerationMutations,
 *   useGenerationUploads, useAuditHooks
 */

export {
  // queries
  useGenerations,
  useGeneration,
  useGenerationImages,
  useCompletedGenerations,
  // helpers
  isTerminalStatus,
  refetchUntilTerminal,
} from './useGenerationQueries';

export {
  useCreateGeneration,
  useDeleteGeneration,
  useRetryGeneration,
} from './useGenerationMutations';

export { useUploadReferenceImage, useUploadFace } from './useGenerationUploads';

export { useAuditDetail, useAuditFeedback, useCreateFeedback } from './useAuditHooks';
