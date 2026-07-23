import apiClient from "./client";

// Verified against backend/apps/customers/{views,serializers}.py.
//   GET/POST /customers/, PATCH /customers/{id}/   (read/create/record-
//     payment = cashier+; PATCH incl. credit_limit = manager+)
//   POST /customers/{id}/record-payment/           { amount, ... }
//   GET  /customers/aged-debt/                      (manager+)
// Balance is server-derived and returned on each customer.
// Same "fetch all, filter client-side" convention as suppliers/inventory.

export async function fetchCustomers() {
  const { data } = await apiClient.get("/customers/", { params: { page_size: 1000 } });
  return data.results; // Customer[] — each with balance, payments
}

export async function createCustomer(payload) {
  const { data } = await apiClient.post("/customers/", payload);
  return data;
}

export async function updateCustomer(id, payload) {
  const { data } = await apiClient.patch(`/customers/${id}/`, payload);
  return data;
}

// payload: { amount, payment_date?, payment_method?, note? }
export async function recordCustomerPayment(customerId, payload) {
  const { data } = await apiClient.post(`/customers/${customerId}/record-payment/`, payload);
  return data; // updated Customer
}

export async function fetchAgedDebt() {
  const { data } = await apiClient.get("/customers/aged-debt/");
  return data; // AgedDebtRow[]
}
