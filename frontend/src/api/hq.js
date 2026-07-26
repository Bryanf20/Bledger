import apiClient from "./client";

// Verified against backend/apps/dashboard/hq_views.py:
//   GET /hq/summary/?period=today|week|month  (owner only)
//     -> { period, branch_count, total_revenue, total_transactions,
//          branches: [{ branch_id, branch_name, code, is_hq, is_active,
//                       last_synced_at, revenue, transaction_count }] }
export async function fetchHQSummary(period = "today") {
  const { data } = await apiClient.get("/hq/summary/", { params: { period } });
  return data;
}
