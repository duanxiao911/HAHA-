export type EntityId = string;
export type ISODateString = string;

export const LOCAL_DEMO_WORKSPACE_ID = "demo-workspace";
export const LOCAL_DEMO_VIEWER_ID = "demo-user";

export type DemoProvenance = "local_demo" | "demo_seed" | "server";

export type ContentType =
  | "short_video"
  | "long_video"
  | "image_story"
  | "knowledge_card"
  | "heritage_project"
  | "inheritor_story"
  | "process_tutorial"
  | "event"
  | "topic"
  | "series"
  | "live_replay";

export type VerificationStatus =
  | "verified"
  | "inheritor_confirmed"
  | "expert_reviewed"
  | "pending"
  | "disputed";

export type ReactionKind =
  | "bookmark"
  | "want_to_learn"
  | "respect"
  | "watch_later";

export type SubmissionType = "video" | "article" | "project" | "event";

export type SubmissionStatus =
  | "draft"
  | "checking"
  | "needs_revision"
  | "submitted"
  | "reviewing"
  | "approved"
  | "scheduled"
  | "published"
  | "rejected"
  | "archived";

export type NotificationKind =
  | "comment"
  | "reply"
  | "follow"
  | "reaction"
  | "review"
  | "correction"
  | "event"
  | "system";

export interface DemoEntity {
  id: EntityId;
  workspaceId: string;
  provenance: DemoProvenance;
  createdAt: ISODateString;
  updatedAt: ISODateString;
}

export interface MediaAsset {
  id: EntityId;
  kind: "image" | "video" | "audio";
  url?: string;
  alt: string;
  mimeType?: string;
  width?: number;
  height?: number;
  durationSeconds?: number;
  placeholder?: {
    mark: string;
    tone: "red" | "green" | "blue" | "gold";
  };
}

export interface CommunityRegion extends DemoEntity {
  slug: string;
  name: string;
  province: string;
  summary: string;
  featuredCrafts: string[];
  projectCount: number;
}

export interface CommunityPerson extends DemoEntity {
  slug: string;
  displayName: string;
  role: "creator" | "inheritor" | "institution" | "expert";
  avatar?: MediaAsset;
  bio: string;
  regionId: EntityId;
  projectIds: EntityId[];
  verified: boolean;
  demoLabel: string;
}

export interface HeritageProject extends DemoEntity {
  slug: string;
  name: string;
  level: "national" | "provincial" | "municipal" | "community";
  category: string;
  regionIds: EntityId[];
  inheritorIds: EntityId[];
  summary: string;
  materials: string[];
  techniques: string[];
  sourceIds: EntityId[];
  verificationStatus: VerificationStatus;
}

export interface SourceCitation extends DemoEntity {
  title: string;
  publisher: string;
  url?: string;
  sourceLevel: "official" | "academic" | "institution" | "interview" | "community";
  accessedAt?: ISODateString;
  note?: string;
}

export interface FactClaim extends DemoEntity {
  contentId: EntityId;
  text: string;
  status: VerificationStatus;
  sourceIds: EntityId[];
  checkedAt?: ISODateString;
  note?: string;
}

export interface ContentMetrics {
  viewCount: number;
  interactionCount: number;
  commentCount: number;
  bookmarkCount: number;
}

export type ReactionCounts = Record<ReactionKind, number>;

export interface ViewerContentState {
  reactions: ReactionKind[];
  followedCreator: boolean;
  viewed: boolean;
  watchProgressSeconds: number;
}

export interface TrustSummary {
  status: VerificationStatus;
  label: string;
  sourceCount: number;
  checkedAt?: ISODateString;
  aiAssisted: boolean;
}

export interface ContentSummary extends DemoEntity {
  slug: string;
  contentType: ContentType;
  title: string;
  summary: string;
  body: string;
  cover: MediaAsset;
  creatorId: EntityId;
  creator: CommunityPerson;
  categoryId: EntityId;
  categoryLabel: string;
  regionId: EntityId;
  regionLabel: string;
  projectIds: EntityId[];
  personIds: EntityId[];
  tags: string[];
  durationSeconds?: number;
  metrics: ContentMetrics;
  reactionCounts: ReactionCounts;
  trust: TrustSummary;
  viewer: ViewerContentState;
  publishedAt: ISODateString;
}

