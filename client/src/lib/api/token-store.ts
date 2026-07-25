// Bearer-token persistence. Browser-only: every accessor is SSR-safe and
// no-ops on the server, where localStorage does not exist.

import { ACCOUNT_STORAGE_KEY, TOKEN_STORAGE_KEY } from "./config";
import type { AccountResponse } from "./types";

const isBrowser = typeof window !== "undefined";

/** In-memory mirror so the axios interceptor reads the token synchronously. */
let cachedToken: string | null = null;

export function getToken(): string | null {
  if (cachedToken !== null) return cachedToken;
  if (!isBrowser) return null;
  cachedToken = window.localStorage.getItem(TOKEN_STORAGE_KEY);
  return cachedToken;
}

export function setToken(token: string | null): void {
  cachedToken = token;
  if (!isBrowser) return;
  if (token) window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
  else window.localStorage.removeItem(TOKEN_STORAGE_KEY);
}

export function getStoredAccount(): AccountResponse | null {
  if (!isBrowser) return null;
  const raw = window.localStorage.getItem(ACCOUNT_STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AccountResponse;
  } catch {
    return null;
  }
}

export function setStoredAccount(account: AccountResponse | null): void {
  if (!isBrowser) return;
  if (account)
    window.localStorage.setItem(ACCOUNT_STORAGE_KEY, JSON.stringify(account));
  else window.localStorage.removeItem(ACCOUNT_STORAGE_KEY);
}

export function clearSession(): void {
  setToken(null);
  setStoredAccount(null);
}
