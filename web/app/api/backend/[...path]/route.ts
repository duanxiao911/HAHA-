import { NextRequest, NextResponse } from "next/server";
import {
  ACCESS_COOKIE, backendFetch, clearSessionCookies, proxyResponse,
  REFRESH_COOKIE, rotateSession, setSessionCookies, validateCsrf,
} from "@/lib/bff-session";

type RouteContext = { params: Promise<{ path: string[] }> };
const MUTATIONS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

async function handle(request: NextRequest, context: RouteContext) {
  if (MUTATIONS.has(request.method)) {
    const csrfError = validateCsrf(request);
    if (csrfError) return csrfError;
  }
  const { path } = await context.params;
  if (!path.length || path[0] !== "api" || path.some((part) => part === "..")) {
    return NextResponse.json({ detail: "BFF 路径不允许" }, { status: 404 });
  }
  const targetPath = `/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`;
  const tokenEndpoints = new Set(["/api/auth/login", "/api/auth/refresh", "/api/auth/logout"]);
  if (tokenEndpoints.has(`/${path.map(encodeURIComponent).join("/")}`)) {
    return NextResponse.json({ detail: "令牌端点只能通过安全会话接口访问" }, { status: 404 });
  }
  const isMediaUpload = request.method === "PUT"
    && path.length === 5
    && path[0] === "api"
    && path[1] === "community"
    && path[2] === "submissions"
    && path[4] === "assets";
  const bodyLimit = isMediaUpload ? 25 * 1024 * 1024 : 1024 * 1024;
  const declaredLength = Number(request.headers.get("content-length") ?? 0);
  if (declaredLength > bodyLimit) {
    return NextResponse.json({ detail: `BFF 请求体超过 ${isMediaUpload ? "25 MiB" : "1 MiB"} 限制` }, { status: 413 });
  }
  const body = ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer();
  const contentLength = Number(request.headers.get("content-length") ?? body?.byteLength ?? 0);
  if (contentLength > bodyLimit) {
    return NextResponse.json({ detail: `BFF 请求体超过 ${isMediaUpload ? "25 MiB" : "1 MiB"} 限制` }, { status: 413 });
  }
  let accessToken = request.cookies.get(ACCESS_COOKIE)?.value ?? "";
  const refreshToken = request.cookies.get(REFRESH_COOKIE)?.value ?? "";
  let rotated = null;
  if (!accessToken && refreshToken) {
    rotated = await rotateSession(refreshToken);
    accessToken = rotated?.access_token ?? "";
  }
  const call = (token: string) => {
    const headers = new Headers();
    for (const name of ["content-type", "idempotency-key", "last-event-id", "range", "x-request-id", "x-upload-filename", "x-upload-kind"]) {
      const value = request.headers.get(name);
      if (value) headers.set(name, value);
    }
    if (token) headers.set("Authorization", `Bearer ${token}`);
    return backendFetch(targetPath, { method: request.method, headers, body });
  };
  let upstream = await call(accessToken);
  if (upstream.status === 401 && refreshToken && !rotated) {
    rotated = await rotateSession(refreshToken);
    if (rotated) upstream = await call(rotated.access_token);
  }
  const response = proxyResponse(upstream);
  if (rotated) setSessionCookies(response, rotated);
  if (upstream.status === 401 && !rotated) clearSessionCookies(response);
  return response;
}

export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const PATCH = handle;
export const DELETE = handle;
