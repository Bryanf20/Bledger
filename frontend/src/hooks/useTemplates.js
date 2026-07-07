import { useQuery } from "@tanstack/react-query";
import { fetchTemplates } from "../api/setup";

// GET /setup/templates/ is AllowAny and reads four small fixture files
// server-side -- cheap, and only needed once per wizard session, so a
// long staleTime is fine.
export function useTemplates() {
  return useQuery({
    queryKey: ["setup-templates"],
    queryFn: fetchTemplates,
    staleTime: 5 * 60_000,
    retry: false,
  });
}
