import type {
  CommunityAdapter,
  CommunityImportPreview,
  CommunityImportResult,
  CommunityChangeListener,
  CreateCommentInput,
  CreateDraftInput,
  CreateTimedAnnotationInput,
  FeedQuery,
  PageResult,
  SearchQuery,
} from "./contract";
import { normalizeCommunityPageLimit } from "./contract";
import { COMMUNITY_SEED, type CommunitySeed } from "./seed";
import {
  CommunityDataError,
  LOCAL_DEMO_VIEWER_ID,
  LOCAL_DEMO_WORKSPACE_ID,
  type CommunityComment,
  type CommunityNotification,
  type CommunitySearchHit,
  type CommunitySnapshot,
  type ContentDetail,
  type ContentSummary,
  type EntityId,
  type ReactionKind,
  type SubmissionDraft,
  type SubmissionDraftPatch,
  type SubmissionStatus,
  type TimedKnowledgeAnnotation,
  type WatchHistoryEntry,
} from "./types";

export const COMMUNITY_LOCAL_SCHEMA_VERSION = 1;
export const COMMUNITY_LOCAL_STORAGE_KEY =
  `haha.community.state.v${COMMUNITY_LOCAL_SCHEMA_VERSION}:${LOCAL_DEMO_WORKSPACE_ID}:${LOCAL_DEMO_VIEWER_ID}`;

interface LocalPersistedStateV1 {
  schemaVersion: 1;
  revision: number;
  viewerId: typeof LOCAL_DEMO_VIEWER_ID;
  workspaceId: typeof LOCAL_DEMO_WORKSPACE_ID;
  reactions: Record<EntityId, ReactionKind[]>;
  followingPersonIds: EntityId[];
  history: WatchHistoryEntry[];
  comments: CommunityComment[];
  annotations: TimedKnowledgeAnnotation[];
  notifications: CommunityNotification[];
  searchHistory: string[];
  drafts: SubmissionDraft[];
}

type RuntimeState = CommunitySnapshot["runtime"];

const DEFAULT_NOTIFICATION_TIME = "2026-10-12T08:00:00.000Z";

function entity(id: string, now: string) {
  return {
    id,
    workspaceId: LOCAL_DEMO_WORKSPACE_ID,
    provenance: "local_demo" as const,
    createdAt: now,
    updatedAt: now,
  };
}

function createDefaultState(): LocalPersistedStateV1 {
  return {
    schemaVersion: COMMUNITY_LOCAL_SCHEMA_VERSION,
    revision: 0,
    viewerId: LOCAL_DEMO_VIEWER_ID,
    workspaceId: LOCAL_DEMO_WORKSPACE_ID,
    reactions: {},
    followingPersonIds: [],
    history: [],
    comments: [],
    annotations: [],
    notifications: [
      {
        ...entity("notification-demo-welcome", DEFAULT_NOTIFICATION_TIME),
        recipientId: LOCAL_DEMO_VIEWER_ID,
        kind: "system",
        title: "欢迎进入 HAHA 本地演示环境",
        body: "互动、历史、评论和投稿草稿只保存在当前浏览器，不代表真实账号数据。",
      },
      {
        ...entity("notification-demo-source", "2026-10-12T08:05:00.000Z"),
        recipientId: LOCAL_DEMO_VIEWER_ID,
        kind: "system",
        title: "来源与事实功能可体验",
        body: "内容中的来源、事实和人物均带有演示标记；真实 API 接入后再执行服务端核验。",
        targetHref: "/?channel=hot",
      },
    ],
    searchHistory: [],
    drafts: [],
  };
}

