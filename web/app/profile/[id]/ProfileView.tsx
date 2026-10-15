"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { ContentTile } from "@/components/community/ContentTile";
import { EntityCard } from "@/components/community/EntityCard";
import { ProductFrame } from "@/components/community/ProductFrame";
import { StateNotice } from "@/components/community/StateNotice";
import {
  COMMUNITY_LOCAL_STORAGE_KEY,
  type CommunityImportPreview,
  type CommunityImportResult,
  LOCAL_DEMO_VIEWER_ID,
  useCommunity,
} from "@/lib/community";

type ArchiveTab = "saved" | "learning" | "history" | "following" | "created" | "contributions";

const archiveTabs: { value: ArchiveTab; label: string }[] = [
  { value: "saved", label: "收藏" },
  { value: "learning", label: "想学清单" },
  { value: "history", label: "观看历史" },
  { value: "following", label: "关注的人" },
  { value: "created", label: "投稿管理" },
  { value: "contributions", label: "知识贡献" },
];

const statusLabels: Record<string, string> = {
  draft: "草稿",
  checking: "事实检查中",
  needs_revision: "需要修改",
  submitted: "已提交",
  reviewing: "审核中",
  approved: "已通过",
  scheduled: "已排期",
  published: "已发布（演示）",
  rejected: "未通过",
  archived: "已归档",
};

const dateTimeFormatter = new Intl.DateTimeFormat("zh-CN", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "Asia/Shanghai",
});

function normalizeArchiveTab(value: string): ArchiveTab {
  if (value === "bookmarks") return "saved";
  return archiveTabs.some((item) => item.value === value) ? value as ArchiveTab : "saved";
}

function readLocalArchive(): {
  detected: boolean;
  value: Record<string, unknown> | null;
  error: string;
} {
  if (typeof window === "undefined") return { detected: false, value: null, error: "" };
  try {
    const raw = window.localStorage.getItem(COMMUNITY_LOCAL_STORAGE_KEY);
    if (!raw) return { detected: false, value: null, error: "" };
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new Error("invalid local archive");
    }
    return { detected: true, value: parsed as Record<string, unknown>, error: "" };
  } catch {
    return {
      detected: true,
      value: null,
      error: "检测到本地档案，但数据已损坏；平台没有修改或删除原始副本。",
    };
  }
}

