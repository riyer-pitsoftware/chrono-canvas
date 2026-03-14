import { useMutation } from '@tanstack/react-query';
import { api } from '../client';
import type { FaceUploadResponse } from '../types';

export function useUploadReferenceImage() {
  return useMutation({
    mutationFn: (params: { file: File; refType?: string; description?: string }) => {
      const formData = new FormData();
      formData.append('file', params.file);
      const queryParams = new URLSearchParams();
      if (params.refType) queryParams.set('ref_type', params.refType);
      if (params.description) queryParams.set('description', params.description);
      const qs = queryParams.toString();
      return api.upload<{ ref_id: string; file_path: string; mime_type: string }>(
        `/reference-images/upload${qs ? `?${qs}` : ''}`,
        formData,
      );
    },
  });
}

export function useUploadFace() {
  return useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      return api.upload<FaceUploadResponse>('/faces/upload', formData);
    },
  });
}
