import { useQuery } from "@tanstack/react-query";
import { fetchTemplates } from "../api/setup";

// GET /setup/templates/ is AllowAny and small (4 rows, each reading a
// cached fixture-file lookup server-side -- see
// apps.inventory.services.get_template_preview), so a longer staleTime
// than useSetupStatus is fine: this data is genuinely static during a
// single wizard run, and template *counts* only ever change on a
// backend deploy.
export function useProductTemplates() {
  return useQuery({
    queryKey: ["product-templates"],
    queryFn: fetchTemplates,
    staleTime: 5 * 60_000,
    retry: 1,
  });
}
