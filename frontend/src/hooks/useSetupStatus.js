import { useQuery } from "@tanstack/react-query";
import { fetchSetupStatus } from "../api/auth";

// GET /setup/status/ is AllowAny and cheap (a single .exists() query),
// so a short staleTime is fine -- this just needs to gate the very
// first route decision, not stay live-synced.
export function useSetupStatus() {
  return useQuery({
    queryKey: ["setup-status"],
    queryFn: fetchSetupStatus,
    staleTime: 60_000,
    retry: false,
  });
}
