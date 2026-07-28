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

// POST /hq/branches/ is not a thing — provisioning is the sync app's
// owner-only endpoint (backend/apps/sync/views.py BranchProvisionView):
//   POST /sync/branches/  { branch_name, code?, is_hq?, address?, phone? }
//     -> { branch_id, branch_name, code, is_hq, enrolment_code, expires_at }
export async function provisionBranch(payload) {
  const { data } = await apiClient.post("/sync/branches/", payload);
  return data;
}
