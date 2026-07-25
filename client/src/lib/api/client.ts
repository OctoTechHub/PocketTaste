// The single axios instance every endpoint call goes through.
//  - attaches the bearer token from token-store on each request
//  - normalises the server's error shape into a thrown ApiError
//  - clears the session on 401 so a stale token can't wedge the UI

import axios, { AxiosError, type AxiosInstance } from "axios";

import { API_BASE_URL } from "./config";
import { clearSession, getToken } from "./token-store";

/** Normalised error thrown by every endpoint call. */
export class ApiError extends Error {
  readonly status: number;
  readonly details?: unknown;

  constructor(message: string, status: number, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
}

export const http: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
  timeout: 30_000,
});

http.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.set?.("Authorization", `Bearer ${token}`);
  }
  return config;
});

// Best-effort extraction of a human message from the server's error envelope.
// The FastAPI layer returns { error: { message, details } } or { detail: ... }.
function messageFrom(data: unknown, fallback: string): {
  message: string;
  details?: unknown;
} {
  if (data && typeof data === "object") {
    const record = data as Record<string, unknown>;
    const error = record.error as Record<string, unknown> | undefined;
    if (error && typeof error.message === "string") {
      return { message: error.message, details: error.details ?? record };
    }
    if (typeof record.message === "string") {
      return { message: record.message, details: record };
    }
    if (typeof record.detail === "string") {
      return { message: record.detail, details: record };
    }
  }
  return { message: fallback };
}

http.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    const status = error.response?.status ?? 0;

    // A rejected token is dead weight — drop it so the UI falls back to
    // anonymous rather than looping on 401s.
    if (status === 401) clearSession();

    const { message, details } = messageFrom(
      error.response?.data,
      status === 0
        ? "Cannot reach the API server. Is it running on " + API_BASE_URL + "?"
        : error.message || "Request failed.",
    );

    return Promise.reject(new ApiError(message, status, details));
  },
);
