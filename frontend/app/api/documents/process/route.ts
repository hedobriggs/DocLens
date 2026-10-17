
import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { request as httpRequest } from "node:http";

import {
  SESSION_COOKIE,
  verifySession,
} from "../../../../lib/auth";

export const runtime = "nodejs";

const UPLOAD_TIMEOUT_MS = 10 * 60 * 1000;

type BackendResult = {
  detail?: string;
  filename?: string;
  total_chunks?: number;
  [key: string]: unknown;
};

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

    if (file.type !== "application/pdf") {
      return NextResponse.json(
        { detail: "Only PDF files are supported." },
        { status: 400 }
      );
    }

    console.log("DocLens upload started:", {
      filename: file.name,
      sizeMB: (file.size / (1024 * 1024)).toFixed(2),
    });

    const boundary =
      "----DocLensUpload" + crypto.randomUUID();

    const header = Buffer.from(
      `--${boundary}\r\n` +
      `Content-Disposition: form-data; name="file"; filename="${file.name.replace(/["\r\n]/g, "_")}"\r\n` +
      `Content-Type: application/pdf\r\n\r\n`
    );

    const pdfBytes = Buffer.from(
      await file.arrayBuffer()
    );

    const footer = Buffer.from(
      `\r\n--${boundary}--\r\n`
    );

    const body = Buffer.concat([
      header,
      pdfBytes,
      footer,
    ]);

    const result = await new Promise<{
      status: number;
      data: BackendResult;
    }>((resolve, reject) => {
      const req = httpRequest(
        "http://backend:8000/documents/process",
        {
          method: "POST",
          headers: {
            "X-DocLens-Internal-Key": secret,
            "Content-Type":
              `multipart/form-data; boundary=${boundary}`,
            "Content-Length": body.length,
          },
        },
        (res) => {
          const chunks: Buffer[] = [];

          res.on("data", (chunk: Buffer) => {
            chunks.push(chunk);
          });

          res.on("end", () => {
            try {
              const raw = Buffer.concat(chunks).toString("utf8");
              const data = JSON.parse(raw) as BackendResult;

              resolve({
                status: res.statusCode ?? 502,
                data,
              });
            } catch {
              reject(
                new Error("Invalid response from backend")
              );
            }
          });

          res.on("error", reject);
        }
      );

      req.setTimeout(UPLOAD_TIMEOUT_MS, () => {
        req.destroy(
          new Error("PDF processing timed out")
        );
      });

      req.on("error", reject);
      req.end(body);
    });

    if (result.status >= 400) {
      console.error("DocLens backend upload failed:", {
        status: result.status,
        detail: result.data.detail,
      });
    } else {
      console.log(
        "DocLens upload completed:",
        file.name
      );
    }

    return NextResponse.json(result.data, {
      status: result.status,
    });
  } catch (error) {
    console.error(
      "DocLens PDF upload failed:",
      error
    );

    const message =
      error instanceof Error ? error.message : "";

    const timedOut = /timed out|timeout/i.test(message);

    return NextResponse.json(
      {
        detail: timedOut
          ? "PDF processing timed out after 10 minutes."
          : "Unable to upload the document. Check frontend logs.",
      },
      { status: timedOut ? 504 : 502 }
    );
  }
}

