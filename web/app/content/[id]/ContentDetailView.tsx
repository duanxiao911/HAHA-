"use client";

import {
  type FormEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { ContentTile } from "@/components/community/ContentTile";
import { EntityCard } from "@/components/community/EntityCard";
import { InteractionBar } from "@/components/community/InteractionBar";
import { ProductFrame } from "@/components/community/ProductFrame";
import { StateNotice } from "@/components/community/StateNotice";
import { TrustBadge } from "@/components/community/TrustBadge";
import {
  CommunityDataError,
  type ReactionKind,
  type TimedKnowledgeAnnotation,
  useCommunity,
} from "@/lib/community";

type ContentDetailViewProps = {
  contentId: string;
};

type Feedback = {
  kind: "success" | "error";
  message: string;
};

const annotationLabels: Record<TimedKnowledgeAnnotation["kind"], string> = {
  craft: "工艺说明",
  term: "术语解释",
  regional_difference: "地域差异",
  source: "来源补充",
  correction: "纠错建议",
};

function formatDate(value?: string): string {
  if (!value) return "尚未记录";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return "时间格式无效";
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Shanghai",
  }).format(date);
}

function formatDuration(seconds: number): string {
  const safeSeconds = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(safeSeconds / 60);
  return `${String(minutes).padStart(2, "0")}:${String(safeSeconds % 60).padStart(2, "0")}`;
}

function describeError(error: unknown): string {
  if (error instanceof CommunityDataError) return error.message;
  if (error instanceof Error) return error.message;
  return "操作没有完成，请稍后重试。";
}