function clone<T>(value: T): T {
  return globalThis.structuredClone(value);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parsePersistedState(raw: string): LocalPersistedStateV1 {
  const parsed: unknown = JSON.parse(raw);
  if (!isRecord(parsed)) throw new Error("根数据不是对象");
  if (parsed.schemaVersion !== COMMUNITY_LOCAL_SCHEMA_VERSION) {
    throw new Error(`不支持的数据版本：${String(parsed.schemaVersion)}`);
  }
  if (parsed.viewerId !== LOCAL_DEMO_VIEWER_ID || parsed.workspaceId !== LOCAL_DEMO_WORKSPACE_ID) {
    throw new Error("演示身份或工作空间不匹配");
  }
  const arrays = [
    "followingPersonIds",
    "history",
    "comments",
    "annotations",
    "notifications",
    "searchHistory",
    "drafts",
  ] as const;
  for (const key of arrays) {
    if (!Array.isArray(parsed[key])) throw new Error(`${key} 不是数组`);
  }
  if (!isRecord(parsed.reactions)) throw new Error("reactions 不是对象");
  return parsed as unknown as LocalPersistedStateV1;
}

function nowIso(): string {
  return new Date().toISOString();
}

function newId(prefix: string): string {
  const suffix = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}_${suffix}`;
}

function assertNotAborted(signal?: AbortSignal): void {
  if (signal?.aborted) throw new CommunityDataError("aborted", "操作已取消");
}

function normalizedCursor(cursor?: string): number {
  if (!cursor) return 0;
  const parsed = Number.parseInt(cursor, 10);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : 0;
}

function page<T>(items: T[], cursor?: string, limit = 20): PageResult<T> {
  const start = normalizedCursor(cursor);
  const safeLimit = normalizeCommunityPageLimit(limit) ?? 20;
  const result = items.slice(start, start + safeLimit);
  const next = start + result.length;
  return {
    items: clone(result),
    nextCursor: next < items.length ? String(next) : null,
    total: items.length,
  };
}

const ALLOWED_SUBMISSION_TRANSITIONS: Record<SubmissionStatus, SubmissionStatus[]> = {
  draft: ["checking", "archived"],
  checking: ["needs_revision", "submitted"],
  needs_revision: ["checking", "archived"],
  submitted: ["reviewing", "archived"],
  reviewing: ["approved", "needs_revision", "rejected"],
  approved: ["scheduled", "published", "archived"],
  scheduled: ["published", "archived"],
  published: ["archived"],
  rejected: ["needs_revision", "archived"],
  archived: [],
};

export class LocalCommunityAdapter implements CommunityAdapter {
  private persisted = createDefaultState();
  private runtime: RuntimeState = {
    mode: "local_demo",
    hydrated: false,
    persistence: "memory",
    recoveryNotice: null,
    schemaVersion: COMMUNITY_LOCAL_SCHEMA_VERSION,
    dataNotice: "本地演示数据：并非真实账号、真实发布内容或服务端审核结果。",
  };
  private readonly listeners = new Set<CommunityChangeListener>();
  private storageListening = false;
  private readonly onStorage = (event: StorageEvent): void => {
    if (event.key !== COMMUNITY_LOCAL_STORAGE_KEY || event.storageArea !== globalThis.localStorage) return;
    if (event.newValue === null) {
      this.persisted = createDefaultState();
      this.runtime = { ...this.runtime, recoveryNotice: "另一个标签页已重置本地演示数据。" };
      this.emit();
      return;
    }
    try {
      this.persisted = parsePersistedState(event.newValue);
      this.runtime = { ...this.runtime, recoveryNotice: null };
    } catch {
      this.runtime = { ...this.runtime, recoveryNotice: "另一个标签页写入了无法识别的数据；当前标签页保留原状态。" };
    }
    this.emit();
  };

  constructor(private readonly seed: CommunitySeed = COMMUNITY_SEED) {}

  hydrate(): void {
    if (typeof window === "undefined") {
      this.runtime = { ...this.runtime, hydrated: true, persistence: "memory" };
      this.emit();
      return;
    }
    if (!this.storageListening) {
      window.addEventListener("storage", this.onStorage);
      this.storageListening = true;
    }
    if (this.runtime.hydrated) return;
    try {
      const raw = window.localStorage.getItem(COMMUNITY_LOCAL_STORAGE_KEY);
      if (raw) this.persisted = parsePersistedState(raw);
      this.runtime = {
        ...this.runtime,
        hydrated: true,
        persistence: "local_storage",
        recoveryNotice: null,
      };
    } catch (error) {
      this.persisted = createDefaultState();
      let recoveryNotice = "本地演示数据不可用，已恢复为初始状态。";
      try {
        window.localStorage.removeItem(COMMUNITY_LOCAL_STORAGE_KEY);
      } catch {
        recoveryNotice = "浏览器存储不可用，当前改动只在本标签页内保留。";
      }
      this.runtime = {
        ...this.runtime,
        hydrated: true,
        persistence: "memory",
        recoveryNotice: `${recoveryNotice}${error instanceof Error ? `（${error.message}）` : ""}`,
      };
    }
    this.emit();
  }

  dispose(): void {
    if (typeof window !== "undefined" && this.storageListening) {
      window.removeEventListener("storage", this.onStorage);
      this.storageListening = false;
    }
  }

  subscribe(listener: CommunityChangeListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private emit(): void {
    for (const listener of this.listeners) listener();
  }

  private persist(): void {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(COMMUNITY_LOCAL_STORAGE_KEY, JSON.stringify(this.persisted));
      this.runtime = { ...this.runtime, persistence: "local_storage" };
    } catch {
      this.runtime = {
        ...this.runtime,
        persistence: "memory",
        recoveryNotice: "浏览器存储空间不足或不可用，本次改动只在当前标签页保留。",
      };
    }
  }

  private mutate(mutator: (next: LocalPersistedStateV1) => void): void {
    const next = clone(this.persisted);
    mutator(next);
    next.revision += 1;
    this.persisted = next;
    this.persist();
    this.emit();
  }

  private contentOrThrow(contentId: EntityId): ContentDetail {
    const content = this.getSnapshot().contents.find((item) => item.id === contentId);
    if (!content) throw new CommunityDataError("not_found", "内容不存在");
    return content;
  }

  private draftOrThrow(draftId: EntityId): SubmissionDraft {
    const draft = this.persisted.drafts.find((item) => item.id === draftId);
    if (!draft) throw new CommunityDataError("not_found", "投稿草稿不存在");
    return draft;
  }

  getSnapshot(): CommunitySnapshot {
    const historyByContent = new Map(this.persisted.history.map((entry) => [entry.contentId, entry]));
    const contents = this.seed.contents.map((seedContent) => {
      const content = clone(seedContent);
      const reactions = [...(this.persisted.reactions[content.id] ?? [])];
      const history = historyByContent.get(content.id);
      const localCommentCount = this.persisted.comments.filter(
        (comment) => comment.contentId === content.id && comment.status === "visible",
      ).length;
      for (const reaction of reactions) content.reactionCounts[reaction] += 1;
      content.metrics.interactionCount += reactions.length + localCommentCount;
      content.metrics.commentCount += localCommentCount;
      if (reactions.includes("bookmark")) content.metrics.bookmarkCount += 1;
      content.viewer = {
        reactions,
        followedCreator: this.persisted.followingPersonIds.includes(content.creatorId),
        viewed: Boolean(history),
        watchProgressSeconds: history?.progressSeconds ?? 0,
      };
      return content;
    });
    return {
      runtime: clone(this.runtime),
      viewer: {
        id: LOCAL_DEMO_VIEWER_ID,
        workspaceId: LOCAL_DEMO_WORKSPACE_ID,
        displayName: "HAHA 本地体验者",
        authState: "local_demo",
        roleLabel: "演示身份（未登录）",
      },
      contents,
      projects: clone(this.seed.projects),
      people: clone(this.seed.people),
      regions: clone(this.seed.regions),
      sources: clone(this.seed.sources),
      facts: clone(this.seed.facts),
      followingPersonIds: [...this.persisted.followingPersonIds],
      history: clone(this.persisted.history),
      comments: clone(this.persisted.comments),
      annotations: clone(this.persisted.annotations),
      notifications: clone(this.persisted.notifications),
      searchHistory: [...this.persisted.searchHistory],
      drafts: clone(this.persisted.drafts),
    };
  }

  async getFeed(query: FeedQuery, signal?: AbortSignal): Promise<PageResult<ContentSummary>> {
    assertNotAborted(signal);
    const snapshot = this.getSnapshot();
    let items = snapshot.contents;
    if (query.mode === "following") {
      items = items.filter((content) => snapshot.followingPersonIds.includes(content.creatorId));
    } else if (query.mode === "learning") {
      items = items.filter((content) => content.viewer.reactions.includes("want_to_learn"));
    } else if (query.mode === "nearby" && query.regionId) {
      items = items.filter((content) => content.regionId === query.regionId);
    }
    if (query.channelId && !["hot", "recommended", "following"].includes(query.channelId)) {
      const channel = query.channelId.toLocaleLowerCase("zh-CN");
      items = items.filter((content) =>
        content.categoryId.toLocaleLowerCase("zh-CN") === channel ||
        content.categoryLabel.toLocaleLowerCase("zh-CN") === channel,
      );
    }
    items = [...items].sort((a, b) => {
      const trustDelta = Number(b.trust.status === "verified") - Number(a.trust.status === "verified");
      return trustDelta || b.metrics.interactionCount - a.metrics.interactionCount;
    });
    assertNotAborted(signal);
    return page(items, query.cursor, query.limit);
  }

  async getContent(contentId: EntityId, signal?: AbortSignal): Promise<ContentDetail> {
    assertNotAborted(signal);
    return clone(this.contentOrThrow(contentId));
  }

  async search(query: SearchQuery, signal?: AbortSignal): Promise<PageResult<CommunitySearchHit>> {
    assertNotAborted(signal);
    const term = query.query.trim().toLocaleLowerCase("zh-CN");
    if (!term) return page([], query.cursor, query.limit);
    const snapshot = this.getSnapshot();
    const hits: CommunitySearchHit[] = [];
    const score = (...values: string[]): number => values.reduce((total, value, index) => {
      const normalized = value.toLocaleLowerCase("zh-CN");
      if (normalized === term) return total + 100 - index;
      if (normalized.startsWith(term)) return total + 50 - index;
      if (normalized.includes(term)) return total + 20 - index;
      return total;
    }, 0);
    if (!query.scope || query.scope === "all" || query.scope === "content") {
      for (const content of snapshot.contents) {
        const relevance = score(content.title, content.summary, content.categoryLabel, content.regionLabel, content.creator.displayName, ...content.tags);
        if (relevance > 0) hits.push({ kind: "content", id: content.id, title: content.title, summary: `${content.categoryLabel} · ${content.regionLabel} · ${content.creator.displayName}`, href: `/content/${content.id}`, score: relevance, verificationStatus: content.trust.status });
      }
    }
    if (!query.scope || query.scope === "all" || query.scope === "project") {
      for (const project of snapshot.projects) {
        const relevance = score(project.name, project.summary, project.category, ...project.materials, ...project.techniques);
        if (relevance > 0) hits.push({ kind: "project", id: project.id, title: project.name, summary: project.summary, href: `/heritage-projects/${project.id}`, score: relevance, verificationStatus: project.verificationStatus });
      }
    }
    if (!query.scope || query.scope === "all" || query.scope === "person") {
      for (const person of snapshot.people) {
        const relevance = score(person.displayName, person.bio, person.role);
        if (relevance > 0) hits.push({ kind: "person", id: person.id, title: person.displayName, summary: person.bio, href: `/profiles/${person.id}`, score: relevance, verificationStatus: person.verified ? "verified" : "pending" });
      }
    }
    if (!query.scope || query.scope === "all" || query.scope === "region") {
      for (const region of snapshot.regions) {
        const relevance = score(region.name, region.province, region.summary, ...region.featuredCrafts);
        if (relevance > 0) hits.push({ kind: "region", id: region.id, title: region.name, summary: region.featuredCrafts.join(" · "), href: `/map?region=${encodeURIComponent(region.id)}`, score: relevance });
      }
    }
    const contentById = new Map(snapshot.contents.map((content) => [content.id, content]));
    const verificationRank: Record<string, number> = {
      verified: 5,
      inheritor_confirmed: 4,
      expert_reviewed: 3,
      pending: 2,
      disputed: 1,
    };
    if (query.sort === "latest") {
      hits.sort((a, b) =>
        (contentById.get(b.id)?.publishedAt ?? "").localeCompare(contentById.get(a.id)?.publishedAt ?? "") ||
        b.score - a.score ||
        a.title.localeCompare(b.title, "zh-CN"));
    } else if (query.sort === "popular") {
      hits.sort((a, b) =>
        (contentById.get(b.id)?.metrics.viewCount ?? 0) - (contentById.get(a.id)?.metrics.viewCount ?? 0) ||
        b.score - a.score ||
        a.title.localeCompare(b.title, "zh-CN"));
    } else if (query.sort === "verified") {
      hits.sort((a, b) =>
        (verificationRank[b.verificationStatus ?? ""] ?? 0) - (verificationRank[a.verificationStatus ?? ""] ?? 0) ||
        b.score - a.score ||
        a.title.localeCompare(b.title, "zh-CN"));
    } else {
      hits.sort((a, b) => b.score - a.score || a.title.localeCompare(b.title, "zh-CN"));
    }
    assertNotAborted(signal);
    return page(hits, query.cursor, query.limit);
  }

  async setReaction(contentId: EntityId, reaction: ReactionKind, active: boolean): Promise<ContentSummary> {
    this.contentOrThrow(contentId);
    this.mutate((next) => {
      const current = new Set(next.reactions[contentId] ?? []);
      if (active) current.add(reaction); else current.delete(reaction);
      if (current.size) next.reactions[contentId] = [...current]; else delete next.reactions[contentId];
    });
    return this.contentOrThrow(contentId);
  }

  async setPersonFollow(personId: EntityId, active: boolean): Promise<boolean> {
    if (!this.seed.people.some((person) => person.id === personId)) throw new CommunityDataError("not_found", "人物不存在");
    this.mutate((next) => {
      const following = new Set(next.followingPersonIds);
      if (active) following.add(personId); else following.delete(personId);
      next.followingPersonIds = [...following];
    });
    return active;
  }

  async recordWatchHistory(contentId: EntityId, progressSeconds = 0): Promise<WatchHistoryEntry> {
    const content = this.contentOrThrow(contentId);
    const duration = content.durationSeconds ?? Number.POSITIVE_INFINITY;
    const progress = Math.max(0, Math.min(progressSeconds, duration));
    const entry: WatchHistoryEntry = {
      contentId,
      viewedAt: nowIso(),
      progressSeconds: progress,
      completed: Number.isFinite(duration) && duration > 0 ? progress / duration >= 0.9 : false,
    };
    this.mutate((next) => {
      next.history = [entry, ...next.history.filter((item) => item.contentId !== contentId)].slice(0, 100);
    });
    return clone(entry);
  }

  async removeWatchHistory(contentId: EntityId): Promise<void> {
    this.mutate((next) => { next.history = next.history.filter((entry) => entry.contentId !== contentId); });
  }

  async clearWatchHistory(): Promise<void> {
    this.mutate((next) => { next.history = []; });
  }

  async createComment(input: CreateCommentInput): Promise<CommunityComment> {
    this.contentOrThrow(input.contentId);
    const body = input.body.trim();
    if (!body || body.length > 1000) throw new CommunityDataError("validation", "评论需为 1–1000 个字符");
    if (input.parentId) {
      const parent = this.persisted.comments.find((comment) => comment.id === input.parentId && comment.status === "visible");
      if (!parent || parent.contentId !== input.contentId) throw new CommunityDataError("validation", "回复目标无效");
    }
    const now = nowIso();
    const comment: CommunityComment = {
      ...entity(newId("comment"), now),
      contentId: input.contentId,
      authorId: LOCAL_DEMO_VIEWER_ID,
      authorName: "HAHA 本地体验者",
      body,
      parentId: input.parentId,
      status: "visible",
    };
    this.mutate((next) => { next.comments.unshift(comment); });
    return clone(comment);
  }

  async deleteOwnComment(commentId: EntityId): Promise<void> {
    const comment = this.persisted.comments.find((item) => item.id === commentId);
    if (!comment || comment.authorId !== LOCAL_DEMO_VIEWER_ID) throw new CommunityDataError("not_found", "找不到可删除的本地评论");
    this.mutate((next) => {
      const target = next.comments.find((item) => item.id === commentId);
      if (target) {
        target.status = "deleted";
        target.body = "评论已由本地体验者删除";
        target.updatedAt = nowIso();
      }
    });
  }

  async createTimedAnnotation(input: CreateTimedAnnotationInput): Promise<TimedKnowledgeAnnotation> {
    const content = this.contentOrThrow(input.contentId);
    const body = input.body.trim();
    const maxTime = content.durationSeconds ?? 24 * 60 * 60;
    if (!body || body.length > 1000) throw new CommunityDataError("validation", "知识注释需为 1–1000 个字符");
    if (!Number.isFinite(input.timestampSeconds) || input.timestampSeconds < 0 || input.timestampSeconds > maxTime) throw new CommunityDataError("validation", "知识注释的时间点超出内容范围");
    const sourceIds = [...new Set(input.sourceIds ?? [])];
    if (sourceIds.some((sourceId) => !this.seed.sources.some((source) => source.id === sourceId))) throw new CommunityDataError("validation", "知识注释包含未知来源");
    const now = nowIso();
    const annotation: TimedKnowledgeAnnotation = {
      ...entity(newId("annotation"), now),
      contentId: input.contentId,
      authorId: LOCAL_DEMO_VIEWER_ID,
      authorName: "HAHA 本地体验者",
      timestampSeconds: Math.round(input.timestampSeconds),
      body,
      kind: input.kind,
      verificationStatus: "pending",
      sourceIds,
    };
    this.mutate((next) => { next.annotations.unshift(annotation); });
    return clone(annotation);
  }

  async deleteOwnTimedAnnotation(annotationId: EntityId): Promise<void> {
    const annotation = this.persisted.annotations.find((item) => item.id === annotationId);
    if (!annotation || annotation.authorId !== LOCAL_DEMO_VIEWER_ID) throw new CommunityDataError("not_found", "找不到可删除的本地知识注释");
    this.mutate((next) => { next.annotations = next.annotations.filter((item) => item.id !== annotationId); });
  }

  async markNotificationRead(notificationId: EntityId): Promise<void> {
    if (!this.persisted.notifications.some((item) => item.id === notificationId)) throw new CommunityDataError("not_found", "消息不存在");
    this.mutate((next) => {
      const target = next.notifications.find((item) => item.id === notificationId);
      if (target && !target.readAt) {
        target.readAt = nowIso();
        target.updatedAt = target.readAt;
      }
    });
  }

  async markAllNotificationsRead(): Promise<void> {
    const now = nowIso();
    this.mutate((next) => {
      for (const notification of next.notifications) {
        if (!notification.readAt) {
          notification.readAt = now;
          notification.updatedAt = now;
        }
      }
    });
  }

  async deleteNotification(notificationId: EntityId): Promise<void> {
    this.mutate((next) => { next.notifications = next.notifications.filter((item) => item.id !== notificationId); });
  }

  async rememberSearchTerm(term: string): Promise<string[]> {
    const clean = term.trim().slice(0, 100);
    if (!clean) return [...this.persisted.searchHistory];
    this.mutate((next) => {
      next.searchHistory = [clean, ...next.searchHistory.filter((item) => item !== clean)].slice(0, 10);
    });
    return [...this.persisted.searchHistory];
  }

  async removeSearchTerm(term: string): Promise<string[]> {
    this.mutate((next) => { next.searchHistory = next.searchHistory.filter((item) => item !== term); });
    return [...this.persisted.searchHistory];
  }

  async clearSearchHistory(): Promise<void> {
    this.mutate((next) => { next.searchHistory = []; });
  }

  async previewLocalArchive(
    _localState: Record<string, unknown>,
  ): Promise<CommunityImportPreview> {
    throw new CommunityDataError("validation", "本地演示模式没有服务端账户可供迁移");
  }

  async importLocalArchive(
    _localState: Record<string, unknown>,
  ): Promise<CommunityImportResult> {
    throw new CommunityDataError("validation", "本地演示模式没有服务端账户可供迁移");
  }

  async createSubmissionDraft(input: CreateDraftInput): Promise<SubmissionDraft> {
    const now = nowIso();
    const draft: SubmissionDraft = {
      ...entity(newId("submission"), now),
      ownerId: LOCAL_DEMO_VIEWER_ID,
      submissionType: input.submissionType,
      status: "draft",
      version: 1,
      title: input.title?.trim().slice(0, 200) ?? "",
      summary: "",
      projectIds: [],
      personIds: [],
      sourceIds: [],
      tags: [],
      assets: [],
      aiDisclosure: "none",
    };
    this.mutate((next) => { next.drafts.unshift(draft); });
    return clone(draft);
  }

  async uploadSubmissionAsset(draftId: EntityId, file: File): Promise<SubmissionDraft> {
    const kind = file.type.startsWith("video/") ? "video" : file.type.startsWith("image/") ? "image" : null;
    if (!kind) throw new CommunityDataError("validation", "本地演示只登记视频或图片元数据");
    const current = this.draftOrThrow(draftId);
    return this.updateSubmissionDraft(draftId, {
      assets: [...current.assets, {
        id: newId("local-asset"),
        name: file.name,
        kind,
        mimeType: file.type,
        sizeBytes: file.size,
        localOnly: true,
      }],
    });
  }

  async deleteSubmissionAsset(draftId: EntityId, assetId: EntityId): Promise<SubmissionDraft> {
    const current = this.draftOrThrow(draftId);
    return this.updateSubmissionDraft(draftId, {
      assets: current.assets.filter((asset) => asset.id !== assetId),
    });
  }

  async updateSubmissionDraft(draftId: EntityId, patch: SubmissionDraftPatch): Promise<SubmissionDraft> {
    const current = this.draftOrThrow(draftId);
    if (!["draft", "needs_revision", "rejected"].includes(current.status)) throw new CommunityDataError("conflict", "当前投稿状态不可编辑");
    if (patch.title !== undefined && patch.title.trim().length > 200) throw new CommunityDataError("validation", "标题不能超过 200 个字符");
    if (patch.summary !== undefined && patch.summary.trim().length > 4000) throw new CommunityDataError("validation", "简介不能超过 4000 个字符");
    this.mutate((next) => {
      const target = next.drafts.find((draft) => draft.id === draftId);
      if (!target) return;
      Object.assign(target, clone(patch), {
        title: patch.title === undefined ? target.title : patch.title.trim(),
        summary: patch.summary === undefined ? target.summary : patch.summary.trim(),
        updatedAt: nowIso(),
        version: target.version + 1,
      });
    });
    return clone(this.draftOrThrow(draftId));
  }

  async transitionSubmissionDraft(draftId: EntityId, nextStatus: SubmissionStatus, reviewerNote?: string): Promise<SubmissionDraft> {
    const current = this.draftOrThrow(draftId);
    if (!ALLOWED_SUBMISSION_TRANSITIONS[current.status].includes(nextStatus)) throw new CommunityDataError("invalid_transition", `投稿状态不能从 ${current.status} 变为 ${nextStatus}`);
    if (["checking", "submitted"].includes(nextStatus) && (!current.title.trim() || !current.summary.trim())) throw new CommunityDataError("validation", "进入检查或提交前必须填写标题和简介");
    const now = nowIso();
    this.mutate((next) => {
      const target = next.drafts.find((draft) => draft.id === draftId);
      if (!target) return;
      target.status = nextStatus;
      target.updatedAt = now;
      target.version += 1;
      if (reviewerNote !== undefined) target.reviewerNote = reviewerNote.trim().slice(0, 2000);
      if (nextStatus === "submitted") target.submittedAt = now;
      if (nextStatus === "published") target.publishedAt = now;
      if (["needs_revision", "approved", "rejected", "published"].includes(nextStatus)) {
        next.notifications.unshift({
          ...entity(newId("notification"), now),
          recipientId: LOCAL_DEMO_VIEWER_ID,
          kind: "review",
          title: `投稿状态已更新：${nextStatus}`,
          body: target.reviewerNote || "这是本地演示审核状态，不代表平台正式审核结果。",
          targetHref: `/creator?submission=${target.submissionType}&draft=${target.id}`,
        });
      }
    });
    return clone(this.draftOrThrow(draftId));
  }

  async deleteSubmissionDraft(draftId: EntityId): Promise<void> {
    const draft = this.draftOrThrow(draftId);
    if (!["draft", "archived"].includes(draft.status)) throw new CommunityDataError("conflict", "只有草稿或已归档投稿可以删除");
    this.mutate((next) => { next.drafts = next.drafts.filter((item) => item.id !== draftId); });
  }

  async resetLocalDemoState(): Promise<void> {
    this.persisted = createDefaultState();
    this.runtime = { ...this.runtime, recoveryNotice: "本地演示互动数据已重置。" };
    if (typeof window !== "undefined") {
      try {
        window.localStorage.removeItem(COMMUNITY_LOCAL_STORAGE_KEY);
        this.runtime = { ...this.runtime, persistence: "local_storage" };
      } catch {
        this.runtime = { ...this.runtime, persistence: "memory" };
      }
    }
    this.emit();
  }
}

export function createLocalCommunityAdapter(seed: CommunitySeed = COMMUNITY_SEED): LocalCommunityAdapter {
  return new LocalCommunityAdapter(seed);
}
