import { NextRequest, NextResponse } from "next/server";
import {
  backendFetch, clearSessionCookies, REFRESH_COOKIE, validateCsrf, validateSameOrigin,
} from "@/lib/bff-session";

export async function POST(request: NextRequest) {
  const originError = validateSameOrigin(request);
  if (originError) return originError;
  const csrfError = validateCsrf(request);
  if (csrfError) {
    // A stale or duplicated CSRF cookie must not trap a same-origin user in an
    // unrecoverable session. Logout is safe after the origin has been verified.
    const response = new NextResponse(null, { status: 204 });
    clearSessionCookies(response);
    return response;
  }
  const refreshToken = request.cookies.get(REFRESH_COOKIE)?.value ?? "";
  if (refreshToken) {
    await backendFetch("/api/auth/logout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  }
  const response = new NextResponse(null, { status: 204 });
  clearSessionCookies(response);
  return response;
}

