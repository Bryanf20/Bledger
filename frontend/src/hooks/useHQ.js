import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchHQSummary, provisionBranch } from "../api/hq";

// Cross-branch HQ summary (Phase 2 §2.4/§2.6). Owner-only; keyed by period so
// switching Today/Week/Month caches each independently.
export function useHQSummary(period) {
  return useQuery({
    queryKey: ["hq-summary", period],
    queryFn: () => fetchHQSummary(period),
    staleTime: 30_000,
  });
}

// Provision a new branch (owner). On success the HQ summary gains the branch,
// so invalidate it. Returns the response incl. the one-time enrolment code.
export function useProvisionBranch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: provisionBranch,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hq-summary"] }),
  });
}
