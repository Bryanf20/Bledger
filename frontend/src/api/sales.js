import apiClient from "./client";

// Sale-detail/receipt/history endpoints, verified against
// backend/apps/sales/{views,serializers}.py in project knowledge.
// createSale/held-sale endpoints already live in api/pos.js -- this
// module covers what ReceiptScreen and SalesHistoryScreen need
// instead of overloading pos.js with unrelated concerns.
//
//   GET  /sales/{id}/          -> Sale (SaleSerializer -- same shape
//     POST /sales/ returns: id, reference, cashier, cashier_name,
//     payment_method, momo_reference, momo_confirmed, subtotal,
//     tax_amount, total_amount, amount_tendered, status, voided_by,
//     void_reason, voided_at, line_items, created_at). Cashiers only
//     ever see their own sales here (SaleViewSet.get_queryset()) --
//     any other cashier's sale id 404s, not 403.
//   GET  /sales/                -> paginated { count, next, previous,
//     results: Sale[] }. StandardResultsSetPagination: page_size=25,
//     max 100. Filtering added this session (SalesHistoryScreen --
//     not one of the original 7 design-doc screens): date_from /
//     date_to (YYYY-MM-DD, inclusive), payment_method, status,
//     search (matches against `reference`). All optional, all
//     silently ignored server-side if malformed -- never 400s.
//   GET  /sales/{id}/receipt/  -> PDF bytes (application/pdf). 503 if
//     apps.printing.pdf_backend.PrinterDependencyMissing is raised.
//   POST /sales/{id}/void/     { void_reason } -> Sale, status
//     "voided" (IsManagerOrOwner server-side on this action).

export async function fetchSale(id) {
  const { data } = await apiClient.get(`/sales/${id}/`);
  return data; // Sale
}

export async function fetchSales(filters = {}) {
  const { data } = await apiClient.get("/sales/", {
    params: {
      page: filters.page || undefined,
      date_from: filters.dateFrom || undefined,
      date_to: filters.dateTo || undefined,
      payment_method: filters.paymentMethod || undefined,
      status: filters.status || undefined,
      search: filters.search || undefined,
    },
  });
  return data; // { count, next, previous, results: Sale[] }
}

export async function fetchReceiptPdf(id) {
  const response = await apiClient.get(`/sales/${id}/receipt/`, {
    responseType: "blob",
  });
  return response.data; // Blob (application/pdf)
}

export async function voidSale(id, voidReason) {
  const { data } = await apiClient.post(`/sales/${id}/void/`, { void_reason: voidReason });
  return data; // Sale
}
