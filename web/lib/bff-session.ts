import "server-only";

import { createHash, randomBytes, timingSafeEqual } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";

export const ACCESS_COOKIE = "haha_access";
export const REFRESH_COOKIE = "haha_refresh";
export const CSRF_COOKIE = "haha_csrf";
export const CSRF_HEADER = "x-csrf-token";

type TokenPayload = {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  account: { user_id: string; workspace_id: string; role: string };
};

const refreshes = new Map<string, Promise<TokenPayload | null>>();

function internalApiUrl(): string {
  const raw = process.env.HAHA_INTERNAL_API_URL
    ?? process.env.NEXT_PUBLIC_API_BASE_URL
    ?? "http://127.0.0.1:8000";
  const url = new URL(raw);
  if (!(["http:", "https:"] as string[]).includes(url.protocol)) {
    throw new Error("HAHA_INTERNAL_API_URL 只允许 http/https");
  }
  return url.origin;
}

function secureCookies(): boolean {
  const environment = (process.env.HAHA_ENVIRONMENT ?? "development").toLowerCase();
  const secure = (process.env.HAHA_COOKIE_SECURE ?? "").toLowerCase() === "true";
  if (["staging", "production"].includes(environment) && !secure) {
    throw new Error("staging/production 必须设置 HAHA_COOKIE_SECURE=true");
  }
  return secure;
}

function cookieBase(httpOnly: boolean) {
  return {
    httpOnly,
    secure: secureCookies(),
    sameSite: "lax" as const,
    path: "/",
  };
}

export async function backendFetch(path: string, init?: RequestInit): Promise<Response> {
  if (!path.startsWith("/api/") || path.includes("..")) {
    throw new Error("BFF 只允许访问后端 /api/** 路径");
  }
  return fetch(`${internalApiUrl()}${path}`, {
    ...init,
    cache: "no-store",
    redirect: "manual",
  });
}

export function validateSameOrigin(request: NextRequest): NextResponse | null {
  const origin = request.headers.get("origin");
  const forwardedHost = request.headers.get("x-forwarded-host")?.split(",", 1)[0]?.trim();
  const host = forwardedHost || request.headers.get("host")?.trim();
  const forwardedProto = request.headers.get("x-forwarded-proto")?.split(",", 1)[0]?.trim();
  const protocol = forwardedProto || request.nextUrl.protocol.replace(":", "");
  const expectedOrigin = host ? `${protocol}://${host}` : request.nextUrl.origin;
  if (!origin || origin !== expectedOrigin) {
    return NextResponse.json({ detail: "请求来源校验失败" }, { status: 403 });
  }
  return null;
}

export function validateCsrf(request: NextRequest): NextResponse | null {
  const originError = validateSameOrigin(request);
  if (originError) return originError;
  const cookieToken = request.cookies.get(CSRF_COOKIE)?.value ?? "";
  const headerToken = request.headers.get(CSRF_HEADER) ?? "";
  const cookieBuffer = Buffer.from(cookieToken);
  const headerBuffer = Buffer.from(headerToken);
  if (!cookieToken || cookieBuffer.length !== headerBuffer.length
    || !timingSafeEqual(cookieBuffer, headerBuffer)) {
    return NextResponse.json({ detail: "CSRF 校验失败" }, { status: 403 });
  }
  return null;
}

export function ensureCsrfCookie(request: NextRequest, response: NextResponse): void {
  if (request.cookies.get(CSRF_COOKIE)?.value) return;
  response.cookies.set(CSRF_COOKIE, randomBytes(32).toString("base64url"), {
    ...cookieBase(false),
    maxAge: 60 * 60 * 24,
  });
}

export function setSessionCookies(response: NextResponse, session: TokenPayload): void {
  response.cookies.set(ACCESS_COOKIE, session.access_token, {
    ...cookieBase(true),
    maxAge: session.expires_in,
  });
  response.cookies.set(REFRESH_COOKIE, session.refresh_token, {
    ...cookieBase(true),
    maxAge: Number(process.env.HAHA_REFRESH_TOKEN_TTL_SECONDS ?? 604800),
  });
}

export function clearSessionCookies(response: NextResponse): void {
  for (const name of [ACCESS_COOKIE, REFRESH_COOKIE, CSRF_COOKIE]) {
    response.cookies.set(name, "", { ...cookieBase(name !== CSRF_COOKIE), maxAge: 0 });
  }
}

export async function parseTokenResponse(response: Response): Promise<TokenPayload | null> {
  if (!response.ok) return null;
  const payload = await response.json() as Partial<TokenPayload>;
  if (!payload.access_token || !payload.refresh_token || !payload.account
    || typeof payload.expires_in !== "number") return null;
  return payload as TokenPayload;
}

export async function rotateSession(refreshToken: string): Promise<TokenPayload | null> {
  const key = createHash("sha256").update(refreshToken).digest("hex");
  const existing = refreshes.get(key);
  if (existing) return existing;
  const pending = backendFetch("/api/auth/refresh", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  }).then(parseTokenResponse);
  refreshes.set(key, pending);
  const timer = setTimeout(() => refreshes.delete(key), 5000);
  timer.unref();
  return pending;
}

export function publicAccount(session: TokenPayload) {
  return {
    authenticated: true,
    expires_in: session.expires_in,
    account: session.account,
  };
}

export function proxyResponse(upstream: Response): NextResponse {
  const headers = new Headers();
  for (const name of [
    "accept-ranges", "cache-control", "content-disposition", "content-length",
    "content-range", "content-type", "etag", "x-content-type-options", "x-request-id",
  ]) {
    const value = upstream.headers.get(name);
    if (value) headers.set(name, value);
  }
  return new NextResponse(upstream.status === 204 ? null : upstream.body, {
    status: upstream.status,
    headers,
  });
}
