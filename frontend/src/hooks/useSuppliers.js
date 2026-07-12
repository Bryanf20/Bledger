import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createPurchase,
  createSupplier,
  fetchPurchases,
  fetchSuppliers,
  recordPurchasePayment,
  updateSupplier,
} from "../api/suppliers";

export function useSuppliers() {
  return useQuery({
    queryKey: ["suppliers"],
    queryFn: fetchSuppliers,
    staleTime: 30_000,
  });
}

export function usePurchases() {
  return useQuery({
    queryKey: ["purchases"],
    queryFn: fetchPurchases,
    staleTime: 30_000,
  });
}

export function useCreateSupplier() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createSupplier,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["suppliers"] }),
  });
}

export function useUpdateSupplier() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }) => updateSupplier(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["suppliers"] }),
  });
}

export function useCreatePurchase() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createPurchase,
    onSuccess: () => {
      // A purchase touches three things at once: the Purchase list
      // itself, the selected supplier's purchase_count/total_spent
      // annotations (SupplierViewSet.get_queryset()), and every line
      // item's Product.stock_level (PurchaseSerializer.create()) --
      // the last of which is the SAME "products" query key POS and
      // Inventory already share, so a restock here is reflected on
      // both of those screens too without extra wiring.
      queryClient.invalidateQueries({ queryKey: ["purchases"] });
      queryClient.invalidateQueries({ queryKey: ["suppliers"] });
      queryClient.invalidateQueries({ queryKey: ["products"] });
    },
  });
}

// Added this session -- records a payment installment against a
// partial/credit purchase (PurchaseViewSet.record_payment). Only
// invalidates ["purchases"]: a payment changes amount_paid/
// payment_status/balance_due and appends to that purchase's `payments`
// list, none of which touch Supplier.total_spent (Sum of
// total_amount, unaffected by amount_paid) or Product.stock_level (a
// payment never moves stock, unlike recording the purchase itself) --
// so unlike useCreatePurchase, there's no need to invalidate
// ["suppliers"] or ["products"] here.
export function useRecordPurchasePayment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ purchaseId, payload }) => recordPurchasePayment(purchaseId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["purchases"] }),
  });
}
