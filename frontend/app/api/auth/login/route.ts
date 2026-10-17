
import { NextRequest, NextResponse } from "next/server";
import {
  createSession,
  sessionCookieOptions,
  SESSION_COOKIE,
  verifyCredentials,
} from "../../../../lib/auth";

export const runtime = "nodejs";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    if (
      typeof body.email !== "string" ||
      typeof body.password !== "string"
    ) {
      return NextResponse.json(
        { error: "Email and password are required." },
        { status: 400 }
      );
    }

    const valid = await verifyCredentials(
      body.email,
      body.password
    );
    try {
  await fetch("http://backend:8000/internal/auth-event", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-DocLens-Internal-Key": process.env.DOCLENS_SESSION_SECRET || "",
    },
    body: JSON.stringify({
      outcome: valid ? "success" : "failure",
    }),
    signal: AbortSignal.timeout(2000),
  });
} catch (error) {
  console.error("Authentication metrics unavailable:", error);
}

    if (!valid) {
      return NextResponse.json(
        { error: "Invalid email or password." },
        { status: 401 }
      );
    }

    const token = await createSession();

    const response = NextResponse.json({
      success: true,
    });

    response.cookies.set(
      SESSION_COOKIE,
      token,
      sessionCookieOptions
    );

    return response;
  } catch (error) {
    console.error("Login failed:", error);

    return NextResponse.json(
      { error: "Unable to sign in." },
      { status: 500 }
    );
  }
}