export function ContentDetailView({ contentId }: ContentDetailViewProps) {
  const { snapshot, actions } = useCommunity();
  const apiMode = snapshot.runtime.mode === "api";
  const snapshotContent = snapshot.contents.find((item) => item.id === contentId);
  const [loadedContent, setLoadedContent] = useState<typeof snapshotContent>(undefined);
  const [detailState, setDetailState] = useState<"loading" | "success" | "error">("loading");
  const [detailError, setDetailError] = useState("");
  const content = snapshotContent ?? loadedContent;
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [commentBody, setCommentBody] = useState("");
  const [annotationBody, setAnnotationBody] = useState("");
  const [annotationSeconds, setAnnotationSeconds] = useState("0");
  const [annotationKind, setAnnotationKind] = useState<TimedKnowledgeAnnotation["kind"]>("craft");
  const [annotationSourceId, setAnnotationSourceId] = useState("");
  const historyRecordedFor = useRef<string | null>(null);
  const historyContentId = content?.id;

  useEffect(() => {
    if (!snapshot.runtime.hydrated) return;
    const controller = new AbortController();
    void actions.getContent(contentId, controller.signal)
      .then((result) => {
        setLoadedContent(result);
        setDetailState("success");
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setDetailError(describeError(error));
        setDetailState("error");
      });
    return () => controller.abort();
  }, [actions, contentId, snapshot.runtime.hydrated]);

  useEffect(() => {
    if (!snapshot.runtime.hydrated || !historyContentId || historyRecordedFor.current === historyContentId) return;
    historyRecordedFor.current = historyContentId;
    let cancelled = false;
    setBusyAction("history");
    void actions.recordWatchHistory(historyContentId, 0)
      .then(() => {
        if (!cancelled) setFeedback({
          kind: "success",
          message: apiMode ? "观看历史已同步到文化账户。" : "观看历史已保存在此浏览器演示数据中。",
        });
      })
      .catch((error: unknown) => {
        if (!cancelled) setFeedback({ kind: "error", message: `观看历史记录失败：${describeError(error)}` });
      })
      .finally(() => {
        if (!cancelled) setBusyAction((current) => current === "history" ? null : current);
    });
    return () => { cancelled = true; };
  }, [actions, apiMode, historyContentId, snapshot.runtime.hydrated]);

  const comments = useMemo(
    () => snapshot.comments.filter((comment) => comment.contentId === contentId),
    [contentId, snapshot.comments],
  );
  const annotations = useMemo(
    () => snapshot.annotations
      .filter((annotation) => annotation.contentId === contentId)
      .sort((a, b) => a.timestampSeconds - b.timestampSeconds),
    [contentId, snapshot.annotations],
  );

  if (!snapshot.runtime.hydrated || (detailState === "loading" && !content)) {
    return (
      <ProductFrame demoLabel={apiMode ? "服务端内容" : "本地演示"}>
        <StateNotice kind="loading" title="正在加载内容" description="正在读取内容、来源与账户互动状态。" />
      </ProductFrame>
    );
  }

  if (!content || detailState === "error") {
    return (
      <ProductFrame demoLabel={apiMode ? "服务端内容" : "本地演示"}>
        <StateNotice
          kind={snapshot.runtime.recoveryNotice ? "offline" : detailState === "error" ? "error" : "empty"}
          title="没有找到这条内容"
          description={snapshot.runtime.recoveryNotice ?? (detailError || "该内容可能已被移除、尚未发布或链接有误。")}
          actionLabel="返回内容社区"
          actionHref="/"
        />
      </ProductFrame>
    );
  }

  const sourcesById = new Map(snapshot.sources.map((source) => [source.id, source]));
  const projects = snapshot.projects.filter((project) => content.projectIds.includes(project.id));
  const relatedPersonIds = new Set([content.creatorId, ...content.personIds]);
  const people = snapshot.people.filter((person) => relatedPersonIds.has(person.id));
  const region = snapshot.regions.find((item) => item.id === content.regionId);
  const relatedContents = content.relatedContentIds
    .map((id) => snapshot.contents.find((item) => item.id === id))
    .filter((item): item is NonNullable<typeof item> => Boolean(item));
  const reactions = new Set(content.viewer.reactions);
  const disabled = busyAction !== null;
  const playableVideo = content.media.find((asset) => asset.kind === "video" && asset.url);

  async function runWrite(
    key: string,
    operation: () => Promise<unknown>,
    successMessage: string,
  ): Promise<void> {
    if (busyAction) return;
    setBusyAction(key);
    setFeedback(null);
    try {
      await operation();
      setFeedback({ kind: "success", message: successMessage });
    } catch (error) {
      setFeedback({ kind: "error", message: describeError(error) });
    } finally {
      setBusyAction(null);
    }
  }

  function changeReaction(reaction: ReactionKind, active: boolean, label: string): void {
    void runWrite(
      `reaction-${reaction}`,
      () => actions.setReaction(contentId, reaction, active),
      `${active ? "已" : "已取消"}${label}${apiMode ? "并同步到文化账户" : "（本机演示）"}。`,
    );
  }

  function submitComment(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const body = commentBody.trim();
    if (!body) {
      setFeedback({ kind: "error", message: "请先填写评论内容。" });
      return;
    }
    void runWrite(
      "comment-create",
      async () => {
        await actions.createComment({ contentId, body });
        setCommentBody("");
      },
      apiMode ? "评论已保存到服务端账户。" : "评论已保存到本地演示数据。",
    );
  }

  function submitAnnotation(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const body = annotationBody.trim();
    const timestampSeconds = Number(annotationSeconds);
    if (!body) {
      setFeedback({ kind: "error", message: "请先填写知识注释。" });
      return;
    }
    if (!Number.isFinite(timestampSeconds) || timestampSeconds < 0) {
      setFeedback({ kind: "error", message: "时间点必须是大于或等于 0 的秒数。" });
      return;
    }
    void runWrite(
      "annotation-create",
      async () => {
        await actions.createTimedAnnotation({
          contentId,
          timestampSeconds,
          body,
          kind: annotationKind,
          sourceIds: annotationSourceId ? [annotationSourceId] : [],
        });
        setAnnotationBody("");
        setAnnotationSeconds("0");
        setAnnotationSourceId("");
      },
      `知识注释已保存，并标记为“待核验”的${apiMode ? "账户贡献" : "本地贡献"}。`,
    );
  }

  const coverMark = content.cover.placeholder?.mark ?? "影";

  return (
    <ProductFrame demoLabel={apiMode ? "服务端内容闭环" : "本地内容闭环演示"}>
      <div className="productDemoStrip" role="note">
        <b>{apiMode ? "内部测试" : "本地演示"}</b>
        <span>{snapshot.runtime.dataNotice}</span>
      </div>

      {snapshot.runtime.recoveryNotice ? (
        <div className="productInlineAlert" role="status">{snapshot.runtime.recoveryNotice}</div>
      ) : null}

      <div className="productDetailGrid">
        <section className="productPanel" aria-label="媒体演示区">
          {playableVideo ? (
            <div className="productMediaStage productMediaStagePlayable">
              <video
                controls
                preload="metadata"
                aria-label={playableVideo.alt}
                src={playableVideo.url}
                onEnded={() => void actions.recordWatchHistory(content.id, content.durationSeconds ?? 0)}
              >当前浏览器不支持视频播放。</video>
              <small>已审核发布素材 · 服务端真实媒体源</small>
            </div>
          ) : <div className="productMediaStage" role="img" aria-label={content.cover.alt}>
            <span aria-hidden="true">{coverMark}</span>
            <button
              type="button"
              disabled={disabled}
              aria-label="体验媒体播放演示"
              onClick={() => void runWrite(
                "media-preview",
                async () => {
                  const progress = Math.min(10, content.durationSeconds ?? 10);
                  await actions.recordWatchHistory(content.id, progress);
                },
                `${apiMode ? "媒体进度已同步到文化账户" : "媒体进度已保存到本机演示"}；当前内容使用占位媒体。`,
              )}
            >
              ▶
            </button>
            <small>占位媒体 · 尚无已发布视频源 · {formatDuration(content.durationSeconds ?? 0)}</small>
          </div>}
        </section>

        <aside className="productDetailSidebar">
          <span className="productEyebrow">{content.categoryLabel} · {content.regionLabel}</span>
          <h1>{content.title}</h1>
          <p>{content.summary}</p>

          <div className="productCreatorRow">
            <a href={`/inheritors/${encodeURIComponent(content.creatorId)}`}>{content.creator.displayName}</a>
            <button
              className={content.viewer.followedCreator ? "productButtonSecondary" : "productButton"}
              type="button"
              disabled={disabled}
              aria-pressed={content.viewer.followedCreator}
              onClick={() => void runWrite(
                "follow",
                async () => {
                  const active = !content.viewer.followedCreator;
                  await actions.setPersonFollow(content.creatorId, active);
                },
                `${content.viewer.followedCreator ? "已取消关注" : "已关注"}${apiMode ? "并同步到文化账户" : "（本机演示）"}。`,
              )}
            >
              {busyAction === "follow" ? "处理中…" : content.viewer.followedCreator ? "已关注" : "关注"}
            </button>
          </div>

          <InteractionBar
            respected={reactions.has("respect")}
            bookmarked={reactions.has("bookmark")}
            wantsToLearn={reactions.has("want_to_learn")}
            watchLater={reactions.has("watch_later")}
            onRespectChange={(active) => changeReaction("respect", active, "致意")}
            onBookmarkChange={(active) => changeReaction("bookmark", active, "收藏")}
            onWantToLearnChange={(active) => changeReaction("want_to_learn", active, "想学")}
            onWatchLaterChange={(active) => changeReaction("watch_later", active, "稍后看")}
            counts={{
              respect: content.reactionCounts.respect,
              bookmark: content.reactionCounts.bookmark,
              wantToLearn: content.reactionCounts.want_to_learn,
              watchLater: content.reactionCounts.watch_later,
            }}
            disabled={disabled}
          />

          <div className="productMetaRow">
            <span>{content.metrics.viewCount.toLocaleString("zh-CN")} 次播放</span>
            <button
              className="productButtonQuiet"
              type="button"
              disabled={disabled}
              onClick={() => void runWrite(
                "share",
                async () => {
                  if (!globalThis.navigator.clipboard) throw new Error("当前浏览器不支持安全剪贴板，请手动复制地址栏链接。");
                  await globalThis.navigator.clipboard.writeText(globalThis.location.href);
                },
                "内容链接已复制。",
              )}
            >
              {busyAction === "share" ? "复制中…" : "复制分享链接"}
            </button>
          </div>

          <section className="productTrustPanel" aria-labelledby="trust-summary-title">
            <h2 id="trust-summary-title">可信摘要</h2>
            <TrustBadge
              status={content.trust.status}
              label={content.trust.label}
              sourceCount={content.trust.sourceCount}
              aiAssisted={content.trust.aiAssisted}
            />
            <p>AI 披露：{content.trust.aiAssisted ? "包含 AI 辅助内容" : "当前条目未标记为 AI 辅助"}</p>
            <p>最后核验：{formatDate(content.trust.checkedAt)}</p>
            <p>说明：{apiMode ? "该目录仍是内部测试种子，正式发布前仍需人工文化审核。" : "该核验状态属于本地演示，不能视为正式审核结论。"}</p>
          </section>
        </aside>
      </div>

      <div className="productDetailSections">
        <section className="productDetailSection">
          <h2>正文</h2>
          {content.body.split(/\n{2,}/).map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
        </section>

        <section className="productDetailSection" aria-labelledby="claims-title">
          <h2 id="claims-title">关键事实与来源映射</h2>
          <ul className="productClaimList">
            {content.claims.map((claim) => (
              <li key={claim.id}>
                <h3>{claim.text}</h3>
                <small>状态：{claim.status} · 最后核对：{formatDate(claim.checkedAt)}</small>
                <p>
                  来源：{claim.sourceIds.map((sourceId, index) => {
                    const source = sourcesById.get(sourceId);
                    return (
                      <span key={sourceId}>
                        {index > 0 ? "、" : ""}
                        {source ? <a href={`#source-${source.id}`}>{source.title}</a> : `未知来源 ${sourceId}`}
                      </span>
                    );
                  })}
                </p>
                {claim.note ? <p>{claim.note}</p> : null}
              </li>
            ))}
          </ul>
        </section>

        <section className="productDetailSection" aria-labelledby="sources-title">
          <h2 id="sources-title">来源清单</h2>
          <ul className="productSourceList">
            {content.sources.map((source) => (
              <li id={`source-${source.id}`} key={source.id}>
                <h3>{source.title}</h3>
                <small>{source.publisher} · {source.sourceLevel} · 访问时间 {formatDate(source.accessedAt)}</small>
                {source.note ? <p>{source.note}</p> : null}
                {source.url ? (
                  <a href={source.url} target="_blank" rel="noreferrer">打开外部来源 ↗</a>
                ) : (
                  <small>当前来源记录没有可打开的外部链接。</small>
                )}
              </li>
            ))}
          </ul>
        </section>

        <section className="productDetailSection" aria-labelledby="entities-title">
          <h2 id="entities-title">关联项目、人物与地区</h2>
          <div className="productEntityGrid">
            {projects.map((project) => (
              <EntityCard
                kind="project"
                id={project.id}
                title={project.name}
                summary={project.summary}
                meta={`${project.category} · ${project.materials.join(" / ")}`}
                verificationStatus={project.verificationStatus}
                href={`/heritage-projects/${encodeURIComponent(project.id)}`}
                key={project.id}
              />
            ))}
            {people.map((person) => (
              <EntityCard
                kind="profile"
                id={person.id}
                title={person.displayName}
                summary={person.bio}
                meta={person.demoLabel}
                verificationStatus={person.verified ? "verified" : "pending"}
                href={`/inheritors/${encodeURIComponent(person.id)}`}
                key={person.id}
              />
            ))}
            {region ? (
              <EntityCard
                kind="region"
                id={region.id}
                title={region.name}
                summary={region.summary}
                meta={region.featuredCrafts.join(" · ")}
                href={`/map?region=${encodeURIComponent(region.id)}`}
              />
            ) : null}
          </div>
        </section>

        <section className="productDetailSection" aria-labelledby="comments-title">
          <h2 id="comments-title">评论 · {apiMode ? "账户互动" : "本地演示"}</h2>
          <form className="productCommentForm" onSubmit={submitComment}>
            <label>
              添加评论
              <textarea
                value={commentBody}
                onChange={(event) => setCommentBody(event.target.value)}
                maxLength={1000}
                disabled={disabled}
                placeholder="分享你的观察；请勿把未经核实的信息写成确定事实。"
              />
            </label>
            <div className="productFormActions">
              <small>{apiMode ? "评论将保存到服务端账户。" : "评论仅保存在当前浏览器。"}</small>
              <button className="productButton" type="submit" disabled={disabled || !commentBody.trim()}>
                {busyAction === "comment-create" ? "保存中…" : "提交评论"}
              </button>
            </div>
          </form>
          <ul className="productCommentList">
            {comments.length ? comments.map((comment) => (
              <li key={comment.id}>
                <h3>{comment.authorName}</h3>
                <p>{comment.body}</p>
                <small>{formatDate(comment.createdAt)}</small>
                {comment.authorId === snapshot.viewer.id && comment.status === "visible" ? (
                  <button
                    className="productButtonQuiet"
                    type="button"
                    disabled={disabled}
                    onClick={() => void runWrite(
                      `comment-delete-${comment.id}`,
                      () => actions.deleteOwnComment(comment.id),
                      apiMode ? "评论已从服务端账户中删除。" : "评论已从本地演示中删除。",
                    )}
                  >
                    {busyAction === `comment-delete-${comment.id}` ? "删除中…" : "删除自己的评论"}
                  </button>
                ) : null}
              </li>
            )) : <li><p>还没有评论，你可以提交第一条。</p></li>}
          </ul>
        </section>

        <section className="productDetailSection" aria-labelledby="annotations-title">
          <h2 id="annotations-title">时间点知识注释</h2>
          <p>补充工艺、术语、地域差异、来源或纠错建议；新注释统一标记为“待核验”。</p>
          <form className="productForm" onSubmit={submitAnnotation}>
            <div className="productFormGrid">
              <label>
                类型
                <select value={annotationKind} disabled={disabled} onChange={(event) => setAnnotationKind(event.target.value as TimedKnowledgeAnnotation["kind"])}>
                  {Object.entries(annotationLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
                </select>
              </label>
              <label>
                时间点（秒）
                <input
                  type="number"
                  min="0"
                  max={content.durationSeconds}
                  step="1"
                  value={annotationSeconds}
                  disabled={disabled}
                  onChange={(event) => setAnnotationSeconds(event.target.value)}
                />
              </label>
              <label>
                可选来源
                <select value={annotationSourceId} disabled={disabled} onChange={(event) => setAnnotationSourceId(event.target.value)}>
                  <option value="">不关联来源</option>
                  {content.sources.map((source) => <option value={source.id} key={source.id}>{source.title}</option>)}
                </select>
              </label>
            </div>
            <label>
              注释内容
              <textarea
                value={annotationBody}
                onChange={(event) => setAnnotationBody(event.target.value)}
                maxLength={1000}
                disabled={disabled}
                placeholder="说明你观察到的工艺细节，或提出需要核对的问题。"
              />
            </label>
            <div className="productFormActions">
              <small>用户贡献不会自动成为已核验事实。</small>
              <button className="productButton" type="submit" disabled={disabled || !annotationBody.trim()}>
                {busyAction === "annotation-create" ? "保存中…" : "提交知识注释"}
              </button>
            </div>
          </form>
          <ul className="productCommentList">
            {annotations.length ? annotations.map((annotation) => (
              <li key={annotation.id}>
                <h3>{formatDuration(annotation.timestampSeconds)} · {annotationLabels[annotation.kind]}</h3>
                <p>{annotation.body}</p>
                <small>{annotation.authorName} · {annotation.verificationStatus} · {formatDate(annotation.createdAt)}</small>
                {annotation.sourceIds.length ? (
                  <p>来源：{annotation.sourceIds.map((id) => sourcesById.get(id)?.title ?? id).join("、")}</p>
                ) : null}
                {annotation.authorId === snapshot.viewer.id ? (
                  <button
                    className="productButtonQuiet"
                    type="button"
                    disabled={disabled}
                    onClick={() => void runWrite(
                      `annotation-delete-${annotation.id}`,
                      () => actions.deleteOwnTimedAnnotation(annotation.id),
                      apiMode ? "知识注释已从服务端账户中删除。" : "知识注释已从本地演示中删除。",
                    )}
                  >
                    {busyAction === `annotation-delete-${annotation.id}` ? "删除中…" : "删除自己的注释"}
                  </button>
                ) : null}
              </li>
            )) : <li><p>还没有时间点知识注释。</p></li>}
          </ul>
        </section>

        <section className="productDetailSection" aria-labelledby="related-title">
          <h2 id="related-title">相关内容</h2>
          {relatedContents.length ? (
            <div className="productContentGrid">
              {relatedContents.map((item) => <ContentTile content={item} compact key={item.id} />)}
            </div>
          ) : (
            <StateNotice kind="empty" compact title="暂无相关内容" description="当前目录尚未建立更多关联。" />
          )}
        </section>
      </div>

      {feedback ? (
        <div className="productToast" role={feedback.kind === "error" ? "alert" : "status"} aria-live={feedback.kind === "error" ? "assertive" : "polite"}>
          {feedback.kind === "error" ? "操作失败：" : "操作成功："}{feedback.message}
        </div>
      ) : null}
    </ProductFrame>
  );
}

export default ContentDetailView;
