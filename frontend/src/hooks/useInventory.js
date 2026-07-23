import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createCategory,
  createProduct,
  createStockAdjustment,
  deactivateProduct,
  fetchCategories,
  fetchProducts,
  reactivateProduct,
  updateProduct,
} from "../api/inventory";

// Deliberately the SAME "products" query key as hooks/useProducts.js
// (POS) -- both screens read the identical GET
// /products/?page_size=1000 shape. Sharing the key means a sale on
// POS (which invalidates ["products"] on stock decrement) and a stock
// adjustment/edit made here both keep the other screen's cached list
// correct without extra cross-feature wiring.
export function useInventoryProducts() {
  return useQuery({
    queryKey: ["products"],
    queryFn: fetchProducts,
    staleTime: 30_000,
  });
}

export function useCategories() {
  return useQuery({
    queryKey: ["categories"],
    queryFn: fetchCategories,
    staleTime: 60_000,
  });
}

export function useCreateCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createCategory,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["categories"] }),
  });
}

export function useCreateProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createProduct,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["products"] }),
  });
}

export function useUpdateProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }) => updateProduct(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["products"] }),
  });
}

export function useDeactivateProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deactivateProduct,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["products"] }),
  });
}

export function useReactivateProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: reactivateProduct,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["products"] }),
  });
}

export function useCreateStockAdjustment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createStockAdjustment,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
      // A damage/expiry removal can book a Losses/Damage expense and logs
      // activity (step 8d) — refresh those views too so a booked loss
      // shows up immediately.
      queryClient.invalidateQueries({ queryKey: ["cashbook"] });
      queryClient.invalidateQueries({ queryKey: ["pnl"] });
      queryClient.invalidateQueries({ queryKey: ["activity"] });
    },
  });
}
