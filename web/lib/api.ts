const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
export const AUTH_REQUIRED = process.env.NEXT_PUBLIC_AUTH_MODE === "jwt";
export const DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE === "true";

type JsonObject = Record<string, unknown>;

function headers(idempotencyKey?: string): HeadersInit {
  const result: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (AUTH_REQUIRED) {
    const token = globalThis.sessionStorage?.getItem("haha_access_token") ?? "";
    if (token) result.Authorization = `Bearer ${token}`;
  } else {
    result["X-Workspace-ID"] = process.env.NEXT_PUBLIC_WORKSPACE_ID ?? "local";
    result["X-User-ID"] = process.env.NEXT_PUBLIC_USER_ID ?? "local-user";
  }
  if (idempotencyKey) result["Idempotency-Key"] = idempotencyKey;
  return result;
}

export function saveAccessToken(token: string): void {
  if (AUTH_REQUIRED && token.trim()) globalThis.sessionStorage?.setItem("haha_access_token", token.trim());
}

export function hasAccessToken(): boolean {
  return !AUTH_REQUIRED || Boolean(globalThis.sessionStorage?.getItem("haha_access_token"));
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, cache: "no-store" });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(String(payload.detail ?? `请求失败：${response.status}`));
  }
  return response.json() as Promise<T>;
}

export type RunResult = {
  id: string;
  status: string;
  error_message: string;
  script: null | { payload: JsonObject; evidence: JsonObject };
};

export async function createProject(title: string): Promise<{ id: string }> {
  return request("/api/projects", {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ title }),
  });
}

export async function createBrief(projectId: string, payload: JsonObject): Promise<{ id: string }> {
  return request(`/api/projects/${projectId}/briefs`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(payload),
  });
}

export async function createRun(projectId: string, briefId: string): Promise<{ id: string }> {
  return request(`/api/projects/${projectId}/runs`, {
    method: "POST",
    headers: headers(crypto.randomUUID()),
    body: JSON.stringify({ brief_version_id: briefId, model_preference: "本地演示" }),
  });
}

export async function getRun(runId: string): Promise<RunResult> {
  return request(`/api/runs/${runId}`, { headers: headers() });
}
