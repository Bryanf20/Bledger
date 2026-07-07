import apiClient from "./client";

// Every function here mirrors an exact endpoint verified from
// backend/apps/auth_users/{views,serializers}.py in project knowledge:
//
//   POST /auth/login/      { username, password } -> { token, user }
//   POST /auth/pin-login/  { username, pin }       -> { token, user }
//   POST /auth/logout/     (token in header)        -> 204 No Content
//   GET  /auth/me/         (token in header)         -> user
//   GET  /setup/status/                              -> { setup_complete }
//
// `user` shape (UserProfileSerializer): id, name, username, role,
// is_active, has_pin, branch: { id, business_name, branch_name,
// address, phone, receipt_footer, deployment_mode, setup_complete }.

export async function login({ username, password }) {
  const { data } = await apiClient.post("/auth/login/", { username, password });
  return data; // { token, user }
}

export async function pinLogin({ username, pin }) {
  const { data } = await apiClient.post("/auth/pin-login/", { username, pin });
  return data; // { token, user }
}

export async function logout() {
  await apiClient.post("/auth/logout/");
}

export async function fetchMe() {
  const { data } = await apiClient.get("/auth/me/");
  return data; // user
}

export async function fetchSetupStatus() {
  const { data } = await apiClient.get("/setup/status/");
  return data; // { setup_complete }
}
