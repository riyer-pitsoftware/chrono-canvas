import { useQuery } from "@tanstack/react-query";
import { api } from "../client";

interface HealthResponse {
  status: string;
  service: string;
  hackathon_mode: boolean;
}

export function useHackathonMode() {
  const { data } = useQuery({
    queryKey: ["health"],
    queryFn: () => api.get<HealthResponse>("/health"),
    staleTime: Infinity, // Cache forever — value won't change at runtime
    refetchOnWindowFocus: false,
  });
  return data?.hackathon_mode ?? false;
}
