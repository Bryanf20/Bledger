import apiClient from "./client";

// Verified against backend/apps/inventory/{views,serializers}.py in
// project knowledge -- ProductViewSet, CategoryViewSet,
// StockAdjustmentViewSet. fetchProducts() mirrors api/pos.js's
// fetchProducts() (same GET /products/?page_size=1000, same reasoning:
// ProductViewSet has no SearchFilter/DjangoFilterBackend today, so
// this screen filters client-side same as POS) -- kept as its own
// small function here rather than imported from api/pos.js, since
// api/pos.js is POS-owned per the project's feature-based api/ file
// convention (api/sales.js, api/setup.js, this file).

export async function fetchProducts() {
  const { data } = await apiClient.get("/products/", { params: { page_size: 1000 } });
  return data.results; // Product[]
}

export async function fetchCategories() {
  const { data } = await apiClient.get("/categories/", { params: { page_size: 200 } });
  return data.results; // Category[]
}

export async function createCategory(payload) {
  const { data } = await apiClient.post("/categories/", payload);
  return data; // Category
}

// stock_level is read_only on ProductSerializer -- new products always
// start at 0 and can only gain stock through a StockAdjustmentSerializer
// POST (its create() atomically owns Product.stock_level, per
// apps/inventory/serializers.py's module docstring). The form surfaces
// this as a note rather than a stock_level input field.
export async function createProduct(payload) {
  const { data } = await apiClient.post("/products/", payload);
  return data; // Product
}

export async function updateProduct(id, payload) {
  const { data } = await apiClient.patch(`/products/${id}/`, payload);
  return data; // Product
}

// DELETE deactivates (is_active=false) rather than deleting -- see
// ProductViewSet.perform_destroy(). Reactivation is a plain PATCH.
export async function deactivateProduct(id) {
  await apiClient.delete(`/products/${id}/`);
}

export async function reactivateProduct(id) {
  const { data } = await apiClient.patch(`/products/${id}/`, { is_active: true });
  return data; // Product
}

export async function createStockAdjustment(payload) {
  const { data } = await apiClient.post("/stock-adjustments/", payload);
  return data; // StockAdjustment
}
