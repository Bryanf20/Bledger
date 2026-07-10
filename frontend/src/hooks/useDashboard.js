import { useQuery } from "@tanstack/react-query";
import {
  fetchDashboardSummary,
  fetchPaymentBreakdown,
  fetchSalesChart,
  fetchStockAlerts,
  fetchTopProducts,
} from "../api/dashboard";
import { fetchSales } from "../api/sales";

// Manager+ widgets -- `period` is one of "today" | "week" | "month"
// (DashboardScreen owns this as local state, shared across all four
// hooks below so the period toggle changes every widget at once, per
// the UI Design Reference's "Period toggle ... changes every widget
// on the screen simultaneously").

export function useDashboardSummary(period) {
  return useQuery({
    queryKey: ["dashboard", "summary", period],
    queryFn: () => fetchDashboardSummary(period),
    staleTime: 15_000,
  });
}

export function useTopProducts(period, limit = 5) {
  return useQuery({
    queryKey: ["dashboard", "top-products", period, limit],
    queryFn: () => fetchTopProducts(period, limit),
    staleTime: 15_000,
  });
}

export function usePaymentBreakdown(period) {
  return useQuery({
    queryKey: ["dashboard", "payment-breakdown", period],
    queryFn: () => fetchPaymentBreakdown(period),
    staleTime: 15_000,
  });
}

export function useSalesChart(period) {
  return useQuery({
    queryKey: ["dashboard", "sales-chart", period],
    queryFn: () => fetchSalesChart(period),
    staleTime: 15_000,
  });
}

// Cashier-visible widget -- not period-filtered (a live snapshot, per
// StockAlertView's docstring), so no `period` param and a shorter
// staleTime feels right for something a cashier at the till relies on.
export function useStockAlerts() {
  return useQuery({
    queryKey: ["dashboard", "stock-alerts"],
    queryFn: fetchStockAlerts,
    staleTime: 15_000,
  });
}

// Recent sales list (design doc B.5) has no dedicated dashboard
// endpoint -- there's no "last N sales" aggregate, just the same
// GET /sales/ SaleViewSet already backing SalesHistoryScreen, which
// defaults to -created_at (BaseModel.Meta.ordering), i.e. newest
// first, exactly what this widget needs. Deliberately NOT reusing
// hooks/useSalesHistory.js's cache key (that hook's key includes a
// `filters` object shaped for pagination/date-range filtering that
// this widget doesn't use) -- a plain unfiltered fetch, first page,
// sliced client-side to a handful of rows in RecentSalesList.
export function useRecentSales() {
  return useQuery({
    queryKey: ["dashboard", "recent-sales"],
    queryFn: () => fetchSales({}),
    staleTime: 15_000,
  });
}
