import { decodeJwt } from "jose";
import { SessionStateProvider } from "../../lib/session-state";

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

  const expiresAt = (decodeJwt(token!).exp || 0) * 1000;
  return <SessionStateProvider expiresAt={expiresAt}>{children}</SessionStateProvider>;
}