export interface ContentDetail extends ContentSummary {
  body: string;
  media: MediaAsset[];
  claims: FactClaim[];
  sources: SourceCitation[];
  relatedContentIds: EntityId[];
}

export interface WatchHistoryEntry {
  contentId: EntityId;
  viewedAt: ISODateString;
  progressSeconds: number;
  completed: boolean;
}

export interface CommunityComment extends DemoEntity {
  contentId: EntityId;
  authorId: EntityId;
  authorName: string;
  body: string;
  parentId?: EntityId;
  status: "visible" | "deleted";
}

export interface TimedKnowledgeAnnotation extends DemoEntity {
  contentId: EntityId;
  authorId: EntityId;
  authorName: string;
  timestampSeconds: number;
  body: string;
  kind: "craft" | "term" | "regional_difference" | "source" | "correction";
  verificationStatus: VerificationStatus;
  sourceIds: EntityId[];
}

export interface CommunityNotification extends DemoEntity {
  recipientId: EntityId;
  kind: NotificationKind;
  title: string;
  body: string;
  targetHref?: string;
  readAt?: ISODateString;
}

export interface SubmissionAssetDraft {
  id: EntityId;
  name: string;
  kind: "image" | "video" | "document";
  mimeType: string;
  sizeBytes: number;
  localOnly: boolean;
  status?: "ready";
  scanStatus?: "signature_verified";
  sha256?: string;
  url?: string;
}

export interface SubmissionDraft extends DemoEntity {
  ownerId: EntityId;
  submissionType: SubmissionType;
  status: SubmissionStatus;
  version: number;
  title: string;
  summary: string;
  body: string;
  categoryId?: EntityId;
  regionId?: EntityId;
  projectIds: EntityId[];
  personIds: EntityId[];
  sourceIds: EntityId[];
  tags: string[];
  assets: SubmissionAssetDraft[];
  assetOrder: EntityId[];
  aiDisclosure: "none" | "assisted" | "generated";
  reviewerNote?: string;
  submittedAt?: ISODateString;
  publishedAt?: ISODateString;
}

export type SubmissionDraftPatch = Partial<
  Pick<
    SubmissionDraft,
    | "title"
    | "summary"
    | "body"
    | "categoryId"
    | "regionId"
    | "projectIds"
    | "personIds"
    | "sourceIds"
    | "tags"
    | "assets"
    | "assetOrder"
    | "aiDisclosure"
    | "reviewerNote"
  >
>;

export interface LocalDemoViewer {
  id: string;
  workspaceId: string;
  displayName: string;
  authState: "local_demo" | "authenticated";
  roleLabel: string;
}

export interface LocalDemoRuntime {
  mode: "local_demo" | "api";
  hydrated: boolean;
  persistence: "memory" | "local_storage" | "postgresql";
  recoveryNotice: string | null;
  schemaVersion: number;
  dataNotice: string;
}

export interface CommunitySnapshot {
  runtime: LocalDemoRuntime;
  viewer: LocalDemoViewer;
  contents: ContentDetail[];
  projects: HeritageProject[];
  people: CommunityPerson[];
  regions: CommunityRegion[];
  sources: SourceCitation[];
  facts: FactClaim[];
  followingPersonIds: EntityId[];
  history: WatchHistoryEntry[];
  comments: CommunityComment[];
  annotations: TimedKnowledgeAnnotation[];
  notifications: CommunityNotification[];
  searchHistory: string[];
  drafts: SubmissionDraft[];
}

export type SearchEntityKind = "content" | "project" | "person" | "region";

export interface CommunitySearchHit {
  kind: SearchEntityKind;
  id: EntityId;
  title: string;
  summary: string;
  href: string;
  score: number;
  verificationStatus?: VerificationStatus;
}

export type CommunityDataErrorCode =
  | "aborted"
  | "not_found"
  | "validation"
  | "conflict"
  | "invalid_transition"
  | "storage_unavailable";

export class CommunityDataError extends Error {
  readonly code: CommunityDataErrorCode;
  readonly retryable: boolean;

  constructor(code: CommunityDataErrorCode, message: string, retryable = false) {
    super(message);
    this.name = "CommunityDataError";
    this.code = code;
    this.retryable = retryable;
  }
}
