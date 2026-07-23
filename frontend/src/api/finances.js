import apiClient from "./client";

// Verified against backend/apps/finances/{views,serializers,services}.py.
//   GET/POST /finances/expense-categories/            manager+
//   POST     /finances/expense-categories/seed-defaults/   manager+ (idempotent)
//   GET/POST/PATCH/DELETE /finances/cashbook/          manager+
//     -- unlike sales, a cashbook entry IS editable (PATCH) and
//        soft-deletable (DELETE) -- the deliberate bookkeeping exception.
//   GET /finances/pnl/?period=today|week|month         OWNER-ONLY
//
// Same "fetch all, filter client-side" convention as the other screens
// (page_size=1000); the cashbook is period-filtered client-side.

export async function fetchExpenseCategories() {
  const { data } = await apiClient.get("/finances/expense-categories/", {
    params: { page_size: 1000 },
  });
  return data.results; // ExpenseCategory[] -- { id, name, is_active }
}

export async function seedDefaultCategories() {
  const { data } = await apiClient.post("/finances/expense-categories/seed-defaults/");
  return data; // full ExpenseCategory[] after seeding (idempotent)
}

export async function createExpenseCategory(payload) {
  const { data } = await apiClient.post("/finances/expense-categories/", payload);
  return data;
}

export async function fetchCashbook() {
  const { data } = await apiClient.get("/finances/cashbook/", {
    params: { page_size: 1000 },
  });
  return data.results; // CashbookEntry[] -- { id, direction, category,
  // category_name, amount, occurred_on, description, payment_method,
  // recorded_by_name }
}

// payload: { direction, category?, amount, occurred_on, description?, payment_method? }
export async function createCashbookEntry(payload) {
  const { data } = await apiClient.post("/finances/cashbook/", payload);
  return data;
}

export async function updateCashbookEntry(id, payload) {
  const { data } = await apiClient.patch(`/finances/cashbook/${id}/`, payload);
  return data;
}

export async function deleteCashbookEntry(id) {
  await apiClient.delete(`/finances/cashbook/${id}/`);
  return id;
}

export async function fetchPnl(period) {
  const { data } = await apiClient.get("/finances/pnl/", { params: { period } });
  return data; // { period, gross_margin, revenue, cogs, total_expenses,
  // total_income, net_profit, expenses_by_category[] }
}
