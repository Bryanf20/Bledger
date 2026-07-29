import apiClient from "./client";

// Verified against backend/apps/suppliers/{models,serializers,views}.py
// in project knowledge -- SupplierViewSet, PurchaseViewSet.
//
//   GET/POST /suppliers/, PATCH /suppliers/{id}/   (Manager+ only --
//     the whole app is gated at IsManagerOrOwner, unlike inventory's
//     read/write split; cashiers never call any of this.)
//   GET/POST /purchases/                            (no PATCH/DELETE --
//     a recorded purchase is a permanent financial record once it's
//     updated the stock ledger.)
//   POST /purchases/{id}/record-payment/            (added this session
//     -- the one purpose-built mutation on an otherwise-immutable
//     Purchase, for recording a payment installment against a
//     partial/credit balance. See PurchaseViewSet.record_payment /
//     RecordPurchasePaymentSerializer.)
//
// Neither list endpoint has a SearchFilter/DjangoFilterBackend today
// (same situation as /products/ and /categories/), and PurchaseViewSet
// has no ?supplier= query param -- so this mirrors api/inventory.js's
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
  return data.results; // Purchase[] (each with nested line_items, payments, balance_due)
}

// payload: { supplier, purchase_date, amount_paid, items: [{ product, quantity, unit_cost }] }
// total_amount and payment_status are always computed server-side in
// PurchaseSerializer.create() -- never sent from here.
export async function createPurchase(payload) {
  const { data } = await apiClient.post("/purchases/", payload);
  return data; // Purchase
}

// payload: { amount, payment_date?, note? } -- amount is validated
// server-side against the purchase's current balance_due (rejects
// zero/negative and overpayment); payment_date defaults to today if
// omitted. Returns the updated Purchase, including the new payment in
// its `payments` list and the recalculated amount_paid/payment_status/
// balance_due.
export async function recordPurchasePayment(purchaseId, payload) {
  const { data } = await apiClient.post(`/purchases/${purchaseId}/record-payment/`, payload);
  return data; // Purchase
}

// ---------------------------------------------------------------------------
// Purchase orders (Phase 2 §6) — verified against PurchaseOrderViewSet.
//   GET/POST /purchase-orders/                         (Manager+)
//   POST /purchase-orders/{id}/receive/  { receipts:[{line,quantity}], purchase_date?, amount_paid? }
//   POST /purchase-orders/{id}/send/     (draft -> sent)
//   POST /purchase-orders/{id}/cancel/
// A PO never moves stock; receiving creates a Purchase (the one stock path).
// Same "fetch all, filter client-side by supplier" convention as purchases.
// ---------------------------------------------------------------------------
export async function fetchPurchaseOrders() {
  const { data } = await apiClient.get("/purchase-orders/", { params: { page_size: 1000 } });
  return data.results;
}

export async function createPurchaseOrder(payload) {
  const { data } = await apiClient.post("/purchase-orders/", payload);
  return data;
}

export async function receivePurchaseOrder(id, payload) {
  const { data } = await apiClient.post(`/purchase-orders/${id}/receive/`, payload);
  return data;
}

export async function sendPurchaseOrder(id) {
  const { data } = await apiClient.post(`/purchase-orders/${id}/send/`);
  return data;
}

export async function cancelPurchaseOrder(id) {
  const { data } = await apiClient.post(`/purchase-orders/${id}/cancel/`);
  return data;
}
