import apiClient from "./client";

// Verified against backend/apps/suppliers/{models,serializers,views}.py
// in project knowledge -- SupplierViewSet, PurchaseViewSet.
//
//   GET/POST /suppliers/, PATCH /suppliers/{id}/   (Manager+ only --
//     the whole app is gated at IsManagerOrOwner, unlike inventory's
//     read/write split; cashiers never call any of this.)
//   GET/POST /purchases/                            (no PATCH/DELETE --
//     a recorded purchase is a permanent financial record once it's
//     updated the stock ledger, same principle as Sale.)
//
// Neither endpoint has a SearchFilter/DjangoFilterBackend today (same
// situation as /products/ and /categories/), and PurchaseViewSet has
// no ?supplier= query param -- so this mirrors api/inventory.js's
// approach: fetch everything with page_size=1000 and filter/group
// client-side (by search text, and by supplier.id for the selected
// supplier's purchase history) rather than assuming server-side
// filtering that doesn't exist.

export async function fetchSuppliers() {
  const { data } = await apiClient.get("/suppliers/", { params: { page_size: 1000 } });
  return data.results; // Supplier[] -- each annotated with purchase_count, total_spent
}

export async function createSupplier(payload) {
  const { data } = await apiClient.post("/suppliers/", payload);
  return data; // Supplier
}

export async function updateSupplier(id, payload) {
  const { data } = await apiClient.patch(`/suppliers/${id}/`, payload);
  return data; // Supplier
}

export async function fetchPurchases() {
  const { data } = await apiClient.get("/purchases/", { params: { page_size: 1000 } });
  return data.results; // Purchase[] (each with nested line_items)
}

// payload: { supplier, purchase_date, amount_paid, items: [{ product, quantity, unit_cost }] }
// total_amount and payment_status are always computed server-side in
// PurchaseSerializer.create() -- never sent from here.
export async function createPurchase(payload) {
  const { data } = await apiClient.post("/purchases/", payload);
  return data; // Purchase
}
