import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import * as authApi from "../api/auth";
import { getStoredToken, setStoredToken, UNAUTHORIZED_EVENT } from "../api/client";

const AuthContext = createContext(null);

// Session lifecycle:
//   1. On mount, if a token is already in storage, call GET /auth/me/
//      to validate it and restore `user` -- this is what survives a
//      page refresh (design doc E.1: "used to restore session on app
//      load").
//   2. login()/pinLogin() call the respective endpoint, store the
//      returned token, and set `user` from the response body directly
//      (no extra /auth/me/ round trip needed -- both endpoints already
//      return the full profile).
//   3. logout() calls POST /auth/logout/ (best-effort -- token is
//      cleared locally regardless of whether the request succeeds)
//      and clears state.
//   4. Any 401 from apiClient (e.g. token revoked server-side, or
//      expired) clears the session the same way, via the
//      UNAUTHORIZED_EVENT listener below.
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
        // Invalid/expired token -- the response interceptor already
        // cleared it on the 401; just make sure local state matches.
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

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      // Ignore -- we clear local state regardless so the user is never
      // stuck "logged in" client-side just because the network call
      // failed.
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
      logout,
    }),
    [user, isRestoring, login, pinLogin, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
