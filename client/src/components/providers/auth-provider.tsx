"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  clearSession,
  getStoredAccount,
  setStoredAccount,
  setToken,
} from "@/lib/api/token-store";
import type { AccountResponse, TokenResponse } from "@/lib/api/types";

interface AuthContextValue {
  account: AccountResponse | null;
  isAuthenticated: boolean;
  /** Persist a successful register/login and update context. */
  setSession: (token: TokenResponse) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/**
 * Holds the signed-in account. Hydrated from localStorage after mount to avoid
 * an SSR/client mismatch, then kept in sync by the auth mutations.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [account, setAccount] = useState<AccountResponse | null>(null);

  // Rehydrate the cached account on the client only. Deliberately a post-mount
  // effect (not a lazy initializer) so server and first client render agree —
  // localStorage is unavailable during SSR.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setAccount(getStoredAccount());
  }, []);

  const setSession = useCallback((token: TokenResponse) => {
    setToken(token.access_token);
    setStoredAccount(token.account);
    setAccount(token.account);
  }, []);

  const logout = useCallback(() => {
    clearSession();
    setAccount(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      account,
      isAuthenticated: account !== null,
      setSession,
      logout,
    }),
    [account, setSession, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuthContext(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuthContext must be used within <AuthProvider>.");
  }
  return ctx;
}
