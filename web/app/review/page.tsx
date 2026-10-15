"use client";

import { useMemo, useState } from "react";
import Link from "next/link";

import { ProductFrame } from "@/components/community/ProductFrame";
import { StateNotice } from "@/components/community/StateNotice";
import { type SubmissionDraft, type SubmissionStatus, useCommunity } from "@/lib/community";

const statusLabel: Record<SubmissionStatus, string> = {
  draft: "草稿",
  checking: "检查中",
  needs_revision: "需要修改",
  submitted: "待审核",
  reviewing: "审核中",
  approved: "已通过",
  scheduled: "已排期",
  published: "已发布（演示）",
  rejected: "未通过",
  archived: "已归档",
};

const statusClass = (status: SubmissionStatus) => {
  if (["approved", "published"].includes(status)) return "productStatusPill is-good";
  if (["needs_revision", "checking", "submitted", "reviewing", "scheduled"].includes(status)) return "productStatusPill is-warning";
  if (status === "rejected") return "productStatusPill is-danger";
  return "productStatusPill";
};

function nextActions(
  status: SubmissionStatus,
  apiMode: boolean,
  activeRole: string,
): { status: SubmissionStatus; label: string }[] {
  if (status === "submitted") return [{ status: "reviewing", label: "开始审核" }];
  if (status === "reviewing") return [
    { status: "approved", label: "审核通过" },
    { status: "needs_revision", label: "退回修改" },
    { status: "rejected", label: "不予通过" },
  ];
  if (status === "approved" && (!apiMode || activeRole === "admin")) return [
    { status: "published", label: apiMode ? "发布到内部内容目录" : "发布演示内容" },
    ...(!apiMode ? [{ status: "scheduled" as const, label: "加入演示排期" }] : []),
  ];
  if (!apiMode && status === "scheduled") return [{ status: "published", label: "执行演示发布" }];
  return [];
}

export default function ReviewPage() {
  const { snapshot, actions } = useCommunity();
  const [filter, setFilter] = useState<"active" | "all">("active");
  const [selectedId, setSelectedId] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState("");
  const apiMode = snapshot.runtime.mode === "api";
  const activeRole = snapshot.viewer.roleLabel;
  const canReview = !apiMode || ["reviewer", "admin"].includes(activeRole);

  const drafts = useMemo(() => snapshot.drafts.filter((draft) => filter === "all" || ["submitted", "reviewing", "approved", "scheduled"].includes(draft.status)), [filter, snapshot.drafts]);
  const selected = snapshot.drafts.find((draft) => draft.id === selectedId) ?? drafts[0];

  async function transition(draft: SubmissionDraft, status: SubmissionStatus) {
    setBusy(true);
    setFeedback("");
    try {
      await actions.transitionSubmissionDraft(draft.id, status, note || `审核处理：${statusLabel[status]}。`);
      setNote("");
      setFeedback(`状态已更新为“${statusLabel[status]}”。${apiMode ? "结果与审计记录已写入服务端。" : "该结果仅保存在本地浏览器。"}`);
    } catch (cause) {
      setFeedback(cause instanceof Error ? cause.message : "状态更新失败。 ");
    } finally {
      setBusy(false);
    }
  }

  return (
    <ProductFrame>
      <div className="productDemoStrip" role="note"><b>{apiMode ? "内部审核台" : "独立本地审核台"}</b><span>{apiMode ? "审核身份由服务端授权，所有状态变化写入审计事件；当前仍是内部测试目录。" : "用于验证投稿状态机、审核意见、消息回流和发布展示；不代表真实专家或平台审核。"}</span></div>
      <header className="productPageHead">
        <div><small>MODERATION WORKSPACE</small><h1>审核中心</h1><p>分开核对文件、版权、事实来源、AI 披露、人物授权和发布规格。</p></div>
        <Link className="productButtonSecondary" href="/creator/submissions/new">新建投稿</Link>
      </header>
      <div className="productFilterBar"><button className={filter === "active" ? "active" : ""} type="button" onClick={() => setFilter("active")}>待处理</button><button className={filter === "all" ? "active" : ""} type="button" onClick={() => setFilter("all")}>全部状态</button></div>
      {!snapshot.runtime.hydrated ? (
        <StateNotice kind="loading" title="正在读取审核队列" description={apiMode ? "正在从服务端读取投稿与审核状态。" : "正在从当前浏览器读取投稿与审核状态。"} />
      ) : snapshot.runtime.recoveryNotice ? (
        <StateNotice kind="offline" title="审核队列暂时不可用" description={snapshot.runtime.recoveryNotice} />
      ) : !canReview ? (
        <StateNotice kind="forbidden" title="当前身份不能进入审核工作台" description="请使用经过授权的审核员或管理员身份；创作者不能审核自己的投稿。" actionLabel="前往身份中心" actionHref="/identity" />
      ) : !drafts.length ? (
        <StateNotice kind="empty" title="当前没有待审核投稿" description={apiMode ? "服务端队列中没有当前身份可处理的投稿。" : "先完成一份投稿并提交，本地审核任务会出现在这里。"} actionLabel="进入投稿向导" actionHref="/creator/submissions/new" />
      ) : (
        <div className="productReviewLayout">
          <ul className="productDraftList" aria-label="投稿列表">
            {drafts.map((draft) => (
              <li key={draft.id}>
                <button className="productButtonQuiet" type="button" onClick={() => setSelectedId(draft.id)} aria-pressed={selected?.id === draft.id}>
                  <span className={statusClass(draft.status)}>{statusLabel[draft.status]}</span>
                  <b>{draft.title || "未命名投稿"}</b>
                </button>
                <p>{draft.summary || "暂无简介"}</p>
                <small>{draft.sourceIds.length} 条来源 · {draft.assets.length} 项素材 · AI {draft.aiDisclosure}</small>
              </li>
            ))}
          </ul>
          {selected ? (
            <aside className="productSidePanel">
              <span className={statusClass(selected.status)}>{statusLabel[selected.status]}</span>
              <h2>{selected.title}</h2>
              <p>{selected.summary}</p>
              <ul>
                <li>{selected.projectIds.length ? "✓" : "!"} 关联项目</li>
                <li>{selected.sourceIds.length ? "✓" : "!"} 事实来源</li>
                <li>{selected.assets.length ? "✓" : "!"} 素材元数据</li>
                <li>✓ AI 披露：{selected.aiDisclosure}</li>
              </ul>
              {selected.reviewerNote ? <div className="productInlineAlert">上一条审核意见：{selected.reviewerNote}</div> : null}
              {nextActions(selected.status, apiMode, activeRole).length ? (
                <div className="productForm">
                  <label>审核意见<textarea value={note} onChange={(event) => setNote(event.target.value)} placeholder="写明事实、来源、授权或规格问题" /></label>
                  {nextActions(selected.status, apiMode, activeRole).map((action) => <button className={action.status === "rejected" ? "productButtonSecondary" : "productButton"} type="button" disabled={busy} onClick={() => void transition(selected, action.status)} key={action.status}>{action.label}</button>)}
                </div>
              ) : <p>当前状态需要创作者处理，或已完成本地演示流程。</p>}
            </aside>
          ) : null}
        </div>
      )}
      {feedback ? <div className="productToast" role="status">{feedback}</div> : null}
    </ProductFrame>
  );
}
