"use client";

import { ReactNode, createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { User } from "@/lib/types";

const TOKEN_KEY = "shiftiq_token";

interface AuthContextValue {
  user: User | null;
  token: string | null;
  /** True while checking localStorage / verifying an existing token on first load. */
  isLoading: boolean;
  /**
   * Set when we have a stored token but couldn't confirm it with the server
   * (e.g. the backend is still waking up). The token is kept — this is NOT
   * a logged-out state — so the UI should show a retry option, not /login.
   */
  authCheckError: string | null;
  retryAuthCheck: () => void;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [authCheckError, setAuthCheckError] = useState<string | null>(null);

  // On first load, restore a token from localStorage and verify it's still
  // valid by fetching the current user. Only a confirmed 401 (token actually
  // invalid/expired) should log the user out. Any other failure — e.g. the
  // Render free-tier backend still waking up from sleep, a dropped network
  // request, a 5xx — is transient, so we keep the token and let the caller
  // retry instead of silently signing the user out.
  const verify = useCallback(async (stored: string) => {
    setIsLoading(true);
    setAuthCheckError(null);
    try {
      const me = await api.auth.me(stored);
      setUser(me);
      setToken(stored);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        localStorage.removeItem(TOKEN_KEY);
        setToken(null);
        setUser(null);
      } else {
        // Keep the stored token — we just couldn't confirm it right now.
        setToken(stored);
        setAuthCheckError(
          err instanceof ApiError
            ? err.message
            : "Couldn't reach the server. It may still be waking up — try again in a moment."
        );
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const stored = localStorage.getItem(TOKEN_KEY);
    if (!stored) {
      setIsLoading(false);
      return;
    }
    verify(stored);
  }, [verify]);

  const retryAuthCheck = useCallback(() => {
    const stored = localStorage.getItem(TOKEN_KEY);
    if (stored) verify(stored);
  }, [verify]);

  const login = useCallback(async (email: string, password: string) => {
    const { access_token } = await api.auth.login(email, password);
    const me = await api.auth.me(access_token);
    localStorage.setItem(TOKEN_KEY, access_token);
    setToken(access_token);
    setUser(me);
  }, []);

  const register = useCallback(
    async (email: string, password: string) => {
      await api.auth.register(email, password);
      await login(email, password);
    },
    [login]
  );

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
  }, []);

  // Every consumer of useAuth() re-renders whenever this object's identity
  // changes. Without memoizing it, AuthProvider re-renders on every state
  // change here recreate a brand-new object, which re-renders the entire
  // subtree (Sidebar, Header, BottomNav, and every page) even when the
  // fields a given consumer actually reads are unchanged.
  const value = useMemo<AuthContextValue>(
    () => ({ user, token, isLoading, authCheckError, retryAuthCheck, login, register, logout }),
    [user, token, isLoading, authCheckError, retryAuthCheck, login, register, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an <AuthProvider>");
  return ctx;
}

export { ApiError };
