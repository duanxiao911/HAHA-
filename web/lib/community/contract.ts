import type {
  CommunityComment,
  CommunityNotification,
  CommunitySearchHit,
  CommunitySnapshot,
  ContentDetail,
  ContentSummary,
  EntityId,
  ReactionKind,
  SubmissionDraft,
  SubmissionDraftPatch,
  SubmissionStatus,
  SubmissionType,
  TimedKnowledgeAnnotation,
  WatchHistoryEntry,
} from "./types";

export interface PageResult<T> {
  items: T[];
  nextCursor: string | null;
  total: number;
}

export interface FeedQuery {
  mode: "recommended" | "following" | "nearby" | "learning";
  channelId?: string;
  regionId?: EntityId;
  cursor?: string;
  limit?: number;
}

export interface SearchQuery {
  query: string;
  scope?: "all" | "content" | "project" | "person" | "region";
  sort?: "relevance" | "latest" | "popular" | "verified";
  cursor?: string;
  limit?: number;
}

export interface CreateCommentInput {
  contentId: EntityId;
  body: string;
  parentId?: EntityId;
}

export interface CreateTimedAnnotationInput {
  contentId: EntityId;
  timestampSeconds: number;
  body: string;
  kind: TimedKnowledgeAnnotation["kind"];
  sourceIds?: EntityId[];
}

export interface CreateDraftInput {
  submissionType: SubmissionType;
  title?: string;
}

export interface CommunityImportPreview {
  fingerprint: string;
  alreadyImported: boolean;
  importable: {
    reactionTargets: number;
    follows: number;
    history: number;
    comments: number;
    annotations: number;
    drafts: number;
  };
  ignored: string[];
}

export interface CommunityImportResult {
  fingerprint: string;
  alreadyImported: boolean;
  imported: {
    reactions: number;
    follows: number;
    history: number;
    comments: number;
    annotations: number;
    drafts: number;
  };
  skipped: number;
  trustBoundary: string;
}

export type CommunityChangeListener = () => void;

/**
 * Stable UI-facing port. Components depend on this contract rather than seed,
 * localStorage, HTTP DTOs, or the existing creator API client.
 */
export interface CommunityAdapter {
  hydrate(): void;
  dispose(): void;
  subscribe(listener: CommunityChangeListener): () => void;
  getSnapshot(): CommunitySnapshot;

  getFeed(query: FeedQuery, signal?: AbortSignal): Promise<PageResult<ContentSummary>>;
  getContent(contentId: EntityId, signal?: AbortSignal): Promise<ContentDetail>;
  search(query: SearchQuery, signal?: AbortSignal): Promise<PageResult<CommunitySearchHit>>;

  setReaction(
    contentId: EntityId,
    reaction: ReactionKind,
    active: boolean,
  ): Promise<ContentSummary>;
  setPersonFollow(personId: EntityId, active: boolean): Promise<boolean>;

  recordWatchHistory(
    contentId: EntityId,
    progressSeconds?: number,
  ): Promise<WatchHistoryEntry>;
  removeWatchHistory(contentId: EntityId): Promise<void>;
  clearWatchHistory(): Promise<void>;

  createComment(input: CreateCommentInput): Promise<CommunityComment>;
  deleteOwnComment(commentId: EntityId): Promise<void>;
  createTimedAnnotation(
    input: CreateTimedAnnotationInput,
  ): Promise<TimedKnowledgeAnnotation>;
  deleteOwnTimedAnnotation(annotationId: EntityId): Promise<void>;

  markNotificationRead(notificationId: EntityId): Promise<void>;
  markAllNotificationsRead(): Promise<void>;
  deleteNotification(notificationId: EntityId): Promise<void>;

  rememberSearchTerm(term: string): Promise<string[]>;
  removeSearchTerm(term: string): Promise<string[]>;
  clearSearchHistory(): Promise<void>;

  previewLocalArchive(
    localState: Record<string, unknown>,
  ): Promise<CommunityImportPreview>;
  importLocalArchive(
    localState: Record<string, unknown>,
  ): Promise<CommunityImportResult>;

  createSubmissionDraft(input: CreateDraftInput): Promise<SubmissionDraft>;
  updateSubmissionDraft(
    draftId: EntityId,
    patch: SubmissionDraftPatch,
  ): Promise<SubmissionDraft>;
  transitionSubmissionDraft(
    draftId: EntityId,
    nextStatus: SubmissionStatus,
    reviewerNote?: string,
  ): Promise<SubmissionDraft>;
  deleteSubmissionDraft(draftId: EntityId): Promise<void>;

  /** Local demo only. Never represents an account or server-side data deletion. */
  resetLocalDemoState(): Promise<void>;
}

export interface CommunityActions {
  getFeed: CommunityAdapter["getFeed"];
  getContent: CommunityAdapter["getContent"];
  search: CommunityAdapter["search"];
  setReaction: CommunityAdapter["setReaction"];
  setPersonFollow: CommunityAdapter["setPersonFollow"];
  recordWatchHistory: CommunityAdapter["recordWatchHistory"];
  removeWatchHistory: CommunityAdapter["removeWatchHistory"];
  clearWatchHistory: CommunityAdapter["clearWatchHistory"];
  createComment: CommunityAdapter["createComment"];
  deleteOwnComment: CommunityAdapter["deleteOwnComment"];
  createTimedAnnotation: CommunityAdapter["createTimedAnnotation"];
  deleteOwnTimedAnnotation: CommunityAdapter["deleteOwnTimedAnnotation"];
  markNotificationRead: CommunityAdapter["markNotificationRead"];
  markAllNotificationsRead: CommunityAdapter["markAllNotificationsRead"];
  deleteNotification: CommunityAdapter["deleteNotification"];
  rememberSearchTerm: CommunityAdapter["rememberSearchTerm"];
  removeSearchTerm: CommunityAdapter["removeSearchTerm"];
  clearSearchHistory: CommunityAdapter["clearSearchHistory"];
  previewLocalArchive: CommunityAdapter["previewLocalArchive"];
  importLocalArchive: CommunityAdapter["importLocalArchive"];
  createSubmissionDraft: CommunityAdapter["createSubmissionDraft"];
  updateSubmissionDraft: CommunityAdapter["updateSubmissionDraft"];
  transitionSubmissionDraft: CommunityAdapter["transitionSubmissionDraft"];
  deleteSubmissionDraft: CommunityAdapter["deleteSubmissionDraft"];
  resetLocalDemoState: CommunityAdapter["resetLocalDemoState"];
}

export interface CommunityContextValue {
  snapshot: CommunitySnapshot;
  actions: CommunityActions;
  unreadNotificationCount: number;
}

export type { CommunityNotification };
