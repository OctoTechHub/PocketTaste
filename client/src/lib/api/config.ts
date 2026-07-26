// Central place for API configuration. Everything else reads from here so the
// base URL and storage keys are defined exactly once.

// Defaults to the same-origin proxy at app/api/backend, which forwards to
// API_UPSTREAM_URL server-side. Going through it means calls are never
// cross-origin, so CORS and the Databricks Apps OAuth redirect stop applying.
// Set NEXT_PUBLIC_API_URL to an absolute URL only to bypass the proxy and hit a
// backend directly — that path is subject to the upstream's CORS policy.
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "/api/backend";

/** localStorage key under which the bearer token is persisted. */
export const TOKEN_STORAGE_KEY = "pockettaste.access_token";

/** localStorage key under which the signed-in account snapshot is cached. */
export const ACCOUNT_STORAGE_KEY = "pockettaste.account";
