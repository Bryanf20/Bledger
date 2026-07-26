import { useQuery } from "@tanstack/react-query";
import { fetchSyncHealth, fetchSyncStatus } from "../api/sync";

// Polls the local sync status for the topbar badge (Phase 2 §2.6). Cheap,
// user-authenticated, and every screen's badge shares one query (React
// Query dedupes by key), so mounting it in ScreenTopbar costs one poll app-
// wide. retry:false — a failed poll just means the branch is offline, which
// the badge renders as a state rather than an error to retry.
export function useSyncStatus() {
  return useQuery({
    queryKey: ["sync-status"],
    queryFn: fetchSyncStatus,
    refetchInterval: 15_000,
    staleTime: 10_000,
    retry: false,
  });
}

export function useSyncHealth() {
  return useQuery({
    queryKey: ["sync-health"],
    queryFn: fetchSyncHealth,
    staleTime: 10_000,
  });
}
