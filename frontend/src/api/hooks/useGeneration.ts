import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../client";
import type { GenerationRequest, GenerationListResponse, GeneratedImage, AuditDetail, FaceUploadResponse } from "../types";

export function useGenerations(offset = 0, limit = 20, status?: string) {
  return useQuery({
    queryKey: ["generations", offset, limit, status],
    queryFn: () => {
      const params = new URLSearchParams({
        offset: String(offset),
        limit: String(limit),
      });
      if (status && status !== "all") {
        params.set("status", status);
      }
      return api.get<GenerationListResponse>(`/generate?${params.toString()}`);
    },
  });
}

export function useGeneration(id: string) {
  return useQuery({
    queryKey: ["generations", id],
    queryFn: () => api.get<GenerationRequest>(`/generate/${id}`),
    enabled: !!id,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data && (data.status === "completed" || data.status === "failed")) return false;
      return 2000;
    },
  });
}

export function useCreateGeneration() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { input_text: string; figure_id?: string; face_id?: string }) =>
      api.post<GenerationRequest>("/generate", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["generations"] }),
  });
}

export function useUploadFace() {
  return useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      return api.upload<FaceUploadResponse>("/faces/upload", formData);
    },
  });
}

export function useDeleteGeneration() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`/generate/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["generations"] }),
  });
}

export function useGenerationImages(requestId: string) {
  return useQuery({
    queryKey: ["generations", requestId, "images"],
    queryFn: () => api.get<GeneratedImage[]>(`/generate/${requestId}/images`),
    enabled: !!requestId,
  });
}

export function useAuditDetail(id: string) {
  return useQuery({
    queryKey: ["audit", id],
    queryFn: () => api.get<AuditDetail>(`/generate/${id}/audit`),
    enabled: !!id,
  });
}

export function useRetryGeneration() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, fromStep }: { id: string; fromStep: string }) =>
      api.post<GenerationRequest>(`/generate/${id}/retry?from_step=${encodeURIComponent(fromStep)}`, {}),
    onSuccess: (_data, { id }) => {
      qc.invalidateQueries({ queryKey: ["generations"] });
      qc.invalidateQueries({ queryKey: ["audit", id] });
    },
  });
}
