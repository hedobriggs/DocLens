"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

const SessionState = createContext({ expired: false, expire: () => {} });

export function SessionStateProvider({ expiresAt, children }: {
  expiresAt: number;
  children: React.ReactNode;
}) {
  const [expired, setExpired] = useState(false);
  const expire = useCallback(() => setExpired(true), []);
  useEffect(() => {
    const check = () => { if (Date.now() >= expiresAt) expire(); };
    const timer = window.setTimeout(expire, Math.max(0, expiresAt - Date.now()));
    window.addEventListener("focus", check);
    document.addEventListener("visibilitychange", check);
    return () => {
      clearTimeout(timer);
      window.removeEventListener("focus", check);
      document.removeEventListener("visibilitychange", check);
    };
  }, [expiresAt, expire]);
  return <SessionState.Provider value={{ expired, expire }}>{children}</SessionState.Provider>;
}

export function useSessionState() { return useContext(SessionState); }
