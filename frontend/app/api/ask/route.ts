
import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { SESSION_COOKIE, verifySession } from "../../../lib/auth";

export const runtime = "nodejs";

export async function POST(request: NextRequest) {
  const cookieStore = await cookies();
  const authenticated = await verifySession(
    cookieStore.get(SESSION_COOKIE)?.value
  );

  if (!authenticated) {
    return NextResponse.json(
      { detail: "Please sign in again." },
      { status: 401 }
    );
  }

  const secret = process.env.DOCLENS_SESSION_SECRET;

  if (!secret) {
    return NextResponse.json(
      { detail: "Server authentication is not configured." },
      { status: 503 }
    );
  }

  try {
    const body = await request.json();

    const response = await fetch("http://backend:8000/ask", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-DocLens-Internal-Key": secret,
      },
      body: JSON.stringify(body),
      cache: "no-store",
    });

    const data = await response.json();

    return NextResponse.json(data, {
      status: response.status,
    });
  } catch {
    return NextResponse.json(
      { detail: "Unable to contact the document service." },
      { status: 502 }
    );
  }
}

