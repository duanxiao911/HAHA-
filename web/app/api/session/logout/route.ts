import { NextRequest, NextResponse } from "next/server";
import {
  backendFetch, clearSessionCookies, REFRESH_COOKIE, validateCsrf,
} from "@/lib/bff-session";

export async function POST(request: NextRequest) {
  const csrfError = validateCsrf(request);
  if (csrfError) return csrfError;
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
