import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchSale, voidSale } from "../api/sales";

export function useSale(id) {
  return useQuery({
    queryKey: ["sale", id],
    queryFn: () => fetchSale(id),
    enabled: Boolean(id),
  });
}

export function useVoidSale(id) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (voidReason) => voidSale(id, voidReason),
    onSuccess: (sale) => {
      queryClient.setQueryData(["sale", id], sale);
      // Voiding restores stock server-side (VoidSaleSerializer.save())
      // -- keep the POS product list in sync the same way sale
      // creation already invalidates it (see useCreateSale.js).
      queryClient.invalidateQueries({ queryKey: ["products"] });
    },
  });
}
