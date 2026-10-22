export const AUTH_REQUIRED = process.env.NEXT_PUBLIC_AUTH_MODE === "jwt";
export const DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE === "true";
const API_BASE_URL = AUTH_REQUIRED
  ? "/api/backend"
  : process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

type JsonObject = Record<string, unknown>;
export class ApiRequestError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}
export type AuthSessionState = "unknown" | "authenticated" | "anonymous";
const authListeners = new Set<() => void>();
let authState: AuthSessionState = AUTH_REQUIRED ? "unknown" : "authenticated";
let authAccountKey = AUTH_REQUIRED
  ? "anonymous"
  : `${process.env.NEXT_PUBLIC_USER_ID ?? "local-user"}:${process.env.NEXT_PUBLIC_WORKSPACE_ID ?? "local"}`;
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

export function getAuthAccountSnapshot(): string {
  return authAccountKey;
}

export function getServerAuthAccountSnapshot(): string {
  return AUTH_REQUIRED ? "unknown" : authAccountKey;
}

function setAuthSession(next: AuthSessionState, account?: { user_id: string; workspace_id: string }): void {
  const nextKey = account ? `${account.user_id}:${account.workspace_id}` : next;
  if (authState === next && authAccountKey === nextKey) return;
  authState = next;
  authAccountKey = nextKey;
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
  setAuthSession(AUTH_REQUIRED ? "anonymous" : "authenticated");
}

export async function initializeAuthSession(): Promise<boolean> {
  if (!AUTH_REQUIRED) return true;
  if (!authInitialization) authInitialization = fetch("/api/session", {
    cache: "no-store",
  }).then(async (response) => {
    const payload = await response.json().catch(() => ({ authenticated: false }));
    const authenticated = response.ok && payload.authenticated === true;
    setAuthSession(
      authenticated ? "authenticated" : "anonymous",
      authenticated ? payload.account : undefined,
    );
    return authenticated;
  }).catch(() => {
    setAuthSession("anonymous");
    return false;
  }).finally(() => { authInitialization = null; });
  return authInitialization;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, cache: "no-store" });
  if (!response.ok) {
    if (response.status === 401 && AUTH_REQUIRED) setAuthSession("anonymous");
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    throw new ApiRequestError(
      response.status,
      String(payload.detail ?? `请求失败：${response.status}`),
    );
  }
  return response.json() as Promise<T>;
}

/** Auth-aware transport shared by bounded-context client adapters. */
export async function communityApiRequest<T>(
  path: string,
  init: RequestInit = {},
  idempotencyKey?: string,
): Promise<T> {
  const merged = new Headers(headers(idempotencyKey));
  new Headers(init.headers).forEach((value, key) => merged.set(key, value));
  return request<T>(path, { ...init, headers: merged });
}

export type AuthSession = {
  authenticated: true; expires_in: number;
  account: { user_id: string; workspace_id: string; role: string };
};

export async function loginAccount(email: string, password: string): Promise<AuthSession> {
  const response = await fetch("/api/session/login", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
    cache: "no-store",
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: "登录失败" }));
    throw new Error(String(payload.detail ?? `登录失败：${response.status}`));
  }
  const session = await response.json() as AuthSession;
  setAuthSession("authenticated", session.account);
  return session;
}

export async function registerAccount(
  displayName: string, email: string, password: string,
): Promise<AuthSession> {
  const response = await fetch("/api/session/register", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ display_name: displayName, email, password }),
    cache: "no-store",
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: "注册失败" }));
    throw new Error(String(payload.detail ?? `注册失败：${response.status}`));
  }
  const session = await response.json() as AuthSession;
  setAuthSession("authenticated", session.account);
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

