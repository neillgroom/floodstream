import type { Env } from "./types";
import { handleChat } from "./chat";

// ─── CORS ──────────────────────────────────────────────────────────
const ALLOWED_ORIGINS = [
  "http://localhost:3000",
  "http://localhost:8787",
  "https://floodstream.quincy-tax.workers.dev",
  "null", // local file:// testing
];

function corsHeaders(origin: string | null): Record<string, string> {
  const allowed =
    origin && ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0];
  return {
    "Access-Control-Allow-Origin": allowed,
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
  };
}

function isOriginAllowed(request: Request): boolean {
  const origin = request.headers.get("Origin");
  if (origin && ALLOWED_ORIGINS.includes(origin)) return true;
  const referer = request.headers.get("Referer");
  if (referer) {
    try {
      const refOrigin = new URL(referer).origin;
      return ALLOWED_ORIGINS.includes(refOrigin);
    } catch {}
  }
  return false;
}

function withCors(response: Response, origin: string | null): Response {
  const headers = new Headers(response.headers);
  for (const [k, v] of Object.entries(corsHeaders(origin))) {
    headers.set(k, v);
  }
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

// ─── Widget JS ─────────────────────────────────────────────────────
import WIDGET_JS from "../echo-widget.js.txt";

// ─── Main Worker ───────────────────────────────────────────────────
export default {
  async fetch(
    request: Request,
    env: Env,
    ctx: ExecutionContext
  ): Promise<Response> {
    const url = new URL(request.url);
    const origin = request.headers.get("Origin");

    // ── Preflight ──────────────────────────────────────────────
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders(origin) });
    }

    // ── Widget JS ──────────────────────────────────────────────
    if (url.pathname === "/widget.js" && request.method === "GET") {
      return new Response(WIDGET_JS, {
        status: 200,
        headers: {
          "Content-Type": "application/javascript; charset=utf-8",
          "Cache-Control": "public, max-age=60",
          ...corsHeaders(origin),
        },
      });
    }

    // ── Test page ───────────────────────────────────────────────
    if (url.pathname === "/test" && request.method === "GET") {
      const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Echo — Flood Claims Assistant</title>
  <style>
    body { font-family: 'Source Sans 3', -apple-system, sans-serif; max-width: 700px; margin: 60px auto; padding: 20px; color: #333; }
    h1 { color: #1a365d; margin-bottom: 8px; }
    h2 { color: #1a365d; font-size: 18px; margin-top: 24px; }
    p { margin: 8px 0; line-height: 1.6; }
    li { margin: 6px 0; }
    .subtitle { color: #666; font-size: 15px; margin-bottom: 24px; }
  </style>
</head>
<body>
  <h1>Echo</h1>
  <p class="subtitle">Flood Claims Assistant for Fountain Group Adjusters</p>
  <h2>Try asking:</h2>
  <ul>
    <li>Is carpet covered under Coverage A or Coverage B?</li>
    <li>What items are covered in a basement?</li>
    <li>Can I submit a lump-sum estimate for bathroom repair?</li>
    <li>What documentation do I need for a price deviation?</li>
    <li>What are the advance payment options?</li>
    <li>How does the RCBAP form differ from the Dwelling form?</li>
  </ul>
  <script src="/widget.js?v=${Date.now()}" defer></script>
</body>
</html>`;
      return new Response(html, {
        status: 200,
        headers: { "Content-Type": "text/html; charset=utf-8" },
      });
    }

    // ── Chat endpoint ──────────────────────────────────────────
    if (url.pathname === "/api/chat" && request.method === "POST") {
      if (!isOriginAllowed(request)) {
        return withCors(
          new Response(
            JSON.stringify({
              error: "forbidden",
              message: "Unauthorized origin",
            }),
            { status: 403, headers: { "Content-Type": "application/json" } }
          ),
          origin
        );
      }
      (request as any).ctx = ctx;
      const response = await handleChat(request, env);
      return withCors(response, origin);
    }

    // ── Health check ───────────────────────────────────────────
    if (url.pathname === "/" && request.method === "GET") {
      return new Response(
        JSON.stringify({ status: "ok", service: "echo" }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    }

    // ── 404 ────────────────────────────────────────────────────
    return new Response("Not Found", { status: 404 });
  },
};
