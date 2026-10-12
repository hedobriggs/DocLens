
import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { SESSION_COOKIE, verifySession } from "../../../../lib/auth";

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
    const formData = await request.formData();
    const file = formData.get("file");

    if (!(file instanceof File)) {
      return NextResponse.json(
        { detail: "Please select a PDF file." },
        { status: 400 }
      );
    }

    const backendForm = new FormData();
    backendForm.append("file", file);

    const response = await fetch(
      "http://backend:8000/documents/process",
      {
        method: "POST",
        headers: {
          "X-DocLens-Internal-Key": secret,
        },
        body: backendForm,
        cache: "no-store",
      }
    );

    const data = await response.json();

    return NextResponse.json(data, {
      status: response.status,
    });
  } catch {
    return NextResponse.json(
      { detail: "Unable to upload the document." },
      { status: 502 }
    );
  }
}

