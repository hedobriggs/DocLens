import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { SESSION_COOKIE, verifySession } from "../../lib/auth";

export default async function MonitoringPage() {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!await verifySession(token)) redirect("/");
  const grafana = process.env.GRAFANA_PUBLIC_URL || "http://localhost:3001";
  const url = new URL(grafana);
  if (!["http:", "https:"].includes(url.protocol)) throw new Error("Invalid Grafana URL");
  return (
    <main className="max-w-3xl mx-auto p-8 space-y-6">
      <a href="/dashboard">← Documents</a>
      <h1 className="text-3xl font-bold">Monitoring</h1>
      <p>Grafana requires a separate administrator sign-in. Your DocLens session does not grant Grafana access.</p>
      <a className="block underline" href={`${grafana.replace(/\/$/, "")}/d/doclens`}>Open Grafana overview</a>
      <p>The overview links to CPU/system, AI, application and storage dashboards. Unavailable metrics show No data.</p>
    </main>
  );
}
