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
  attempt?: number;
  error_code?: string;
  error_message: string;
  updated_at?: string;
  script: null | { payload: JsonObject; evidence: JsonObject };
};

export type RunEvent = {
  event: "run.status" | "run.terminal" | "run.timeout" | "run.deleted";
  id?: string;
  data: {
    run_id: string;
    status?: string;
    attempt?: number;
    updated_at?: string;
    error_code?: string;
    error_message?: string;
    terminal: boolean;
  };
};

export type FailedJob = {
  id: string;
  run_id: string;
  reason: string;
  created_at: string;
  resolved_at: string;
  run: Omit<RunResult, "script"> & { attempt: number; error_code: string };
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

export async function cancelRun(runId: string): Promise<RunResult> {
  const run = await request<Omit<RunResult, "script">>(`/api/runs/${runId}/cancel`, {
    method: "POST",
    headers: headers(),
  });
  return { ...run, script: null };
}

export async function listFailedJobs(): Promise<{ items: FailedJob[]; count: number }> {
  return request("/api/failed-jobs", { headers: headers() });
}

export async function retryFailedJob(
  failedJobId: string,
): Promise<{ failed_job: Omit<FailedJob, "run">; run: RunResult; execution: string }> {
  const result = await request<{
    failed_job: Omit<FailedJob, "run">;
    run: Omit<RunResult, "script">;
    execution: string;
  }>(`/api/failed-jobs/${failedJobId}/retry`, {
    method: "POST",
    headers: headers(),
  });
  return { ...result, run: { ...result.run, script: null } };
}

export async function resolveFailedJob(failedJobId: string): Promise<void> {
  await request(`/api/failed-jobs/${failedJobId}/resolve`, {
    method: "POST",
    headers: headers(),
  });
}

function parseEventBlock(block: string): RunEvent | null {
  let event = "";
  let id = "";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("id:")) id = line.slice(3).trim();
    if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
  }
  if (!event || data.length === 0) return null;
  return {
    event: event as RunEvent["event"],
    id: id || undefined,
    data: JSON.parse(data.join("\n")) as RunEvent["data"],
  };
}

export async function streamRunEvents(
  runId: string,
  onEvent: (event: RunEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  let lastEventId = "";
  while (!signal?.aborted) {
    const streamHeaders = new Headers(headers());
    if (lastEventId) streamHeaders.set("Last-Event-ID", lastEventId);
    const response = await fetch(
      `${API_BASE_URL}/api/runs/${runId}/events?timeout_seconds=30`,
      { headers: streamHeaders, cache: "no-store", signal },
    );
    if (!response.ok || !response.body) {
      const payload = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(String(payload.detail ?? `状态流连接失败：${response.status}`));
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let terminal = false;
    while (!terminal) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done }).replaceAll("\r\n", "\n");
      let boundary = buffer.indexOf("\n\n");
      while (boundary >= 0) {
        const parsed = parseEventBlock(buffer.slice(0, boundary));
        buffer = buffer.slice(boundary + 2);
        boundary = buffer.indexOf("\n\n");
        if (!parsed) continue;
        if (parsed.id) lastEventId = parsed.id;
        onEvent(parsed);
        terminal = parsed.data.terminal;
      }
      if (done) break;
    }
    if (terminal) return;
  }
}
