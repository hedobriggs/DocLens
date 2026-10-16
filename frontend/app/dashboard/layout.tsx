
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

  return <><nav aria-label="Administration" className="bg-slate-950 px-6 py-2 text-sm">
    <a href="/monitoring" className="underline">Monitoring</a>
  </nav>{children}</>;
}

