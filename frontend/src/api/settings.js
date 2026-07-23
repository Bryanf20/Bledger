import apiClient from "./client";

// Verified against backend/apps/auth_users/{views,serializers}.py.
// All owner-only (IsOwner).
//   GET/PATCH /settings/business/      Branch details (code is read-only)
//   GET/PATCH /settings/preferences/   business-wide policy defaults
//   GET       /users/                  staff directory
//   POST      /users/                  create staff (password or PIN)
//   PATCH     /users/{id}/             edit name/role/is_active (deactivate)
//   POST      /users/{id}/reset-pin/   set a new 4-digit PIN

export async function fetchBusiness() {
  const { data } = await apiClient.get("/settings/business/");
  return data;
}

export async function updateBusiness(payload) {
  const { data } = await apiClient.patch("/settings/business/", payload);
  return data;
}

export async function fetchPreferences() {
  const { data } = await apiClient.get("/settings/preferences/");
  return data;
}

export async function updatePreferences(payload) {
  const { data } = await apiClient.patch("/settings/preferences/", payload);
  return data;
}

export async function fetchStaff() {
  const { data } = await apiClient.get("/users/");
  return data; // StaffUser[] (not paginated — one branch's staff)
}

export async function createStaff(payload) {
  const { data } = await apiClient.post("/users/", payload);
  return data;
}

export async function updateStaff(id, payload) {
  const { data } = await apiClient.patch(`/users/${id}/`, payload);
  return data;
}

export async function resetStaffPin(id, pin) {
  const { data } = await apiClient.post(`/users/${id}/reset-pin/`, { pin });
  return data;
}
