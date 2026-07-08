import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { discardHeldSale, fetchHeldSales, holdSale, restoreHeldSale } from "../api/pos";

export function useHeldSales() {
  return useQuery({
    queryKey: ["held-sales"],
    queryFn: fetchHeldSales,
  });
}

export function useHoldSale() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: holdSale,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["held-sales"] }),
  });
}

export function useRestoreHeldSale() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: restoreHeldSale,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["held-sales"] }),
  });
}

export function useDiscardHeldSale() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: discardHeldSale,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["held-sales"] }),
  });
}
