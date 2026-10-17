import { NextRequest, NextResponse } from "next/server";

export function proxy(request: NextRequest) {
  if (process.env.DOCLENS_PLATFORM_ENABLED !== "1") return NextResponse.next();
  const path = request.nextUrl.pathname;
  if (path === "/") {
    const origin = process.env.PLATFORM_PUBLIC_ORIGIN;
    if (!origin) return new NextResponse(null, { status: 503 });
    return NextResponse.redirect(new URL("/workspaces", origin));
  }
  if (path === "/workspaces" || path.startsWith("/api/platform/") || path.startsWith("/_next/") || path === "/favicon.ico") {
    return NextResponse.next();
  }
  // Opt-in platform mode cannot reach the legacy shared-admin RAG endpoints.
  return new NextResponse(null, { status: 404 });
}
// Streaming API routes enforce their own platform-mode boundary. Excluding them
// avoids Next proxy's automatic body clone/truncation (including legacy 25 MiB PDFs).
export const config = { matcher: ["/((?!api/platform/|api/documents/process).*)"] };
