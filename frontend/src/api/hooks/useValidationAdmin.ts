import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../client";
import type {
  ValidationQueueResponse,
  ValidationRule,
  ValidationRulesConfig,
} from "../types";

export function useValidationRules() {
  return useQuery({
    queryKey: ["admin", "validation-rules"],
    queryFn: () => api.get<ValidationRulesConfig>("/admin/validation/rules"),
  });
}

export function useUpdateValidationRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, weight, enabled }: { id: string; weight: number; enabled?: boolean }) =>
      api.put<ValidationRule>(`/admin/validation/rules/${id}`, { weight, enabled }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "validation-rules"] });
    },
  });
}

export function useUpdatePassThreshold() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (pass_threshold: number) =>
      api.put<{ pass_threshold: number }>("/admin/validation/threshold", { pass_threshold }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "validation-rules"] });
    },
  });
}

export function useValidationQueue(skip = 0, limit = 50) {
  return useQuery({
    queryKey: ["admin", "validation-queue", skip, limit],
    queryFn: () =>
      api.get<ValidationQueueResponse>(`/admin/validation/queue?skip=${skip}&limit=${limit}`),
  });
}

export function useAcceptValidation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ requestId, notes }: { requestId: string; notes?: string }) =>
      api.post(`/admin/validation/${requestId}/accept`, { notes: notes ?? null }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "validation-queue"] });
    },
  });
}

export function useRejectValidation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ requestId, notes }: { requestId: string; notes?: string }) =>
      api.post(`/admin/validation/${requestId}/reject`, { notes: notes ?? null }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "validation-queue"] });
    },
  });
}
