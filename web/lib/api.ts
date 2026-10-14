export const AUTH_REQUIRED = process.env.NEXT_PUBLIC_AUTH_MODE === "jwt";
export const DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE === "true";
const API_BASE_URL = AUTH_REQUIRED
  ? "/api/backend"
  : process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

type JsonObject = Record<string, unknown>;
export type AuthSessionState = "unknown" | "authenticated" | "anonymous";
const authListeners = new Set<() => void>();
let authState: AuthSessionState = AUTH_REQUIRED ? "unknown" : "authenticated";
let authInitialization: Promise<boolean> | null = null;

function emitAuthSessionChange(): void {
  for (const listener of authListeners) listener();
}

export function subscribeAuthSession(listener: () => void): () => void {
  authListeners.add(listener);
  return () => { authListeners.delete(listener); };
}

export function getAuthSessionSnapshot(): AuthSessionState {
  return authState;
}

export function getServerAuthSessionSnapshot(): AuthSessionState {
  return AUTH_REQUIRED ? "unknown" : "authenticated";
}

function setAuthState(next: AuthSessionState): void {
  if (authState === next) return;
  authState = next;
  emitAuthSessionChange();
}

function csrfToken(): string {
  if (typeof document === "undefined") return "";
  const prefix = "haha_csrf=";
  const item = document.cookie.split("; ").find((value) => value.startsWith(prefix));
  return item ? decodeURIComponent(item.slice(prefix.length)) : "";
}

function headers(idempotencyKey?: string): Record<string, string> {
  const result: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (AUTH_REQUIRED) {
    const csrf = csrfToken();
    if (csrf) result["X-CSRF-Token"] = csrf;
  } else {
    result["X-Workspace-ID"] = process.env.NEXT_PUBLIC_WORKSPACE_ID ?? "local";
    result["X-User-ID"] = process.env.NEXT_PUBLIC_USER_ID ?? "local-user";
  }
  if (idempotencyKey) result["Idempotency-Key"] = idempotencyKey;
  return result;
}

export function saveAccessToken(token: string): void {
  void token;
}

export function hasAccessToken(): boolean {
  return !AUTH_REQUIRED || authState === "authenticated";
}

export function clearAuthSession(): void {
  setAuthState(AUTH_REQUIRED ? "anonymous" : "authenticated");
}

export async function initializeAuthSession(): Promise<boolean> {
  if (!AUTH_REQUIRED) return true;
  if (!authInitialization) authInitialization = fetch("/api/session", {
    cache: "no-store",
  }).then(async (response) => {
    const payload = await response.json().catch(() => ({ authenticated: false }));
    const authenticated = response.ok && payload.authenticated === true;
    setAuthState(authenticated ? "authenticated" : "anonymous");
    return authenticated;
  }).catch(() => {
    setAuthState("anonymous");
    return false;
  }).finally(() => { authInitialization = null; });
  return authInitialization;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, cache: "no-store" });
  if (!response.ok) {
    if (response.status === 401 && AUTH_REQUIRED) setAuthState("anonymous");
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(String(payload.detail ?? `请求失败：${response.status}`));
  }
  return response.json() as Promise<T>;
}

export type AuthSession = {
  authenticated: true; expires_in: number;
  account: { user_id: string; workspace_id: string; role: string };
};

export async function loginAccount(email: string, password: string, workspaceId: string): Promise<AuthSession> {
  const response = await fetch("/api/session/login", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, workspace_id: workspaceId }),
    cache: "no-store",
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: "登录失败" }));
    throw new Error(String(payload.detail ?? `登录失败：${response.status}`));
  }
  const session = await response.json() as AuthSession;
  setAuthState("authenticated");
  return session;
}

export async function logoutAccount(): Promise<void> {
  const response = await fetch("/api/session/logout", {
    method: "POST", headers: headers(), cache: "no-store",
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: "退出失败" }));
    throw new Error(String(payload.detail ?? `退出失败：${response.status}`));
  }
  clearAuthSession();
}

export async function getAuthenticatedAccount(): Promise<{ user_id: string; workspace_id: string; role: string; auth_mode: string }> {
  return request("/api/auth/me", { headers: headers() });
}

export type AccountSession = {
  id: string;
  status: "active" | "expired" | "revoked";
  is_current: boolean;
  created_at: string;
  last_used_at: string;
  expires_at: string;
  revoked_at: string;
};

export async function listAccountSessions(): Promise<{ items: AccountSession[]; count: number }> {
  return request("/api/auth/sessions", { headers: headers() });
}

export async function revokeAccountSession(sessionId: string): Promise<void> {
  await request(`/api/auth/sessions/${encodeURIComponent(sessionId)}`, {
    method: "DELETE", headers: headers(),
  });
}

