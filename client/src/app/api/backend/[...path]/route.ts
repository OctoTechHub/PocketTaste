// Server-side pass-through to the FastAPI backend.
//
// The browser cannot call the Databricks Apps URL directly. Apps puts an OAuth
// proxy in front of the container, so a cross-origin request from the app gets
// a 302 to the workspace login page carrying no CORS headers — the browser
// blocks it and axios reports a bare network failure with no status.
//
// Routing every call through this handler fixes both halves of that: the
// browser only ever talks to its own origin, and the workspace token is
// attached here, server-side, where it is never shipped to the client.

import type { NextRequest } from "next/server";

import { WorkspaceTokenError, credentialsDiagnosis, workspaceToken } from "./workspace-token";

export const dynamic = "force-dynamic";

// Deployed builds default to the hosted API; `npm run dev` defaults to the local
// server. Without the split, either local development silently proxies to production
// or production has nowhere to go. `API_UPSTREAM_URL` overrides both.
const DEFAULT_UPSTREAM =
  process.env.NODE_ENV === "production"
    ? "https://pockettaste-api-7474647028679809.aws.databricksapps.com"
    : "http://127.0.0.1:8000";

const UPSTREAM = (process.env.API_UPSTREAM_URL ?? DEFAULT_UPSTREAM).replace(/\/$/, "");

/** Databricks Apps hostnames sit behind the OAuth proxy; nothing else does. */
const BEHIND_OAUTH_PROXY = (() => {
  try {
    return /\.databricksapps\.com$/i.test(new URL(UPSTREAM).hostname);
  } catch {
    return false;
  }
})();

// Hop-by-hop headers, plus the ones fetch must recompute for the new request.
const DROP_REQUEST_HEADERS = new Set([
  "host",
  "connection",
  "keep-alive",
  "transfer-encoding",
  "upgrade",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "content-length",
  "accept-encoding",
]);

const DROP_RESPONSE_HEADERS = new Set([
  "content-encoding",
  "content-length",
  "transfer-encoding",
  "connection",
  "keep-alive",
]);

/** Matches the server's error envelope so ApiError picks up a real message. */
function envelope(message: string, status: number, details?: unknown): Response {
  return Response.json({ error: { message, details } }, { status });
}

async function upstreamHeaders(req: NextRequest): Promise<Headers> {
  const headers = new Headers();
  req.headers.forEach((value, key) => {
    if (!DROP_REQUEST_HEADERS.has(key.toLowerCase())) headers.set(key, value);
  });

  if (!BEHIND_OAUTH_PROXY) return headers;

  // The Apps proxy consumes Authorization for its own workspace check, so the
  // login token from token-store has to travel beside it. deps.py promotes
  // X-App-Authorization back into place on the other side.
  const appToken = req.headers.get("authorization");
  headers.delete("authorization");
  if (appToken) headers.set("x-app-authorization", appToken);

  const token = await workspaceToken();
  if (token) headers.set("authorization", `Bearer ${token}`);

  return headers;
}

/**
 * Turns the proxy's own failure modes into readable JSON. Without this the UI
 * renders an HTML login page or an "app unavailable" splash as a body, which
 * tells nobody anything.
 */
function proxyFailure(response: Response): Response | null {
  // The Apps proxy does not 401 an unusable token — it redirects to login, the
  // same as for no token at all. So the diagnosis has to come from the config.
  const location = response.headers.get("location") ?? "";
  if (response.status >= 300 && response.status < 400 && /\/oidc\//.test(location)) {
    return envelope(
      `Databricks bounced the request to its login page. ${credentialsDiagnosis()}`,
      502,
      { upstream: UPSTREAM, redirected_to: "workspace OAuth login" },
    );
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (response.status === 503 && contentType.includes("text/html")) {
    return envelope(
      "The Databricks App is deployed but not running. Start it from the workspace Apps page.",
      503,
      { upstream: UPSTREAM },
    );
  }

  // A 401/403 that isn't our own error envelope came from the Apps proxy, not
  // from the API. Passing it through unlabelled reads as a failed user login,
  // which sends you looking in exactly the wrong place.
  if ((response.status === 401 || response.status === 403) && !contentType.includes("json")) {
    return envelope(
      `Databricks rejected the workspace credentials. ${credentialsDiagnosis()}`,
      502,
      { upstream: UPSTREAM, upstream_status: response.status },
    );
  }

  return null;
}

async function forward(req: NextRequest, path: string[]): Promise<Response> {
  const target = `${UPSTREAM}/${path.join("/")}${req.nextUrl.search}`;

  // Buffered rather than streamed: the payloads here are small JSON documents,
  // and a streaming body would need duplex negotiation for no benefit.
  const method = req.method.toUpperCase();
  const body =
    method === "GET" || method === "HEAD" ? undefined : await req.arrayBuffer();

  let headers: Headers;
  try {
    headers = await upstreamHeaders(req);
  } catch (cause) {
    if (cause instanceof WorkspaceTokenError) {
      return envelope(`${cause.message} ${credentialsDiagnosis()}`, 502, { upstream: UPSTREAM });
    }
    throw cause;
  }

  let response: Response;
  try {
    response = await fetch(target, {
      method,
      headers,
      body,
      redirect: "manual",
      cache: "no-store",
    });
  } catch (cause) {
    return envelope(
      `Cannot reach the API server at ${UPSTREAM}.`,
      502,
      { upstream: UPSTREAM, cause: cause instanceof Error ? cause.message : String(cause) },
    );
  }

  const failure = proxyFailure(response);
  if (failure) return failure;

  const responseHeaders = new Headers();
  response.headers.forEach((value, key) => {
    if (!DROP_RESPONSE_HEADERS.has(key.toLowerCase())) responseHeaders.set(key, value);
  });

  return new Response(response.body, { status: response.status, headers: responseHeaders });
}

type Context = RouteContext<"/api/backend/[...path]">;

const handler = async (req: NextRequest, ctx: Context) =>
  forward(req, (await ctx.params).path);

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const PATCH = handler;
export const DELETE = handler;
export const HEAD = handler;
