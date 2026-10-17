import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
const COOKIE = "doclens_workspace_session";
const ID = "[0-9a-fA-F-]{36}";
const routes = [
  /^session$/, /^workspaces$/, /^libraries$/,
  new RegExp(`^(workspaces|libraries)/${ID}/documents$`),
  new RegExp(`^documents/${ID}/versions$`),
  new RegExp(`^versions/${ID}/(original|passages)$`),
  new RegExp(`^workspaces/${ID}/search$`),
  new RegExp(`^workspaces/${ID}/references/${ID}$`),
];

async function forward(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  if (process.env.DOCLENS_PLATFORM_ENABLED !== "1") return new NextResponse(null, { status: 404 });
  const path = (await context.params).path.join("/");
  if (!routes.some(route => route.test(path))) return new NextResponse(null, { status: 404 });
  if (!process.env.PLATFORM_PUBLIC_ORIGIN) return NextResponse.json({ detail: "Workspace service unavailable." }, { status: 503 });
  if (!["GET", "HEAD"].includes(request.method) && request.headers.get("origin") !== process.env.PLATFORM_PUBLIC_ORIGIN) {
    return NextResponse.json({ detail: "Request origin is not allowed." }, { status: 403 });
  }
  const token = request.cookies.get(COOKIE)?.value;
  const isLogin = path === "session" && request.method === "POST";
  // Before reading or forwarding any document body, let the API check live policy.
  if (!isLogin && !token) return NextResponse.json({ detail: "Sign in required." }, { status: 401 });
  const base = process.env.PLATFORM_API_URL;
  if (!base) return NextResponse.json({ detail: "Workspace service unavailable." }, { status: 503 });
  const headers = new Headers();
  if (token && !isLogin) headers.set("Authorization", `Bearer ${token}`);
  for (const name of ["content-type", "content-length", "range"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  try {
    const upstream = await fetch(`${base.replace(/\/$/, "")}/${path}`, {
      method: request.method, headers,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
      // Node streams preserve authorization-before-body admission at the API.
      duplex: "half", redirect: "error", cache: "no-store", signal: AbortSignal.timeout(120000),
    } as RequestInit & { duplex: string });
    if (isLogin && upstream.ok) {
      const data = await upstream.json();
      const response = NextResponse.json({ success: true });
      response.cookies.set(COOKIE, data.token, { httpOnly: true, sameSite: "strict", secure: process.env.NODE_ENV === "production", path: "/", maxAge: data.expires_in });
      response.headers.set("Cache-Control", "no-store");
      return response;
    }
    const resultHeaders = new Headers({ "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" });
    for (const name of ["content-type", "content-range", "accept-ranges", "etag", "content-disposition", "content-security-policy"]) {
      const value = upstream.headers.get(name);
      if (value) resultHeaders.set(name, value);
    }
    const response = new NextResponse(upstream.body, { status: upstream.status, headers: resultHeaders });
    if (path === "session" && request.method === "DELETE") response.cookies.delete(COOKIE);
    return response;
  } catch {
    return NextResponse.json({ detail: "Workspace service unavailable. Reload to check the document state before retrying an upload." }, { status: 502 });
  }
}
export const GET = forward;
export const POST = forward;
export const DELETE = forward;
