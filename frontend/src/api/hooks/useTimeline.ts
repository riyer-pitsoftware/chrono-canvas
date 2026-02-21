import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { TimelineFigureListResponse } from "@/api/types";

export function useTimelineFigures(yearMin = -500, yearMax = 1700) {
  return useQuery({
    queryKey: ["timeline", yearMin, yearMax],
    queryFn: () => {
      const params = new URLSearchParams({
        year_min: String(yearMin),
        year_max: String(yearMax),
        limit: "300",
      });
      return api.get<TimelineFigureListResponse>(`/timeline/figures?${params}`);
    },
    staleTime: 5 * 60 * 1000,
  });
}
