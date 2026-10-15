import { ApiRequestError, communityApiRequest } from "@/lib/api";

import { normalizeCommunityPageLimit } from "./contract";

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
import {
  CommunityDataError,
  type CommunityComment,
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

function emptySnapshot(): CommunitySnapshot {
  return {
    runtime: {
      mode: "api",
      hydrated: false,
      persistence: "postgresql",
      recoveryNotice: null,
      schemaVersion: 2,
      dataNotice: "正在连接服务端内容与账户数据。",
    },
    viewer: {
      id: "",
      workspaceId: "",
      displayName: "",
      authState: "authenticated",
      roleLabel: "viewer",
    },
    contents: [],
    projects: [],
    people: [],
    regions: [],
    sources: [],
    facts: [],
    followingPersonIds: [],
    history: [],
    comments: [],
    annotations: [],
    notifications: [],
    searchHistory: [],
    drafts: [],
  };
}

function translateError(error: unknown): CommunityDataError {
  if (error instanceof CommunityDataError) return error;
  if (error instanceof ApiRequestError) {
    if (error.status === 404) return new CommunityDataError("not_found", error.message);
    if (error.status === 409) return new CommunityDataError("conflict", error.message);
    if (error.status === 400 || error.status === 422) {
      return new CommunityDataError("validation", error.message);
    }
    return new CommunityDataError("storage_unavailable", error.message, error.status >= 500);
  }
  return new CommunityDataError(
    "storage_unavailable",
    error instanceof Error ? error.message : "服务端社区请求失败",
    true,
  );
}

function queryString(values: Record<string, string | number | undefined>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  return params.toString();
}

export class ApiCommunityAdapter implements CommunityAdapter {
  private snapshot = emptySnapshot();
  private readonly listeners = new Set<CommunityChangeListener>();
  private searchHistory: string[] = [];
  private disposed = false;

  hydrate(): void {
    void this.refresh().catch(() => undefined);
  }

  dispose(): void {
    this.disposed = true;
    this.listeners.clear();
  }

  subscribe(listener: CommunityChangeListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  getSnapshot(): CommunitySnapshot {
    return this.snapshot;
  }

  private emit(): void {
    if (this.disposed) return;
    for (const listener of this.listeners) listener();
  }

  private async refresh(): Promise<CommunitySnapshot> {
    try {
      const next = await communityApiRequest<CommunitySnapshot>("/api/community/bootstrap");
      if (this.disposed) return this.snapshot;
      this.snapshot = {
        ...next,
        searchHistory: [...this.searchHistory],
        runtime: { ...next.runtime, hydrated: true, recoveryNotice: null },
      };
      this.emit();
      return this.snapshot;
    } catch (error) {
      const translated = translateError(error);
      if (!this.disposed) {
        this.snapshot = {
          ...this.snapshot,
          runtime: {
            ...this.snapshot.runtime,
            hydrated: true,
            recoveryNotice: `服务端数据不可用：${translated.message}`,
          },
        };
        this.emit();
      }
      throw translated;
    }
  }

  async getFeed(query: FeedQuery, signal?: AbortSignal): Promise<PageResult<ContentSummary>> {
    try {
      return await communityApiRequest<PageResult<ContentSummary>>(`/api/community/feed?${queryString({
        mode: query.mode,
        channel_id: query.channelId,
        region_id: query.regionId,
        cursor: query.cursor,
        limit: normalizeCommunityPageLimit(query.limit),
      })}`, { signal });
    } catch (error) {
      throw translateError(error);
    }
  }

  async getContent(contentId: EntityId, signal?: AbortSignal): Promise<ContentDetail> {
    try {
      return await communityApiRequest<ContentDetail>(
        `/api/community/contents/${encodeURIComponent(contentId)}`,
        { signal },
      );
    } catch (error) {
      throw translateError(error);
    }
  }

  async search(query: SearchQuery, signal?: AbortSignal): Promise<PageResult<CommunitySearchHit>> {
    try {
      return await communityApiRequest<PageResult<CommunitySearchHit>>(`/api/community/search?${queryString({
        q: query.query,
        scope: query.scope,
        sort: query.sort,
        cursor: query.cursor,
        limit: normalizeCommunityPageLimit(query.limit),
      })}`, { signal });
    } catch (error) {
      throw translateError(error);
    }
  }

  async setReaction(contentId: EntityId, reaction: ReactionKind, active: boolean): Promise<ContentSummary> {
    try {
      const content = await communityApiRequest<ContentSummary>(
        `/api/community/contents/${encodeURIComponent(contentId)}/reactions/${reaction}`,
        { method: active ? "PUT" : "DELETE" },
      );
      await this.refresh();
      return content;
    } catch (error) {
      throw translateError(error);
    }
  }

  async setPersonFollow(personId: EntityId, active: boolean): Promise<boolean> {
    try {
      await communityApiRequest(
        `/api/community/people/${encodeURIComponent(personId)}/follow`,
        { method: active ? "PUT" : "DELETE" },
      );
      await this.refresh();
      return active;
    } catch (error) {
      throw translateError(error);
    }
  }

  async recordWatchHistory(contentId: EntityId, progressSeconds = 0): Promise<WatchHistoryEntry> {
    try {
      await communityApiRequest(
        `/api/community/contents/${encodeURIComponent(contentId)}/history`,
        { method: "PUT", body: JSON.stringify({ progress_seconds: progressSeconds }) },
      );
      const snapshot = await this.refresh();
      const entry = snapshot.history.find((item) => item.contentId === contentId);
      if (!entry) throw new CommunityDataError("not_found", "观看历史写入后未找到记录");
      return entry;
    } catch (error) {
      throw translateError(error);
    }
  }

  async removeWatchHistory(contentId: EntityId): Promise<void> {
    try {
      await communityApiRequest(`/api/community/contents/${encodeURIComponent(contentId)}/history`, {
        method: "DELETE",
      });
      await this.refresh();
    } catch (error) {
      throw translateError(error);
    }
  }

  async clearWatchHistory(): Promise<void> {
    try {
      await communityApiRequest("/api/user-center/history", { method: "DELETE" });
      await this.refresh();
    } catch (error) {
      throw translateError(error);
    }
  }

  async createComment(input: CreateCommentInput): Promise<CommunityComment> {
    try {
      const comment = await communityApiRequest<CommunityComment>(
        `/api/community/contents/${encodeURIComponent(input.contentId)}/comments`,
        {
          method: "POST",
          body: JSON.stringify({ body: input.body, parent_id: input.parentId ?? "" }),
        },
      );
      await this.refresh();
      return comment;
    } catch (error) {
      throw translateError(error);
    }
  }

  async deleteOwnComment(commentId: EntityId): Promise<void> {
    try {
      await communityApiRequest(`/api/community/comments/${encodeURIComponent(commentId)}`, {
        method: "DELETE",
      });
      await this.refresh();
    } catch (error) {
      throw translateError(error);
    }
  }

  async createTimedAnnotation(input: CreateTimedAnnotationInput): Promise<TimedKnowledgeAnnotation> {
    try {
      const annotation = await communityApiRequest<TimedKnowledgeAnnotation>(
        `/api/community/contents/${encodeURIComponent(input.contentId)}/annotations`,
        {
          method: "POST",
          body: JSON.stringify({
            timestamp_seconds: input.timestampSeconds,
            body: input.body,
            kind: input.kind,
            source_ids: input.sourceIds ?? [],
          }),
        },
      );
      await this.refresh();
      return annotation;
    } catch (error) {
      throw translateError(error);
    }
  }

  async deleteOwnTimedAnnotation(annotationId: EntityId): Promise<void> {
    try {
      await communityApiRequest(`/api/community/annotations/${encodeURIComponent(annotationId)}`, {
        method: "DELETE",
      });
      await this.refresh();
    } catch (error) {
      throw translateError(error);
    }
  }

  async markNotificationRead(notificationId: EntityId): Promise<void> {
    try {
      await communityApiRequest(`/api/user-center/notifications/${encodeURIComponent(notificationId)}/read`, {
        method: "POST",
      });
      await this.refresh();
    } catch (error) {
      throw translateError(error);
    }
  }

  async markAllNotificationsRead(): Promise<void> {
    try {
      const unread = this.snapshot.notifications.filter((item) => !item.readAt);
      await Promise.all(unread.map((item) => communityApiRequest(
        `/api/user-center/notifications/${encodeURIComponent(item.id)}/read`,
        { method: "POST" },
      )));
      await this.refresh();
    } catch (error) {
      throw translateError(error);
    }
  }

  async deleteNotification(notificationId: EntityId): Promise<void> {
    try {
      await communityApiRequest(`/api/user-center/notifications/${encodeURIComponent(notificationId)}`, {
        method: "DELETE",
      });
      await this.refresh();
    } catch (error) {
      throw translateError(error);
    }
  }

  async rememberSearchTerm(term: string): Promise<string[]> {
    const normalized = term.trim().slice(0, 100);
    if (!normalized) return [...this.searchHistory];
    this.searchHistory = [normalized, ...this.searchHistory.filter((item) => item !== normalized)].slice(0, 12);
    this.snapshot = { ...this.snapshot, searchHistory: [...this.searchHistory] };
    this.emit();
    return [...this.searchHistory];
  }

  async removeSearchTerm(term: string): Promise<string[]> {
    this.searchHistory = this.searchHistory.filter((item) => item !== term);
    this.snapshot = { ...this.snapshot, searchHistory: [...this.searchHistory] };
    this.emit();
    return [...this.searchHistory];
  }

  async clearSearchHistory(): Promise<void> {
    this.searchHistory = [];
    this.snapshot = { ...this.snapshot, searchHistory: [] };
    this.emit();
  }

  async previewLocalArchive(
    localState: Record<string, unknown>,
  ): Promise<CommunityImportPreview> {
    try {
      return await communityApiRequest<CommunityImportPreview>(
        "/api/community/imports/preview",
        { method: "POST", body: JSON.stringify({ local_state: localState }) },
      );
    } catch (error) {
      throw translateError(error);
    }
  }

  async importLocalArchive(
    localState: Record<string, unknown>,
  ): Promise<CommunityImportResult> {
    try {
      const result = await communityApiRequest<CommunityImportResult>(
        "/api/community/imports/commit",
        { method: "POST", body: JSON.stringify({ local_state: localState }) },
      );
      await this.refresh();
      return result;
    } catch (error) {
      throw translateError(error);
    }
  }

  async createSubmissionDraft(input: CreateDraftInput): Promise<SubmissionDraft> {
    try {
      const draft = await communityApiRequest<SubmissionDraft>("/api/community/submissions", {
        method: "POST",
        body: JSON.stringify({ submission_type: input.submissionType, title: input.title ?? "" }),
      });
      await this.refresh();
      return draft;
    } catch (error) {
      throw translateError(error);
    }
  }

  async updateSubmissionDraft(draftId: EntityId, patch: SubmissionDraftPatch): Promise<SubmissionDraft> {
    const current = this.snapshot.drafts.find((item) => item.id === draftId);
    if (!current) throw new CommunityDataError("not_found", "投稿草稿不存在");
    try {
      const draft = await communityApiRequest<SubmissionDraft>(
        `/api/community/submissions/${encodeURIComponent(draftId)}`,
        { method: "PATCH", body: JSON.stringify({ expected_version: current.version, ...patch }) },
      );
      await this.refresh();
      return draft;
    } catch (error) {
      throw translateError(error);
    }
  }

  async transitionSubmissionDraft(
    draftId: EntityId,
    nextStatus: SubmissionStatus,
    reviewerNote = "",
  ): Promise<SubmissionDraft> {
    const current = this.snapshot.drafts.find((item) => item.id === draftId);
    if (!current) throw new CommunityDataError("not_found", "投稿草稿不存在");
    try {
      const draft = await communityApiRequest<SubmissionDraft>(
        `/api/community/submissions/${encodeURIComponent(draftId)}/transition`,
        {
          method: "POST",
          body: JSON.stringify({
            expected_version: current.version,
            status: nextStatus,
            reviewer_note: reviewerNote,
          }),
        },
      );
      await this.refresh();
      return draft;
    } catch (error) {
      throw translateError(error);
    }
  }

  async deleteSubmissionDraft(draftId: EntityId): Promise<void> {
    const current = this.snapshot.drafts.find((item) => item.id === draftId);
    if (!current) throw new CommunityDataError("not_found", "投稿草稿不存在");
    if (current.status !== "archived") await this.transitionSubmissionDraft(draftId, "archived");
  }

  async resetLocalDemoState(): Promise<void> {
    throw new CommunityDataError("validation", "API 模式不允许重置服务端账户数据");
  }
}

export function createApiCommunityAdapter(): ApiCommunityAdapter {
  return new ApiCommunityAdapter();
}
