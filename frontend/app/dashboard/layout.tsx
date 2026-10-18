
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import {
  SESSION_COOKIE,
  verifySession,
} from "../../lib/auth";

export default async function DashboardLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE)?.value;

  const authenticated = await verifySession(token);

  if (!authenticated) {
    redirect("/");
  }

  return <div className="flex h-dvh flex-col overflow-hidden"><nav aria-label="Administration" className="doclens-dashboard-navigation shrink-0 bg-slate-950 px-6 py-2 text-sm text-slate-300">
    <a href="/monitoring" className="underline">Monitoring</a>
  </nav><div className="min-h-0 flex-1">{children}</div></div>;
}

