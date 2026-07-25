// Central place for API configuration. Everything else reads from here so the
// base URL and storage keys are defined exactly once.

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

/** localStorage key under which the bearer token is persisted. */
export const TOKEN_STORAGE_KEY = "pockettaste.access_token";

/** localStorage key under which the signed-in account snapshot is cached. */
export const ACCOUNT_STORAGE_KEY = "pockettaste.account";
