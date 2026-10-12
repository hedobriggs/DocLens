
import "server-only";

import { compare } from "bcryptjs";
import { SignJWT, jwtVerify } from "jose";

export const SESSION_COOKIE = "doclens_session";

const SESSION_DURATION = 60 * 60 * 8; // 8 hours

function getSessionKey(): Uint8Array {
  const secret = process.env.DOCLENS_SESSION_SECRET;

  if (!secret || secret.length < 32) {
    throw new Error("DOCLENS_SESSION_SECRET is not configured.");
  }

  return new TextEncoder().encode(secret);
}

export async function verifyCredentials(
  email: string,
  password: string
): Promise<boolean> {
  const configuredEmail = process.env.DOCLENS_ADMIN_EMAIL;
  const passwordHash = process.env.DOCLENS_ADMIN_PASSWORD_HASH;

  if (!configuredEmail || !passwordHash) {
    throw new Error("DocLens admin credentials are not configured.");
  }

  const emailMatches =
    email.trim().toLowerCase() === configuredEmail.toLowerCase();

  const passwordMatches = await compare(password, passwordHash);

  return emailMatches && passwordMatches;
}

export async function createSession(): Promise<string> {
  return new SignJWT({ role: "admin" })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuer("doclens")
    .setAudience("doclens-frontend")
    .setIssuedAt()
    .setExpirationTime(`${SESSION_DURATION}s`)
    .sign(getSessionKey());
}

export async function verifySession(
  token: string | undefined
): Promise<boolean> {
  if (!token) return false;

  try {
    const { payload } = await jwtVerify(token, getSessionKey(), {
      issuer: "doclens",
      audience: "doclens-frontend",
      algorithms: ["HS256"],
    });

    return payload.role === "admin";
  } catch {
    return false;
  }
}

export const sessionCookieOptions = {
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: "lax" as const,
  path: "/",
  maxAge: SESSION_DURATION,
};