export async function changeAccountPassword(
  currentPassword: string,
  newPassword: string,
): Promise<{ changed: boolean; revoked_sessions: number; requires_login: boolean }> {
  return request("/api/auth/password/change", {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
}

export async function exportUserCenterData(): Promise<Record<string, unknown>> {
  return request("/api/user-center/export", { headers: headers() });
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
  consumer_capabilities: BusinessRole[];
  professional_roles: BusinessRole[];
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
  footprint: { saved_assets: number; following: number; watched_items: number; completed_views: number; active_days: number; first_activity_at: string; latest_activity_at: string };
  growth: {
    active_roles: number; completed_tasks: number; open_tasks: number; has_cultural_footprint: boolean;
    learning_paths: number; completed_paths: number; completed_units: number; knowledge_cards: number;
    quiz_attempts: number; passed_quizzes: number; achievements: number; achievement_points: number;
    current_streak: number; longest_streak: number; last_learning_date: string;
  };
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

export type PlatformCapabilities = {
  contract_version: "platform-capabilities.v1";
  catalog_scope: { status: "decision_required" | "approved"; mode: string; reason: string };
  modules: {
    key: "community" | "commerce" | "learning" | "identity";
    label: string; href: string; status: "available" | "limited" | "blocked"; reason: string;
    features?: { ai_tutor?: { status: "available" | "blocked"; reason: string } };
  }[];
};

export type LearningQuestion = {
  id: string; position: number; prompt: string; choices: string[]; source_id: string; version: number;
};

export type LearningUnitSnapshot = {
  id: string; path_id: string; position: number; kind: "lesson" | "quiz"; title: string;
  summary: string; source_id: string; version: number; required: boolean; estimated_minutes: number;
  progress: { status: "not_started" | "in_progress" | "completed"; progress_percent: number; version: number; updated_at: string };
  quiz?: { id: string; title: string; version: number; pass_score: number; questions: LearningQuestion[] };
};

export type TutorCitation = {
  source_id: string; title: string; publisher: string; url: string;
  version: string; trust_status: "reviewed_internal";
};

export type TutorInteraction = {
  id: string; question: string; status: "completed"; answer: string;
  citations: TutorCitation[]; uncertainty: string; suggested_questions: string[];
  mode: "grounded_model" | "no_sources"; model: string; request_id: string;
  input_tokens: number; output_tokens: number; latency_ms: number; created_at: string;
};

export type LearningSnapshot = {
  profile: { timezone: string; current_streak: number; longest_streak: number; last_learning_date: string; version: number };
  paths: {
    id: string; title: string; summary: string; status: string; version: number; provenance: string;
    verification_status: string; source_note: string; completion_percent: number;
    enrollment: null | { id: string; status: "active" | "completed"; version: number; source_content_id: string };
    units: LearningUnitSnapshot[];
  }[];
  sources: { id: string; title: string; publisher: string; source_type: string; url: string; version: number; verification_status: string; provenance: string; checked_at: string }[];
  learning_candidates: UserCenterLibraryItem[];
  cards: { id: string; path_id: string; unit_id: string; topic: string; body: string; source_id: string; source_version: number; trust_status: string; version: number; updated_at: string }[];
  quiz_attempts: { id: string; quiz_id: string; quiz_version: number; score: number; passed: boolean; created_at: string }[];
  daily_tasks: { id: string; task_date: string; kind: string; title: string; target_count: number; current_count: number; status: "open" | "completed"; version: number }[];
  achievements: { id: string; code: string; title: string; description: string; points: number; definition_version: number; granted_at: string }[];
  recent_events: { id: string; event_type: string; entity_type: string; entity_id: string; entity_version: number; created_at: string }[];
  summary: { learning_paths: number; completed_paths: number; completed_units: number; knowledge_cards: number; quiz_attempts: number; passed_quizzes: number; achievements: number; achievement_points: number; current_streak: number; longest_streak: number; last_learning_date: string };
  ai_tutor: {
    status: "available" | "blocked"; reason: string; model: string;
    knowledge_version: string; supported_scope: string; request_limit_24h: number;
  };
  tutor_history: TutorInteraction[];
  catalog_notice: string;
  last_quiz_result?: { attempt_id: string; score: number; passed: boolean; correct: number; total: number };
  last_tutor_result?: TutorInteraction;
};

export type CommerceProduct = {
  id: string; workspace_id: string; store_id: string; seller_user_id: string;
  title: string; summary: string; price_cents: number; currency: "CNY";
  source_note: string; provenance: string;
  category_id: string; craft_type: string; origin_region: string; season_tag: string;
  status: "draft" | "submitted" | "approved" | "rejected" | "listed" | "delisted";
  version: number; reviewer_note: string; reviewed_by: string; updated_at: string;
  category: null | { id: string; slug: string; name: string; description: string; sort_order: number; status: string };
  media: { id: string; media_type: "image" | "video"; url: string; alt_text: string; source_note: string; rights_status: string; sort_order: number; version: number }[];
  variants: { id: string; sku: string; name: string; price_cents: number; attributes_json: string; is_default: 0 | 1; status: string; version: number }[];
  heritage_links: { id: string; heritage_ref: string; relation_type: string; claim_status: string; source_note: string; version: number }[];
  inventory: { available_qty: number; sold_qty: number; version: number; updated_at: string };
  trust?: { status: string; label: string; platform_endorsement: false };
};

export type CommerceCategory = { id: string; slug: string; name: string; description: string; sort_order: number; status: string };

export type CommerceCatalog = {
  items: CommerceProduct[]; total: number; page: number; page_size: number; has_more: boolean;
  categories: CommerceCategory[];
  filters: { query: string; category: string; craft_type: string; origin_region: string; season_tag: string; sort: string };
};

export type CommerceAdvisorResult = {
  id: string; question: string; answer: string; mode: string; model: string; provider: string;
  request_id: string; input_tokens: number; output_tokens: number; created_at: string;
  suggestions: string[];
  recommendations: { product: CommerceProduct; reason: string }[];
};

export type CommerceAdvisorSnapshot = {
  advisor: { status: "available" | "blocked"; reason: string; model: string; request_limit_24h: number; authority: "recommend_only" };
  history: CommerceAdvisorResult[];
  last_result?: CommerceAdvisorResult;
};

export type CommerceOrder = {
  id: string; buyer_user_id: string; seller_user_id: string; store_id: string;
  status: "awaiting_sandbox_payment" | "paid" | "shipped" | "completed" | "after_sales" | "cancelled";
  total_cents: number; currency: "CNY"; version: number; created_at: string; updated_at: string;
  items: { id: string; product_id: string; title_snapshot: string; unit_price_cents: number; quantity: number }[];
  payment: null | { provider: "internal_sandbox"; status: "authorized"; amount_cents: number; created_at: string };
  fulfillment: null | { status: "shipped" | "delivered"; tracking_note: string; version: number };
};

export type CommerceSnapshot = {
  roles: BusinessRole[];
  store: null | { id: string; name: string; status: string; version: number };
  catalog: CommerceProduct[];
  seller_products: CommerceProduct[];
  review_queue: CommerceProduct[];
  cart: { id: string; product_id: string; quantity: number; version: number; product: CommerceProduct | null }[];
  buyer_orders: CommerceOrder[];
  seller_orders: CommerceOrder[];
  buyer_after_sales: { id: string; order_id: string; reason: string; status: string; decision_note: string; version: number }[];
  seller_after_sales: { id: string; order_id: string; reason: string; status: string; decision_note: string; version: number }[];
  categories: CommerceCategory[];
  seller_insights: null | {
    product_status_counts: Record<string, number>; order_count: number;
    completed_order_count: number; completed_revenue_cents: number;
    actionable: { drafts_to_finish: number; orders_to_ship: number; after_sales_to_handle: number };
    scope: "internal_sandbox_only"; generated_at: string;
  };
  sandbox: { status: "internal_test_only"; payment_provider: "internal_sandbox"; real_money_moved: false; notice: string; checkout_scope: "single_store"; production_gates: Record<"payment" | "logistics" | "public_release", { status: "blocked"; reason: string }> };
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
export async function getPlatformCapabilities(): Promise<PlatformCapabilities> {
  return request("/api/platform/capabilities", { headers: headers() });
}
export async function getLearningCenter(): Promise<LearningSnapshot> {
  return request("/api/learning", { headers: headers() });
}
export async function enrollLearningPath(pathId: string, sourceContentId = ""): Promise<LearningSnapshot> {
  return request(`/api/learning/paths/${encodeURIComponent(pathId)}/enroll`, {
    method: "POST", headers: headers(crypto.randomUUID()),
    body: JSON.stringify({ source_content_id: sourceContentId }),
  });
}
export async function completeLearningUnit(unitId: string, expectedVersion: number): Promise<LearningSnapshot> {
  return request(`/api/learning/units/${encodeURIComponent(unitId)}/complete`, {
    method: "POST", headers: headers(crypto.randomUUID()),
    body: JSON.stringify({ expected_version: expectedVersion }),
  });
}
export async function saveLearningKnowledgeCard(
  unitId: string, topic: string, body: string, expectedVersion: number,
): Promise<LearningSnapshot> {
  return request(`/api/learning/cards/${encodeURIComponent(unitId)}`, {
    method: "PUT", headers: headers(crypto.randomUUID()),
    body: JSON.stringify({ topic, body, expected_version: expectedVersion }),
  });
}
export async function submitLearningQuiz(
  quizId: string, answers: Record<string, number>, expectedProgressVersion: number,
): Promise<LearningSnapshot> {
  return request(`/api/learning/quizzes/${encodeURIComponent(quizId)}/attempts`, {
    method: "POST", headers: headers(crypto.randomUUID()),
    body: JSON.stringify({ answers, expected_progress_version: expectedProgressVersion }),
  });
}
export async function askLearningTutor(question: string): Promise<LearningSnapshot> {
  return request("/api/learning/tutor/questions", {
    method: "POST", headers: headers(crypto.randomUUID()),
    body: JSON.stringify({ question }),
  });
}
export async function getCommerceCenter(): Promise<CommerceSnapshot> {
  return request("/api/commerce", { headers: headers() });
}
export async function getCommerceCatalog(params: URLSearchParams = new URLSearchParams()): Promise<CommerceCatalog> {
  const query = params.toString();
  return request(`/api/commerce/catalog${query ? `?${query}` : ""}`, { headers: headers() });
}
export async function getCommerceProduct(productId: string): Promise<CommerceProduct> {
  return request(`/api/commerce/products/${encodeURIComponent(productId)}`, { headers: headers() });
}
export async function getCommerceAdvisor(): Promise<CommerceAdvisorSnapshot> {
  return request("/api/commerce/advisor", { headers: headers() });
}
export async function askCommerceAdvisor(question: string): Promise<CommerceAdvisorSnapshot> {
  return request("/api/commerce/advisor/messages", {
    method: "POST",
    headers: headers(crypto.randomUUID()),
    body: JSON.stringify({ question }),
  });
}
export async function openCommerceStore(name: string): Promise<CommerceSnapshot> {
  return request("/api/commerce/stores", { method: "POST", headers: headers(), body: JSON.stringify({ name }) });
}
export async function createCommerceProduct(payload: { title: string; summary: string; price_cents: number; source_note: string; category_slug?: string; craft_type?: string; origin_region?: string; season_tag?: string }): Promise<CommerceSnapshot> {
  return request("/api/commerce/products", { method: "POST", headers: headers(crypto.randomUUID()), body: JSON.stringify(payload) });
}
export async function updateCommerceProduct(productId: string, payload: { title: string; summary: string; price_cents: number; source_note: string; category_slug: string; craft_type: string; origin_region: string; season_tag: string; expected_version: number }): Promise<CommerceSnapshot> {
  return request(`/api/commerce/products/${encodeURIComponent(productId)}`, { method: "PUT", headers: headers(), body: JSON.stringify(payload) });
}
export async function uploadCommerceProductImage(productId: string, file: File, altText: string, sourceNote: string, expectedVersion: number): Promise<CommerceSnapshot> {
  const uploadHeaders = headers();
  uploadHeaders["Content-Type"] = file.type;
  uploadHeaders["X-Upload-Filename"] = encodeURIComponent(file.name);
  uploadHeaders["X-Image-Alt"] = encodeURIComponent(altText);
  uploadHeaders["X-Image-Source"] = encodeURIComponent(sourceNote);
  const response = await fetch(`${API_BASE_URL}/api/commerce/products/${encodeURIComponent(productId)}/images?expected_version=${expectedVersion}`, {
    method: "PUT", headers: uploadHeaders, body: file, credentials: "include",
  });
  if (!response.ok) throw new ApiRequestError(response.status, await response.text());
  return response.json();
}
export async function deleteCommerceProductImage(productId: string, mediaId: string, expectedVersion: number): Promise<CommerceSnapshot> {
  return request(`/api/commerce/products/${encodeURIComponent(productId)}/images/${encodeURIComponent(mediaId)}?expected_version=${expectedVersion}`, { method: "DELETE", headers: headers() });
}
export function commerceMediaUrl(mediaId: string): string {
  return `${API_BASE_URL}/api/commerce/media/${encodeURIComponent(mediaId)}`;
}
export async function submitCommerceProduct(productId: string, expectedVersion: number): Promise<CommerceSnapshot> {
  return request(`/api/commerce/products/${encodeURIComponent(productId)}/submit`, { method: "POST", headers: headers(), body: JSON.stringify({ expected_version: expectedVersion }) });
}
export async function reviewCommerceProduct(productId: string, decision: "approved" | "rejected", note: string, expectedVersion: number): Promise<CommerceSnapshot> {
  return request(`/api/commerce/products/${encodeURIComponent(productId)}/review`, { method: "POST", headers: headers(), body: JSON.stringify({ decision, note, expected_version: expectedVersion }) });
}
export async function updateCommerceInventory(productId: string, quantity: number, expectedVersion: number): Promise<CommerceSnapshot> {
  return request(`/api/commerce/products/${encodeURIComponent(productId)}/inventory`, { method: "PUT", headers: headers(), body: JSON.stringify({ quantity, expected_version: expectedVersion }) });
}
export async function updateCommerceCart(productId: string, quantity: number, expectedVersion: number): Promise<CommerceSnapshot> {
  return request(`/api/commerce/cart/${encodeURIComponent(productId)}`, { method: "PUT", headers: headers(), body: JSON.stringify({ quantity, expected_version: expectedVersion }) });
}
export async function removeCommerceCartItem(productId: string): Promise<CommerceSnapshot> {
  return request(`/api/commerce/cart/${encodeURIComponent(productId)}`, { method: "DELETE", headers: headers() });
}
export async function checkoutCommerceCart(): Promise<CommerceSnapshot> {
  return request("/api/commerce/checkout", { method: "POST", headers: headers(crypto.randomUUID()) });
}
export async function payCommerceSandboxOrder(orderId: string, expectedVersion: number): Promise<CommerceSnapshot> {
  return request(`/api/commerce/orders/${encodeURIComponent(orderId)}/sandbox-payment`, { method: "POST", headers: headers(crypto.randomUUID()), body: JSON.stringify({ expected_version: expectedVersion }) });
}
export async function cancelCommerceOrder(orderId: string, expectedVersion: number): Promise<CommerceSnapshot> {
  return request(`/api/commerce/orders/${encodeURIComponent(orderId)}/cancel`, { method: "POST", headers: headers(), body: JSON.stringify({ expected_version: expectedVersion }) });
}
export async function shipCommerceOrder(orderId: string, expectedVersion: number, trackingNote: string): Promise<CommerceSnapshot> {
  return request(`/api/commerce/orders/${encodeURIComponent(orderId)}/ship`, { method: "POST", headers: headers(), body: JSON.stringify({ expected_version: expectedVersion, tracking_note: trackingNote }) });
}
export async function confirmCommerceDelivery(orderId: string, expectedVersion: number): Promise<CommerceSnapshot> {
  return request(`/api/commerce/orders/${encodeURIComponent(orderId)}/confirm-delivery`, { method: "POST", headers: headers(), body: JSON.stringify({ expected_version: expectedVersion }) });
}
export async function requestCommerceAfterSale(orderId: string, expectedVersion: number, reason: string): Promise<CommerceSnapshot> {
  return request(`/api/commerce/orders/${encodeURIComponent(orderId)}/after-sales`, { method: "POST", headers: headers(), body: JSON.stringify({ expected_version: expectedVersion, reason }) });
}
export async function decideCommerceAfterSale(afterSaleId: string, expectedVersion: number, decision: "approved" | "rejected", note: string): Promise<CommerceSnapshot> {
  return request(`/api/commerce/after-sales/${encodeURIComponent(afterSaleId)}/decision`, { method: "POST", headers: headers(), body: JSON.stringify({ expected_version: expectedVersion, decision, note }) });
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
export async function deleteUserCenterNotification(id: string): Promise<void> {
  await request(`/api/user-center/notifications/${encodeURIComponent(id)}`, { method: "DELETE", headers: headers() });
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
