import { useQuery } from "@tanstack/react-query";
import { fetchProducts } from "../api/pos";

// Client-side filtering (search + category) happens in POSScreen
// against this one fetched list -- see api/pos.js for why, and the commented
// fetchProductsFiltered() variant there for the server-side path.
export function useProducts() {
  return useQuery({
    queryKey: ["products"],
    queryFn: fetchProducts,
    staleTime: 30_000,
  });
}
