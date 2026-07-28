import apiClient from "./client";

// Verified against backend/apps/sync/views.py:
//   GET /sync/status/  (any staff)  -> { sync_enabled, connectivity, pending,
//                                        rejected, consecutive_failures,
//                                        last_success_at, last_error }
//   GET /sync/health/  (owner only) -> { sync_enabled, pending, rejected_count,
//                                        rejected: [...], last_success_at,
//                                        last_attempt_at, consecutive_failures,
//                                        last_error }
export async function fetchSyncStatus() {
  const { data } = await apiClient.get("/sync/status/");
  return data;
}

export async function fetchSyncHealth() {
  const { data } = await apiClient.get("/sync/health/");
  return data;
}

// POST /sync/connect/ — device-side "Connect to head office" (Phase 2 §2.3).
// AllowAny (pre-setup). Redeems the enrolment code, persists the branch
// identity locally, and warms up a pull. Payload: { code, cloud_url? }.
export async function connectToHQ(payload) {
  const { data } = await apiClient.post("/sync/connect/", payload);
  return data; // { branch_id, branch_name, business_name, code, is_hq }
}
