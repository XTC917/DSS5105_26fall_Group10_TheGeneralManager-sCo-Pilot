import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { clearToken, fetchMe, getToken, setToken } from "../services/authApi.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
  }, []);

  const restore = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      setAuthLoading(false);
      return;
    }
    try {
      const me = await fetchMe();
      setUser(me);
    } catch {
      clearToken();
      setUser(null);
    } finally {
      setAuthLoading(false);
    }
  }, []);

  useEffect(() => {
    restore();
  }, [restore]);

  useEffect(() => {
    const handleUnauthorized = () => logout();
    window.addEventListener("sweaterco:unauthorized", handleUnauthorized);
    return () => window.removeEventListener("sweaterco:unauthorized", handleUnauthorized);
  }, [logout]);

  const value = useMemo(
    () => ({
      user,
      setUser,
      setToken,
      logout,
      restore,
      authLoading,
      isAuthenticated: Boolean(user),
    }),
    [user, logout, restore, authLoading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
