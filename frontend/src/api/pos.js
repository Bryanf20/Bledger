import apiClient from "./client";

// Verified against backend/apps/inventory/views.py (ProductViewSet) and
// backend/apps/sales/{views,serializers}.py (SaleSerializer,
// HeldSaleSerializer) in project knowledge.

// GET /products/ -- ProductViewSet has no SearchFilter/DjangoFilterBackend
// today, so this fetches the whole active branch+HQ catalogue in one
// page and POSScreen filters client-side. page_size=1000 is
// StandardResultsSetPagination's max -- fine for realistic SME
// catalogue sizes (tens to low hundreds of SKUs).
export async function fetchProducts() {
  const { data } = await apiClient.get("/products/", { params: { page_size: 1000 } });
  return data.results; // Product[]
}

// --- Server-side filtering variant (not wired up) ---
// Left commented rather than deleted: the moment ProductViewSet grows
// a SearchFilter/DjangoFilterBackend, swapping this in only means
// changing useProducts.js's queryFn/queryKey -- ProductGrid/POSScreen
// read the same shape either way.
//
// export async function fetchProductsFiltered({ search, category } = {}) {
//   const { data } = await apiClient.get("/products/", {
//     params: {
//       search: search || undefined,
//       category: category || undefined,
//       page_size: 25,
//     },
//   });
//   return data; // paginated: { count, next, previous, results }
// }

export async function createSale(payload) {
  const { data } = await apiClient.post("/sales/", payload);
  return data; // Sale -- includes reference (BLD-YYYY-NNNN) and line_items
}

export async function fetchHeldSales() {
  const { data } = await apiClient.get("/held-sales/");
  return data.results; // HeldSale[]
}

export async function holdSale({ label, cartData }) {
  const { data } = await apiClient.post("/held-sales/", { label, cart_data: cartData });
  return data;
}

export async function restoreHeldSale(id) {
  const { data } = await apiClient.post(`/held-sales/${id}/restore/`);
  return data; // cart_data verbatim: { items: [{ product, quantity }] }
}

export async function discardHeldSale(id) {
  await apiClient.delete(`/held-sales/${id}/`);
}
