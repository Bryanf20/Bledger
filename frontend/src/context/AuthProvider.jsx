import { useCallback, useEffect, useMemo, useState } from "react";
import * as authApi from "../api/auth";
import { submitSetup } from "../api/setup";
import { getStoredToken, setStoredToken, UNAUTHORIZED_EVENT } from "../api/client";
import { AuthContext } from "./AuthContext";

// Session lifecycle:
//   1. On mount, if a token is already in storage, call GET /auth/me/
//      to validate it and restore `user`.
//   2. login()/pinLogin() call the respective endpoint, store the
//      returned token, and set `user` from the response body directly.
//   3. completeSetup() does the same for POST /setup/ -- it returns
//      the same { token, user } shape (the backend's shared
//      _token_response() helper), so it reuses the identical
//      store-token-then-set-user pattern.
//   4. logout() calls POST /auth/logout/ (best-effort) and clears state.
//   5. Any 401 from apiClient clears the session via UNAUTHORIZED_EVENT.
//
// Lives in its own file (split from AuthContext.jsx) so that file exports
// only the context object + useAuth hook — see AuthContext.jsx's note on
// the react-refresh only-export-components rule.
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isRestoring, setIsRestoring] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function restoreSession() {
      const token = getStoredToken();
      if (!token) {
        setIsRestoring(false);
        return;
      }
      try {
        const profile = await authApi.fetchMe();
        if (!cancelled) setUser(profile);
      } catch {
        if (!cancelled) setUser(null);
      } finally {
        if (!cancelled) setIsRestoring(false);
      }
    }

    restoreSession();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    function handleUnauthorized() {
      setUser(null);
    }
    window.addEventListener(UNAUTHORIZED_EVENT, handleUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, handleUnauthorized);
  }, []);

  const login = useCallback(async (username, password) => {
    const { token, user: profile } = await authApi.login({ username, password });
    setStoredToken(token);
    setUser(profile);
    return profile;
  }, []);

  const pinLogin = useCallback(async (username, pin) => {
    const { token, user: profile } = await authApi.pinLogin({ username, pin });
    setStoredToken(token);
    setUser(profile);
    return profile;
  }, []);

  const completeSetup = useCallback(async (payload) => {
    const { token, user: profile } = await submitSetup(payload);
    setStoredToken(token);
    setUser(profile);
    return profile;
  }, []);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      // Ignore -- clear local state regardless.
    } finally {
      setStoredToken(null);
      setUser(null);
    }
  }, []);

  const value = useMemo(
    () => ({
      user,
      role: user?.role ?? null,
      branch: user?.branch ?? null,
      isAuthenticated: Boolean(user),
      isRestoring,
      login,
      pinLogin,
      completeSetup,
      logout,
    }),
    [user, isRestoring, login, pinLogin, completeSetup, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
