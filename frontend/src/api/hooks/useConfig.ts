import { useQuery } from '@tanstack/react-query';
import { api } from '../client';

interface ServiceMap {
  llm: Record<string, boolean>;
  image: Record<string, boolean>;
  search: Record<string, boolean>;
  tts: boolean;
  facefusion: boolean;
}

interface HealthResponse {
  status: string;
  service: string;
  deployment_mode: 'gcp' | 'local' | 'hybrid';
  hackathon_mode: boolean;
  services: ServiceMap;
}

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => api.get<HealthResponse>('/health'),
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
}

export function useDeploymentMode() {
  const { data } = useHealth();
  return data?.deployment_mode ?? 'hybrid';
}

export function useHackathonMode() {
  const { data } = useHealth();
  return data?.hackathon_mode ?? false;
}

export function useServiceAvailability() {
  const { data } = useHealth();
  return data?.services ?? null;
}

interface ConfigValidation {
  valid: boolean;
  errors: Array<{ channel: string; provider: string; error: string }>;
}

export async function validateConfig(payload: Record<string, unknown>): Promise<ConfigValidation> {
  return api.post<ConfigValidation>('/config/validate', payload);
}
