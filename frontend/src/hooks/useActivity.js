import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { fetchActivity } from "../api/activity";

// keepPreviousData: hold the current page's rows while the next page or a
// new filter loads, instead of flashing a loading state — same pattern as
// useSalesHistory.
export function useActivity(filters) {
  return useQuery({
    queryKey: ["activity", filters],
    queryFn: () => fetchActivity(filters),
    placeholderData: keepPreviousData,
    staleTime: 15_000,
  });
}
