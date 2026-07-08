import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createSale } from "../api/pos";

export function useCreateSale() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createSale,
    onSuccess: () => {
      // Sale creation decrements Product.stock_level server-side --
      // invalidate so the grid's stock numbers are correct after
      // "New sale" without a manual refetch call at every use site.
      queryClient.invalidateQueries({ queryKey: ["products"] });
    },
  });
}