export async function revokeAllAccountSessions(): Promise<number> {
  const result = await request<{ revoked: number }>("/api/auth/sessions", {
    method: "DELETE", headers: headers(),
  });
  clearAuthSession();
  return result.revoked;
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

export type BusinessRole = "viewer" | "buyer" | "learner" | "creator" | "contributor" | "seller" | "reviewer" | "admin";

export type IdentityRole = {
  id: string;
  role: BusinessRole;
  label: string;
  status: "active" | "revoked";
  is_active_context: boolean;
  created_at: string;
};

export type RoleApplication = {
  id: string;
  role: BusinessRole;
  status: "pending" | "approved" | "rejected" | "cancelled";
  reason: string;
  decision_note: string;
  reviewed_by: string;
  created_at: string;
  updated_at: string;
};

export type IdentityTask = {
  id: string;
  role: BusinessRole;
  kind: string;
  title: string;
  description: string;
  target_href: string;
  status: "open" | "completed" | "cancelled";
  created_at: string;
  completed_at: string;
};

export type IdentitySnapshot = {
  profile: {
    user_id: string;
    workspace_id: string;
    display_name: string;
    active_role: BusinessRole;
    personalization_enabled: boolean;
    created_at: string;
    updated_at: string;
  };
  roles: IdentityRole[];
  applications: RoleApplication[];
  tasks: IdentityTask[];
  available_actions: {
    self_activate: BusinessRole[];
    apply: BusinessRole[];
  };
};

export type UserCenterLibraryItem = {
  id: string; kind: "bookmark" | "want_to_learn" | "watch_later";
  target_id: string; title: string; target_href: string; updated_at: string;
};
export type UserCenterSnapshot = IdentitySnapshot & {
  account: { display_name: string; bio: string; region: string; profile_visibility: "private" | "members" | "public" };
  preferences: { history_enabled: boolean; recommendation_enabled: boolean; personalization_enabled: boolean; notification_enabled: boolean };
  library: UserCenterLibraryItem[];
  follows: { id: string; target_id: string; display_name: string; target_href: string; updated_at: string }[];
  history: { id: string; content_id: string; title: string; target_href: string; progress_seconds: number; duration_seconds: number; completed: boolean; viewed_at: string }[];
  notifications: { id: string; kind: string; title: string; body: string; target_href: string; read_at: string; created_at: string }[];
  summary: { bookmarks: number; want_to_learn: number; watch_later: number; following: number; history: number; unread_notifications: number; open_tasks: number };
  today: { continue_watching: UserCenterSnapshot["history"][number] | null; next_learning: UserCenterLibraryItem | null; open_tasks: number; unread_notifications: number };
};

export type WorkbenchSnapshot = {
  role: BusinessRole;
  label: string;
  headline: string;
  description: string;
  maturity: "operational" | "partial" | "blocked";
  metrics: { key: string; label: string; value: number }[];
  capabilities: {
    key: string;
    label: string;
    description: string;
    status: "available" | "limited" | "blocked";
    href: string;
    action_label: string;
    reason: string;
  }[];
  resources: {
    id: string;
    kind: string;
    title: string;
    subtitle: string;
    href: string;
    status: string;
  }[];
  tasks: IdentityTask[];
  boundary_note: string;
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

export async function getIdentityCenter(): Promise<IdentitySnapshot> {
  return request("/api/identity/me", { headers: headers() });
}

export async function activateBusinessRole(role: BusinessRole): Promise<IdentitySnapshot> {
  return request(`/api/identity/roles/${role}/activate`, {
    method: "POST",
    headers: headers(),
  });
}

export async function switchIdentityContext(role: BusinessRole): Promise<IdentitySnapshot> {
  return request("/api/identity/context", {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ role }),
  });
}

export async function applyForBusinessRole(role: BusinessRole, reason: string): Promise<RoleApplication> {
  return request("/api/identity/role-applications", {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ role, reason }),
  });
}

export async function completeIdentityTask(taskId: string): Promise<IdentityTask> {
  return request(`/api/identity/tasks/${taskId}/complete`, {
    method: "POST",
    headers: headers(),
  });
}

export async function getUserCenter(): Promise<UserCenterSnapshot> {
  return request("/api/user-center", { headers: headers() });
}
export async function getIdentityWorkbench(): Promise<WorkbenchSnapshot> {
  return request("/api/identity/workbench", { headers: headers() });
}
export async function updateUserCenterProfile(payload: UserCenterSnapshot["account"]): Promise<UserCenterSnapshot> {
  return request("/api/user-center/profile", { method: "PATCH", headers: headers(), body: JSON.stringify(payload) });
}
export async function updateUserCenterPreferences(payload: UserCenterSnapshot["preferences"]): Promise<UserCenterSnapshot> {
  return request("/api/user-center/preferences", { method: "PATCH", headers: headers(), body: JSON.stringify(payload) });
}
export async function setUserCenterLibrary(kind: UserCenterLibraryItem["kind"], targetId: string, title: string, targetHref: string, active = true): Promise<UserCenterSnapshot> {
  return request(`/api/user-center/library/${kind}/${encodeURIComponent(targetId)}`, {
    method: active ? "PUT" : "DELETE", headers: headers(),
    body: active ? JSON.stringify({ title, target_href: targetHref }) : undefined,
  });
}
export async function setUserCenterFollow(targetId: string, displayName: string, targetHref: string, active = true): Promise<UserCenterSnapshot> {
  return request(`/api/user-center/follows/${encodeURIComponent(targetId)}`, {
    method: active ? "PUT" : "DELETE", headers: headers(),
    body: active ? JSON.stringify({ display_name: displayName, target_href: targetHref }) : undefined,
  });
}
export async function recordUserCenterHistory(contentId: string, title: string, targetHref: string, progressSeconds = 0, durationSeconds = 0): Promise<void> {
  await request(`/api/user-center/history/${encodeURIComponent(contentId)}`, { method: "PUT", headers: headers(), body: JSON.stringify({ title, target_href: targetHref, progress_seconds: progressSeconds, duration_seconds: durationSeconds }) });
}
export async function clearUserCenterHistory(): Promise<{ removed: number }> {
  return request("/api/user-center/history", { method: "DELETE", headers: headers() });
}
export async function markUserCenterNotificationRead(id: string): Promise<void> {
  await request(`/api/user-center/notifications/${encodeURIComponent(id)}/read`, { method: "POST", headers: headers() });
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
