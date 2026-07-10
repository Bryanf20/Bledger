import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { fetchSales } from "../api/sales";

// Separate from hooks/useSale.js (single-sale fetch/void for
// ReceiptScreen) -- this is the paginated, filterable list backing
// SalesHistoryScreen. Kept as its own file rather than folded into
// useSale.js, matching how POS's list concern (useProducts.js) and
// single-item concern (useSale.js) already live apart.
//
// placeholderData: keepPreviousData keeps the previous page/filter's
// rows on screen while a new combination loads, instead of flashing
// back to a loading state on every filter click or page turn.
export function useSalesHistory(filters) {
  return useQuery({
    queryKey: ["sales", "history", filters],
    queryFn: () => fetchSales(filters),
    placeholderData: keepPreviousData,
  });
}
