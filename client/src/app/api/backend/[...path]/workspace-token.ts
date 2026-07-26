// Obtains the workspace token the Databricks Apps proxy demands.
//
// A pasted-in token is not viable for a deployed frontend: Databricks OAuth
// tokens expire in about an hour, so prod would come back up and then fall over
// again unattended. Instead the service principal's client credentials are
// exchanged for a fresh token here and cached until just before it expires.
//
// DATABRICKS_TOKEN still wins if set, which keeps a quick manual test one env
// var away — but it inherits that expiry, so it is not for production.

const HOST = process.env.DATABRICKS_HOST?.trim();
const CLIENT_ID = process.env.DATABRICKS_CLIENT_ID?.trim();
const CLIENT_SECRET = process.env.DATABRICKS_CLIENT_SECRET?.trim();
const STATIC_TOKEN = process.env.DATABRICKS_TOKEN?.trim();

/** Refresh this far ahead of expiry so a request in flight can't age out. */
const EXPIRY_MARGIN_MS = 120_000;

export class WorkspaceTokenError extends Error {}

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

/** A valid workspace token, or null if this deployment has no credentials. */
export async function workspaceToken(): Promise<string | null> {
  if (STATIC_TOKEN) return STATIC_TOKEN;
  if (!CLIENT_ID || !CLIENT_SECRET) return null;
  if (cached && Date.now() < cached.expiresAt) return cached.token;

  inFlight ??= mint().finally(() => {
    inFlight = null;
  });
  return inFlight;
}

/** Whether credentials exist at all — drives the "what do I set?" error text. */
export const HAS_CREDENTIALS = Boolean(STATIC_TOKEN || (CLIENT_ID && CLIENT_SECRET));
