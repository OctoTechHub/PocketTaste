// Obtains the workspace token the Databricks Apps proxy demands.
//
// A pasted-in token is not viable for a deployed frontend: Databricks OAuth
// tokens expire in about an hour, so prod would come back up and then fall over
// again unattended. Instead the service principal's client credentials are
// exchanged for a fresh token here and cached until just before it expires.
//
// DATABRICKS_TOKEN is only a fallback for a quick manual test. It loses to
// client credentials deliberately: a stale value there used to shadow a working
// service principal, and because the Apps proxy answers a bad token with a
// redirect rather than a 401, that failure looked identical to no token at all.

// The workspace host is not a secret — it is in the README and the app URL. Defaulting
// it means only two variables have to be set in the deployment, and a missing host can
// never be the reason production is down.
const DEFAULT_HOST = "https://dbc-8f4c336d-b2bc.cloud.databricks.com";

// The client id and secret are deliberately env-only. This repository is public, so a
// checked-in fallback would publish the credential and GitHub secret scanning would
// have Databricks revoke it. Server-only is not the same as private.
const HOST = process.env.DATABRICKS_HOST?.trim() || DEFAULT_HOST;
const CLIENT_ID = process.env.DATABRICKS_CLIENT_ID?.trim();
const CLIENT_SECRET = process.env.DATABRICKS_CLIENT_SECRET?.trim();
const RAW_STATIC_TOKEN = process.env.DATABRICKS_TOKEN?.trim();

/** Personal access tokens are not merely rejected here — they are ignored. */
const IS_PAT = /^dapi/i.test(RAW_STATIC_TOKEN ?? "");
const STATIC_TOKEN = RAW_STATIC_TOKEN && !IS_PAT ? RAW_STATIC_TOKEN : undefined;

const HAS_CLIENT_CREDENTIALS = Boolean(CLIENT_ID && CLIENT_SECRET);

/** Refresh this far ahead of expiry so a request in flight can't age out. */
const EXPIRY_MARGIN_MS = 120_000;

export class WorkspaceTokenError extends Error {}

/**
 * Names the missing piece rather than listing every variable. The failure modes
 * here are all invisible from the outside — a PAT, a half-filled service
 * principal and no config at all produce the same login redirect.
 */
export function credentialsDiagnosis(): string {
  if (HAS_CLIENT_CREDENTIALS) {
    return "The service principal is configured but Databricks would not accept it — check it has CAN_USE on the app.";
  }
  if (IS_PAT) {
    return (
      "DATABRICKS_TOKEN holds a 'dapi…' personal access token, which the Apps proxy ignores " +
      "outright. Remove it and set DATABRICKS_CLIENT_ID and DATABRICKS_CLIENT_SECRET instead."
    );
  }
  if (CLIENT_ID && !CLIENT_SECRET) return "DATABRICKS_CLIENT_SECRET is not set.";
  if (CLIENT_SECRET && !CLIENT_ID) return "DATABRICKS_CLIENT_ID is not set.";
  if (STATIC_TOKEN) return "DATABRICKS_TOKEN was not accepted — it has most likely expired.";
  return (
    "No workspace credentials are set. Create a service principal with CAN_USE on the app " +
    "and set DATABRICKS_HOST, DATABRICKS_CLIENT_ID and DATABRICKS_CLIENT_SECRET."
  );
}

/** `https://host/?o=123` is what the workspace UI hands you; keep only the origin. */
function tokenEndpoint(): string {
  if (!HOST) {
    throw new WorkspaceTokenError(
      "DATABRICKS_HOST is not set, so no workspace token can be minted.",
    );
  }
  try {
    return `${new URL(HOST).origin}/oidc/v1/token`;
  } catch {
    throw new WorkspaceTokenError(`DATABRICKS_HOST is not a valid URL: ${HOST}`);
  }
}

let cached: { token: string; expiresAt: number } | null = null;
// Concurrent requests on a cold lambda would otherwise each mint their own.
let inFlight: Promise<string> | null = null;

async function mint(): Promise<string> {
  const response = await fetch(tokenEndpoint(), {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      // Client credentials go in the Basic header rather than the body; the
      // endpoint rejects body-only auth with invalid_client.
      Authorization: `Basic ${Buffer.from(`${CLIENT_ID}:${CLIENT_SECRET}`).toString("base64")}`,
    },
    body: new URLSearchParams({ grant_type: "client_credentials", scope: "all-apis" }),
    cache: "no-store",
  });

  const payload = (await response.json().catch(() => null)) as {
    access_token?: string;
    expires_in?: number;
    error_description?: string;
    error?: string;
  } | null;

  if (!response.ok || !payload?.access_token) {
    const reason = payload?.error_description ?? payload?.error ?? `HTTP ${response.status}`;
    throw new WorkspaceTokenError(
      `Databricks refused the service principal: ${reason.replace(/\.$/, "")}.`,
    );
  }

  cached = {
    token: payload.access_token,
    expiresAt: Date.now() + (payload.expires_in ?? 3600) * 1000 - EXPIRY_MARGIN_MS,
  };
  return cached.token;
}

/** A valid workspace token, or null if this deployment has no usable credentials. */
export async function workspaceToken(): Promise<string | null> {
  if (!HAS_CLIENT_CREDENTIALS) return STATIC_TOKEN ?? null;
  if (cached && Date.now() < cached.expiresAt) return cached.token;

  inFlight ??= mint().finally(() => {
    inFlight = null;
  });
  return inFlight;
}
