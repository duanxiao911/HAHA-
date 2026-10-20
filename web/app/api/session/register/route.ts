import { NextRequest, NextResponse } from "next/server";
import {
  backendFetch, ensureCsrfCookie, parseTokenResponse, publicAccount,
  setSessionCookies, validateSameOrigin,
} from "@/lib/bff-session";

export async function POST(request: NextRequest) {
  const originError = validateSameOrigin(request);
  if (originError) return originError;
  const contentLength = Number(request.headers.get("content-length") ?? 0);
  if (contentLength > 8192) {
    return NextResponse.json({ detail: "注册请求过大" }, { status: 413 });
  }
  const body = await request.text();
  const upstream = await backendFetch("/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  });
  const session = await parseTokenResponse(upstream);
  if (!session) {
    if (upstream.ok) {
      return NextResponse.json({ detail: "认证服务响应格式无效" }, { status: 502 });
    }
    const payload = await upstream.json().catch(() => ({ detail: "注册失败" }));
    return NextResponse.json(payload, { status: upstream.status });
  }
  const response = NextResponse.json(publicAccount(session), { status: 201 });
  setSessionCookies(response, session);
  ensureCsrfCookie(request, response);
  return response;
}