export function ProfileView({ profileId }: { profileId: string }) {
  const searchParams = useSearchParams();
  const { snapshot, actions } = useCommunity();
  const [tab, setTab] = useState<ArchiveTab>(() => normalizeArchiveTab(searchParams.get("tab") ?? "saved"));
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [archiveDetection] = useState(readLocalArchive);
  const [importPreview, setImportPreview] = useState<CommunityImportPreview | null>(null);
  const [importResult, setImportResult] = useState<CommunityImportResult | null>(null);
  const [importError, setImportError] = useState(archiveDetection.error);
  const archiveDetected = archiveDetection.detected;
  const localArchive = archiveDetection.value;
  const apiMode = snapshot.runtime.mode === "api";
  const isViewer = profileId === snapshot.viewer.id
    || (!apiMode && profileId === LOCAL_DEMO_VIEWER_ID);
  const person = snapshot.people.find((item) => item.id === profileId || item.slug === profileId);

  const saved = snapshot.contents.filter((item) => item.viewer.reactions.includes("bookmark"));
  const learning = snapshot.contents.filter((item) => item.viewer.reactions.includes("want_to_learn"));
  const history = snapshot.history
    .map((entry) => ({ entry, content: snapshot.contents.find((item) => item.id === entry.contentId) }))
    .filter((item): item is { entry: typeof snapshot.history[number]; content: typeof snapshot.contents[number] } => Boolean(item.content));
  const following = snapshot.people.filter((item) => snapshot.followingPersonIds.includes(item.id));

  const personContent = useMemo(() => person
    ? snapshot.contents.filter((item) => item.creatorId === person.id || item.personIds.includes(person.id))
    : [], [person, snapshot.contents]);

  async function toggleFollow() {
    if (!person) return;
    setBusy(true);
    try {
      const next = !snapshot.followingPersonIds.includes(person.id);
      await actions.setPersonFollow(person.id, next);
      setFeedback(next ? "已关注这位演示人物。" : "已取消关注。 ");
    } catch (cause) {
      setFeedback(cause instanceof Error ? cause.message : "操作失败。");
    } finally {
      setBusy(false);
    }
  }

  async function resetDemo() {
    if (apiMode) return;
    if (!globalThis.confirm("只清除这个浏览器中的 HAHA 演示互动、历史和草稿，确定继续吗？")) return;
    setBusy(true);
    try {
      await actions.resetLocalDemoState();
      setFeedback("本地演示状态已重置，种子内容没有被删除。");
    } finally {
      setBusy(false);
    }
  }

  async function previewArchive() {
    if (!localArchive) return;
    setBusy(true);
    setImportError("");
    try {
      setImportPreview(await actions.previewLocalArchive(localArchive));
      setImportResult(null);
    } catch (cause) {
      setImportError(cause instanceof Error ? cause.message : "本地档案检查失败。");
    } finally {
      setBusy(false);
    }
  }

  async function importArchive() {
    if (!localArchive || !importPreview || importPreview.alreadyImported) return;
    setBusy(true);
    setImportError("");
    try {
      const result = await actions.importLocalArchive(localArchive);
      setImportResult(result);
      setImportPreview({ ...importPreview, alreadyImported: true });
      setFeedback("本地文化档案已迁移到账户；浏览器原始副本仍保留。");
    } catch (cause) {
      setImportError(cause instanceof Error ? cause.message : "本地档案迁移失败。");
    } finally {
      setBusy(false);
    }
  }

  if (!snapshot.runtime.hydrated) {
    return <ProductFrame><StateNotice kind="loading" title="正在打开文化档案" description="正在读取人物、互动和投稿数据。" /></ProductFrame>;
  }

  if (snapshot.runtime.recoveryNotice) {
    return <ProductFrame><StateNotice kind="offline" title="文化档案暂时不可用" description={snapshot.runtime.recoveryNotice} /></ProductFrame>;
  }

  if (!isViewer && !person) {
    return (
      <ProductFrame>
        <StateNotice kind="empty" title="没有找到这份人物档案" description="该人物可能不在当前目录中。" actionLabel="浏览传承人" actionHref="/inheritors" />
      </ProductFrame>
    );
  }

  if (person) {
    const followed = snapshot.followingPersonIds.includes(person.id);
    const project = snapshot.projects.find((item) => person.projectIds.includes(item.id));
    return (
      <ProductFrame>
        <div className="productDemoStrip"><b>人物演示档案</b><span>{person.demoLabel}</span></div>
        <section className="productProfileHero">
          <div className="productProfileAvatar" aria-hidden="true">{person.avatar?.placeholder?.mark ?? person.displayName.slice(0, 1)}</div>
          <div>
            <small className="productEyebrow">{person.verified ? "已核验演示身份" : "演示身份"}</small>
            <h1>{person.displayName}</h1>
            <p>{person.bio}</p>
          </div>
          <button className={followed ? "productButtonSecondary" : "productButton"} type="button" disabled={busy} onClick={() => void toggleFollow()} aria-pressed={followed}>{followed ? "已关注" : "＋ 关注"}</button>
        </section>
        {project ? (
          <div className="productEntityGrid"><EntityCard kind="project" id={project.id} title={project.name} summary={project.summary} verificationStatus={project.verificationStatus} /></div>
        ) : null}
        <div className="productSectionHead"><div><small>RELATED CONTENT</small><h2>相关内容</h2></div></div>
        {personContent.length ? <div className="productContentGrid">{personContent.map((item) => <ContentTile content={item} key={item.id} />)}</div> : <StateNotice kind="empty" title="暂无关联内容" description="这个演示人物还没有关联内容。" />}
        {feedback ? <div className="productToast" role="status">{feedback}</div> : null}
      </ProductFrame>
    );
  }

  const contributionCount = snapshot.comments.filter((item) => item.authorId === snapshot.viewer.id && item.status === "visible").length
    + snapshot.annotations.filter((item) => item.authorId === snapshot.viewer.id).length;

  return (
    <ProductFrame>
      <div className="productDemoStrip" role="note">
        <b>{apiMode ? "文化账户档案" : "本地体验身份"}</b>
        <span>{apiMode ? "收藏、想学、关注、观看和贡献均来自服务端账户。" : "这不是注册账号。档案和操作只保存在当前浏览器，不能跨设备同步。"}</span>
      </div>
      <section className="productProfileHero">
        <div className="productProfileAvatar" aria-hidden="true">哈</div>
        <div>
          <small className="productEyebrow">MY CULTURE ARCHIVE</small>
          <h1>{snapshot.viewer.displayName}</h1>
          <p>{snapshot.viewer.roleLabel} · 把收藏、想学、关注、观看和知识贡献整理成个人非遗探索档案。</p>
        </div>
        {!apiMode ? <button className="productButtonSecondary" type="button" disabled={busy} onClick={() => void resetDemo()}>重置本地演示</button> : null}
      </section>

      {apiMode && archiveDetected ? (
        <section className="productPanel" aria-labelledby="local-archive-migration-title">
          <div className="productPanelBody">
            <small className="productEyebrow">LOCAL ARCHIVE MIGRATION</small>
            <h2 id="local-archive-migration-title">迁移浏览器文化档案</h2>
            <p>先由服务端检查可迁移数量，再由你明确确认。原始浏览器副本不会自动删除，本地“已核验、已审核、已发布”状态不会提升为账户可信状态。</p>
            {importError ? <div className="productInlineAlert" role="alert">{importError}</div> : null}
            {!importPreview ? (
              <button className="productButtonSecondary" type="button" disabled={busy || !localArchive} onClick={() => void previewArchive()}>
                {busy ? "正在检查…" : "检查本地档案"}
              </button>
            ) : (
              <>
                <div className="productStatGrid" aria-label="本地档案可迁移数量">
                  <div><b>{importPreview.importable.reactionTargets}</b><span>互动目标</span></div>
                  <div><b>{importPreview.importable.follows}</b><span>关注人物</span></div>
                  <div><b>{importPreview.importable.history}</b><span>观看记录</span></div>
                  <div><b>{importPreview.importable.comments + importPreview.importable.annotations + importPreview.importable.drafts}</b><span>贡献与草稿</span></div>
                </div>
                <div className="productInlineAlert">
                  {importPreview.alreadyImported
                    ? "这份本地档案已经迁移过；幂等保护会阻止重复写入。"
                    : `不会迁移：${importPreview.ignored.join("、")}。`}
                </div>
                {!importPreview.alreadyImported ? (
                  <button className="productButton" type="button" disabled={busy} onClick={() => void importArchive()}>
                    {busy ? "正在迁移…" : "确认迁移到当前账户"}
                  </button>
                ) : null}
              </>
            )}
            {importResult ? (
              <p role="status">
                迁移完成：互动 {importResult.imported.reactions}、关注 {importResult.imported.follows}、历史 {importResult.imported.history}、评论 {importResult.imported.comments}、注释 {importResult.imported.annotations}、草稿 {importResult.imported.drafts}；跳过 {importResult.skipped}。{importResult.trustBoundary}。
              </p>
            ) : null}
          </div>
        </section>
      ) : null}

      <div className="productStatGrid" aria-label="文化档案概览">
        <div><b>{saved.length}</b><span>收藏内容</span></div>
        <div><b>{learning.length}</b><span>想学技艺</span></div>
        <div><b>{following.length}</b><span>关注人物</span></div>
        <div><b>{contributionCount}</b><span>知识贡献</span></div>
      </div>

      <nav className="productTabs" aria-label="文化档案分类">
        {archiveTabs.map((item) => (
          <button className={tab === item.value ? "active" : ""} type="button" aria-pressed={tab === item.value} onClick={() => setTab(item.value)} key={item.value}>{item.label}</button>
        ))}
      </nav>

      {tab === "saved" && (saved.length ? <div className="productContentGrid">{saved.map((item) => <ContentTile content={item} key={item.id} />)}</div> : <StateNotice kind="empty" title="还没有收藏" description="打开任意内容详情，点“收藏”后会出现在这里。" actionLabel="发现内容" actionHref="/" />)}
      {tab === "learning" && (learning.length ? <div className="productContentGrid">{learning.map((item) => <ContentTile content={item} key={item.id} />)}</div> : <StateNotice kind="empty" title="想学清单还是空的" description="在内容详情点“想学”，建立自己的技艺学习清单。" actionLabel="搜索技艺" actionHref="/search" />)}
      {tab === "history" && (history.length ? <div className="productSearchResults">{history.map(({ entry, content }) => <div key={content.id}><ContentTile content={content} compact /><p>最近观看：{dateTimeFormatter.format(new Date(entry.viewedAt))} · {entry.progressSeconds} 秒</p></div>)}</div> : <StateNotice kind="empty" title="还没有观看记录" description={apiMode ? "进入内容详情后会记录到账户观看历史。" : "进入内容详情后会在当前浏览器记录观看历史。"} actionLabel="浏览首页" actionHref="/" />)}
      {tab === "following" && (following.length ? <div className="productEntityGrid">{following.map((item) => <EntityCard kind="profile" id={item.id} href={`/inheritors/${item.id}`} title={item.displayName} summary={item.bio} verificationStatus={item.verified ? "verified" : "pending"} key={item.id} />)}</div> : <StateNotice kind="empty" title="还没有关注人物" description="人物档案和内容详情都可以关注。" actionLabel="浏览人物" actionHref="/inheritors" />)}
      {tab === "created" && (snapshot.drafts.length ? <ul className="productDraftList">{snapshot.drafts.map((draft) => <li key={draft.id}><span className="productStatusPill">{statusLabels[draft.status] ?? draft.status}</span><h2>{draft.title || "未命名投稿"}</h2><p>{draft.summary || "还没有填写内容简介。"}</p><Link className="productButtonSecondary" href={`/creator/submissions/new?draft=${encodeURIComponent(draft.id)}`}>继续处理</Link></li>)}</ul> : <StateNotice kind="empty" title="还没有投稿草稿" description="从 AI 创作结果或投稿向导创建第一份草稿。" actionLabel="开始投稿" actionHref="/creator/submissions/new" />)}
      {tab === "contributions" && (contributionCount ? <div className="productPanel"><div className="productPanelBody"><h2>你的知识贡献</h2><p>评论 {snapshot.comments.filter((item) => item.authorId === snapshot.viewer.id && item.status === "visible").length} 条，时间点知识注释 {snapshot.annotations.filter((item) => item.authorId === snapshot.viewer.id).length} 条。{apiMode ? "注释在服务端保持待核验，不能自动成为可信事实。" : "正式系统接入后，贡献会经历身份、来源和审核校验。"}</p></div></div> : <StateNotice kind="empty" title="还没有知识贡献" description="在内容详情中添加评论、来源或时间点知识注释。" actionLabel="去浏览内容" actionHref="/" />)}
      {feedback ? <div className="productToast" role="status">{feedback}</div> : null}
    </ProductFrame>
  );
}
