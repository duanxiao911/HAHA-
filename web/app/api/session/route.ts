import { NextRequest, NextResponse } from "next/server";
import {
  ACCESS_COOKIE, backendFetch, clearSessionCookies, ensureCsrfCookie,
  REFRESH_COOKIE, rotateSession, setSessionCookies,
} from "@/lib/bff-session";

async function account(accessToken: string): Promise<Response> {
  return backendFetch("/api/auth/me", {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}

export async function GET(request: NextRequest) {
  const recoveryRequested = request.nextUrl.searchParams.get("recover") === "confirm";
  const fetchSite = request.headers.get("sec-fetch-site") ?? "none";
  if (recoveryRequested && (fetchSite === "same-origin" || fetchSite === "none")) {
    const response = NextResponse.redirect(
      new URL("/login?logged-out=1", request.url),
      303,
    );
    clearSessionCookies(response);
    return response;
  }
  let accessToken = request.cookies.get(ACCESS_COOKIE)?.value ?? "";
  const refreshToken = request.cookies.get(REFRESH_COOKIE)?.value ?? "";
  let upstream = accessToken ? await account(accessToken) : null;
  let rotated = null;
  if ((!upstream || upstream.status === 401) && refreshToken) {
    rotated = await rotateSession(refreshToken);
    if (rotated) {
      accessToken = rotated.access_token;
      upstream = await account(accessToken);
    }
  }
  if (!upstream?.ok) {
    const response = NextResponse.json({ authenticated: false }, { status: 200 });
    clearSessionCookies(response);
    ensureCsrfCookie(request, response);
    return response;
  }
  const response = NextResponse.json({ authenticated: true, account: await upstream.json() });
  if (rotated) setSessionCookies(response, rotated);
  ensureCsrfCookie(request, response);
  return response;
}

