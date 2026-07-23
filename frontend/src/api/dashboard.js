import apiClient from "./client";

// Verified against backend/apps/dashboard/{views,services,reports_views}.py
// in project knowledge -- SalesSummaryView, TopProductsView,
// PaymentBreakdownView, SalesChartView, StockAlertView, SalesReportView.
//
//   GET /dashboard/summary/?period=today|week|month           Manager+
//   GET /dashboard/top-products/?period=...&limit=10           Manager+
//   GET /dashboard/payment-breakdown/?period=...                Manager+
//   GET /dashboard/sales-chart/?period=...                      Manager+
//   GET /dashboard/stock-alerts/                                All roles
//     (IsCashierOrAbove -- the one widget cashiers can call; not
//     period-filtered, a live snapshot per the view's docstring)
//   GET /reports/sales/?period=...&export=csv|pdf               Manager+
//     -- `export`, not `format`: DRF reserves `?format=` for content
//     negotiation and would 404 before the view body runs (same
//     gotcha as apps.dashboard's other endpoints, see project's
//     running "Debugged / caught" list).
//
// resolve_period() defaults anything missing/unrecognized to "today"
// server-side, so these never need to guard against a bad period
// value client-side either.

export async function fetchDashboardSummary(period) {
  const { data } = await apiClient.get("/dashboard/summary/", { params: { period } });
  return data; // { period, revenue, revenue_change_pct, transaction_count,
  // transaction_count_change, average_sale, top_product_name }
}

export async function fetchTopProducts(period, limit = 5) {
  const { data } = await apiClient.get("/dashboard/top-products/", { params: { period, limit } });
  return data; // TopProduct[] -- { rank, product_id, product_name, units_sold, revenue }
}

export async function fetchPaymentBreakdown(period) {
  const { data } = await apiClient.get("/dashboard/payment-breakdown/", { params: { period } });
  return data; // { payment_method, revenue, transaction_count }[] -- only methods
  // with at least one sale in the period are present; missing methods
  // are treated as zero client-side (see PaymentBreakdownCard).
}

export async function fetchSalesChart(period) {
  const { data } = await apiClient.get("/dashboard/sales-chart/", { params: { period } });
  return data; // { label, revenue }[] -- hourly buckets for "today", daily otherwise
}

export async function fetchStockAlerts() {
  const { data } = await apiClient.get("/dashboard/stock-alerts/");
  return data; // { product_id, product_name, stock_level, low_stock_threshold, status }[]
}

// Phase 2 §3.4 / §7A.6 reporting — all Manager+.
export async function fetchVarianceSummary(period) {
  const { data } = await apiClient.get("/dashboard/variance-summary/", { params: { period } });
  return data; // { period, total_surplus, total_discount, net_variance, per_cashier[] }
}

export async function fetchMarginSummary(period) {
  const { data } = await apiClient.get("/dashboard/margin-summary/", { params: { period } });
  return data; // { revenue, cogs, gross_margin, margin_pct, total_revenue, uncosted_revenue }
}

export async function fetchStockValuation() {
  const { data } = await apiClient.get("/dashboard/stock-valuation/");
  return data; // { stock_value, costed_products, cost_unknown_products }
}

export async function fetchLowMargin() {
  const { data } = await apiClient.get("/dashboard/low-margin/");
  return data; // { threshold_pct, products[] }
}

// Brokered / commission-sale gains for the period (§7C.4 / step 8f).
export async function fetchBrokeredSummary(period) {
  const { data } = await apiClient.get("/dashboard/brokered-summary/", { params: { period } });
  return data; // { period, gain, revenue, cost, line_count }
}

// Customers aged-debt (Phase 2 §4.5).
export async function fetchAgedDebtReport() {
  const { data } = await apiClient.get("/customers/aged-debt/");
  return data; // AgedDebtRow[]
}

// Blob download for the toolbar's Export control -- same
// responseType: "blob" + downloadBlob() pattern as
// ReceiptScreen's fetchReceiptPdf/handleDownloadPdf.
export async function fetchSalesReport(period, exportFormat) {
  const response = await apiClient.get("/reports/sales/", {
    params: { period, export: exportFormat },
    responseType: "blob",
  });
  return response.data; // Blob (text/csv or application/pdf)
}
