import { NextRequest, NextResponse } from "next/server";
import { SESSION_COOKIE, verifySession } from "./auth";

const HOP_HEADERS = ["connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailer", "transfer-encoding", "upgrade"];

export async function monitoringProxy(request: NextRequest, context: { params: Promise<{ path?: string[] }> }, service: "grafana" | "prometheus") {
  const prefix = service === "grafana" ? "/monitoring" : "/prometheus";
  if (process.env.DOCLENS_MONITORING !== "1") {
    return NextResponse.json({ detail: "Monitoring is not enabled." }, { status: 404 });
  }
  if (!(await verifySession(request.cookies.get(SESSION_COOKIE)?.value))) {
    if (request.nextUrl.pathname.startsWith(prefix + "/api/")) {
      return NextResponse.json({ detail: "Please sign into DocLens again." }, { status: 401 });
    }
    return NextResponse.redirect(new URL("/", request.url), 303);
  }
  const { path = [] } = await context.params;
  if (path.some(part => part === "." || part === ".." || /[\\/]/.test(part))) {
    return NextResponse.json({ detail: "Invalid monitoring path." }, { status: 400 });
  }
  // This fixed internal destination cannot be selected by request input.
  const destination = service === "grafana" ? "http://grafana:3001/monitoring/" : "http://prometheus:9090/";
  const target = destination + path.map(encodeURIComponent).join("/") + request.nextUrl.search;
  const headers = new Headers(request.headers);
  HOP_HEADERS.forEach(name => headers.delete(name));
  ["authorization", "content-length", "x-doclens-internal-key"].forEach(name => headers.delete(name));
  headers.delete("x-doclens-grafana-user");
  if (service === "grafana") headers.set("x-doclens-grafana-user", "admin");
  headers.set("cookie", (request.headers.get("cookie") || "").split(";").filter(c => c.trim().split("=")[0] !== SESSION_COOKIE).join(";"));
  headers.set("x-forwarded-host", request.headers.get("host") || request.nextUrl.host);
  headers.set("x-forwarded-proto", request.nextUrl.protocol.replace(":", ""));

  try {
    let body: Uint8Array | undefined;
    if (request.method !== "GET" && request.method !== "HEAD" && request.body) {
      const reader = request.body.getReader();
      const chunks: Uint8Array[] = [];
      let bytes = 0, expired = false;
      const timer = setTimeout(() => { expired = true; void reader.cancel(); }, 5000);
      try {
        while (true) {
          const chunk = await reader.read();
          if (expired) return NextResponse.json({ detail: "Monitoring request timed out." }, { status: 408 });
          if (chunk.done) break;
          bytes += chunk.value.byteLength;
          if (bytes > 2 * 1024 * 1024) {
            await reader.cancel();
            return NextResponse.json({ detail: "Monitoring request is too large." }, { status: 413 });
          }
          chunks.push(chunk.value);
        }
      } finally { clearTimeout(timer); reader.releaseLock(); }
      body = new Uint8Array(bytes);
      let offset = 0;
      for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.byteLength; }
    }
    const upstream = await fetch(target, {
      method: request.method, headers, body: body as BodyInit | undefined,
      redirect: "manual", cache: "no-store", signal: AbortSignal.timeout(15000),
    });
    const outgoing = new Headers(upstream.headers);
    HOP_HEADERS.forEach(name => outgoing.delete(name));
    // Fetch decompresses content; do not forward stale compressed length/encoding.
    ["content-encoding", "content-length", "set-cookie"].forEach(name => outgoing.delete(name));
    for (const cookie of upstream.headers.getSetCookie()) outgoing.append("set-cookie", cookie);
    outgoing.set("cache-control", "no-store");
    const empty = request.method === "HEAD" || [204, 205, 304].includes(upstream.status);
    return new Response(empty ? null : upstream.body, { status: upstream.status, headers: outgoing });
  } catch {
    return NextResponse.json({ detail: "Monitoring is temporarily unavailable." }, { status: 502 });
  }
}
