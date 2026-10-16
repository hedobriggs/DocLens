
import { NextRequest, NextResponse } from "next/server";
import { Agent, FormData as BackendFormData, fetch as backendFetch } from "undici";
import { cookies } from "next/headers";
import { SESSION_COOKIE, verifySession } from "../../../../lib/auth";

export const runtime = "nodejs";
// Processing a large PDF includes CPU inference, not just transferring bytes.
export const maxDuration = 600;
const configuredDeadline = Number(process.env.UPLOAD_TIMEOUT_MS || 600_000);
if (!Number.isInteger(configuredDeadline) || configuredDeadline < 1 || configuredDeadline > 600_000) {
  throw new Error("UPLOAD_TIMEOUT_MS must be an integer between 1 and 600000.");
}
const processingAgent = new Agent({
  headersTimeout: configuredDeadline,
  bodyTimeout: configuredDeadline,
});

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
    let formData: FormData;
    try {
      formData = await request.formData();
    } catch {
      return NextResponse.json({ detail: "Invalid multipart upload. Please select the PDF again." }, { status: 400 });
    }
    const file = formData.get("file");

    if (!(file instanceof File)) {
      return NextResponse.json(
        { detail: "Please select a PDF file." },
        { status: 400 }
      );
    }

    if (file.size > 50 * 1024 * 1024) {
      return NextResponse.json(
        { detail: "PDF files must be 50 MiB or smaller." },
        { status: 413 }
      );
    }

    const backendForm = new BackendFormData();
    backendForm.append("file", file);

    const response = await backendFetch(
      `${process.env.BACKEND_URL || "http://backend:8000"}/documents/process`,
      {
        method: "POST",
        headers: {
          "X-DocLens-Internal-Key": secret,
        },
        body: backendForm,
        dispatcher: processingAgent,
        cache: "no-store",
        signal: AbortSignal.timeout(configuredDeadline),
      }
    );

    let data: unknown;
    try {
      data = await response.json();
    } catch (error) {
      // Keep timeout errors distinct, including a timeout while reading the body.
      if (isTimeout(error)) throw error;
      return NextResponse.json({ detail: "Document service returned an invalid response. Please contact the administrator." }, { status: 502 });
    }

    if (response.ok && (!data || typeof data !== "object" ||
      !("filename" in data) || typeof data.filename !== "string" ||
      !("indexed" in data) || data.indexed !== true ||
      !("total_chunks" in data) || !Number.isInteger(data.total_chunks) || Number(data.total_chunks) < 0)) {
      return NextResponse.json({ detail: "Document service returned an invalid response. Please contact the administrator." }, { status: 502 });
    }
    return NextResponse.json(data, {
      status: response.status,
    });
  } catch (error) {
    if (isTimeout(error)) {
      return NextResponse.json(
        { detail: "Document processing exceeded the supported deadline. Try a smaller PDF or ask the administrator to check processing capacity. The server may still be processing; check before retrying." },
        { status: 504 }
      );
    }
    return NextResponse.json(
      { detail: "Document service is unavailable. Please try again later or contact the administrator." },
      { status: 502 }
    );
  }
}


function isTimeout(error: unknown): boolean {
  if (!(error instanceof Error)) return false;
  const code = (error as Error & { code?: string }).code;
  return error.name === "TimeoutError" || code === "UND_ERR_HEADERS_TIMEOUT" ||
    code === "UND_ERR_BODY_TIMEOUT" || (error.cause !== undefined && isTimeout(error.cause));
}
