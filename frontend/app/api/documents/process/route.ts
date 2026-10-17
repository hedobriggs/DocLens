import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { request as httpRequest } from "node:http";
import { once } from "node:events";
import { SESSION_COOKIE, verifySession } from "../../../../lib/auth";
export const runtime = "nodejs";
const MAX_BODY = 32 * 1024 * 1024 + 65536;
const DEADLINE_MS = 120000;
class UploadFailure extends Error {
  constructor(public status: number, message: string) { super(message); }
}
export async function POST(request: NextRequest) {
  if (!await verifySession((await cookies()).get(SESSION_COOKIE)?.value)) {
    return NextResponse.json({ detail: "Please sign in again." }, { status: 401 });
  }
  const secret = process.env.DOCLENS_SESSION_SECRET;
  if (!secret) return NextResponse.json({ detail: "Server authentication is not configured." }, { status: 503 });
  const contentType = request.headers.get("content-type") || "";
  const length = request.headers.get("content-length");
  if (!contentType.toLowerCase().startsWith("multipart/form-data;")) return NextResponse.json({ detail: "A multipart PDF upload is required." }, { status: 400 });
  if (length !== null && (!/^\d+$/.test(length) || Number(length) > MAX_BODY)) return NextResponse.json({ detail: "PDF upload exceeds the 32 MiB limit." }, { status: 413 });
  if (!request.body) return NextResponse.json({ detail: "A PDF is required." }, { status: 400 });
  const reader = request.body.getReader();
  let timer: ReturnType<typeof setTimeout> | undefined;
  let stop: (() => void) | undefined;
  try {
    const result = await new Promise<{ status: number; data: object }>((resolve, reject) => {
      let settled = false;
      const finish = (error?: Error, value?: { status: number; data: object }) => {
        if (settled) return;
        settled = true;
        if (timer) clearTimeout(timer);
        void reader.cancel().catch(() => {});
        if (error) { upstream.destroy(); reject(error); }
        else if (value) { upstream.destroy(); resolve(value); }
      };
      const headers: Record<string, string> = { "Content-Type": contentType, "X-DocLens-Internal-Key": secret };
      if (length !== null) headers["Content-Length"] = length;
      const upstream = httpRequest("http://backend:8000/documents/process", { method: "POST", headers }, response => {
        const chunks: Buffer[] = [];
        let size = 0;
        response.on("data", (chunk: Buffer) => {
          size += chunk.length;
          if (size > 65536) finish(new UploadFailure(502, "Invalid response from document service."));
          else chunks.push(chunk);
        });
        response.on("aborted", () => finish(new UploadFailure(502, "Document service closed its response.")));
        response.on("error", () => finish(new UploadFailure(502, "Unable to read the document service response.")));
        response.on("end", () => {
          if (settled) return;
          try {
            const data = JSON.parse(Buffer.concat(chunks).toString("utf8"));
            if (!data || typeof data !== "object" || Array.isArray(data)) throw new Error();
            finish(undefined, { status: response.statusCode || 502, data });
          } catch { finish(new UploadFailure(502, "Invalid response from document service.")); }
        });
      });
      const writableLifetime = new AbortController();
      upstream.once("close", () => writableLifetime.abort());
      stop = () => finish(new UploadFailure(499, "Upload cancelled. Check document status before retrying."));
      request.signal.addEventListener("abort", stop, { once: true });
      upstream.on("error", () => finish(new UploadFailure(502, "Unable to reach the document service.")));
      // Absolute, including transfer: response trickle cannot reset this deadline.
      timer = setTimeout(() => finish(new UploadFailure(504, "PDF upload exceeded the two-minute deadline. Check document status before retrying.")), DEADLINE_MS);
      if (request.signal.aborted) { stop(); return; }
      void (async () => {
        let sent = 0;
        try {
          while (!settled) {
            const { done, value } = await reader.read();
            if (done) { if (!settled) upstream.end(); return; }
            if (settled) return;
            sent += value.byteLength;
            if (sent > MAX_BODY) throw new UploadFailure(413, "PDF upload exceeds the 32 MiB limit.");
            if (!upstream.write(value)) await once(upstream, "drain", { signal: writableLifetime.signal });
          }
        } catch (error) {
          finish(error instanceof UploadFailure ? error : new UploadFailure(502, "Upload transfer failed."));
        }
      })();
    });
    return NextResponse.json(result.data, { status: result.status });
  } catch (error) {
    const failure = error instanceof UploadFailure ? error : new UploadFailure(502, "Unable to upload the document.");
    return NextResponse.json({ detail: failure.message }, { status: failure.status });
  } finally {
    if (timer) clearTimeout(timer);
    if (stop) request.signal.removeEventListener("abort", stop);
    void reader.cancel().catch(() => {});
  }
}
