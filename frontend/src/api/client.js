import axios from "axios";

// Real backend contract (verified against apps/auth_users/views.py and
// serializers.py in project knowledge, not assumed from the design
// doc alone):
//   - DRF TokenAuthentication: header is `Authorization: Token <key>`
//     (NOT `Bearer <key>` -- that's a different DRF/OAuth scheme).
//   - Root API prefix is /api/v1/, mounted in bledger/urls.py.
export const TOKEN_STORAGE_KEY = "bledger_token";

export function getStoredToken() {
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setStoredToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_STORAGE_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
  }
}

const apiClient = axios.create({
  baseURL: `${import.meta.env.VITE_API_URL ?? ""}/api/v1`,
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.request.use((config) => {
  const token = getStoredToken();
  if (token) {
    config.headers.Authorization = `Token ${token}`;
  }
  return config;
});

// On a 401, clear the stored token and broadcast a window event rather
// than importing AuthContext here directly -- keeps this module free
// of a circular dependency on the context that consumes it.
// AuthContext subscribes to this event to clear its own state and
// redirect to /login.
export const UNAUTHORIZED_EVENT = "bledger:unauthorized";

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      setStoredToken(null);
      window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT));
    }
    return Promise.reject(error);
  },
);

export default apiClient;
