import { NextRequest } from "next/server";
import { monitoringProxy } from "../../../lib/monitoring-proxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

async function proxy(request: NextRequest, context: { params: Promise<{ path?: string[] }> }) {
  return monitoringProxy(request, context, "grafana");
}

export { proxy as GET, proxy as POST, proxy as PUT, proxy as PATCH, proxy as DELETE, proxy as HEAD };
