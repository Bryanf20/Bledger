import { useQuery } from "@tanstack/react-query";
import { fetchHQSummary } from "../api/hq";

// Cross-branch HQ summary (Phase 2 §2.4/§2.6). Owner-only; keyed by period so
// switching Today/Week/Month caches each independently.
export function useHQSummary(period) {
  return useQuery({
    queryKey: ["hq-summary", period],
    queryFn: () => fetchHQSummary(period),
    staleTime: 30_000,
  });
}
