"use client";

import { ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { ConfirmDialog } from "@/components/community/ConfirmDialog";
import { ProductFrame } from "@/components/community/ProductFrame";
import { StateNotice } from "@/components/community/StateNotice";
import {
  type SubmissionAssetDraft,
  type SubmissionDraft,
  type SubmissionType,
  useCommunity,
} from "@/lib/community";

const steps = ["内容类型", "素材", "基础信息", "关联与来源", "披露与检查", "预览提交"];
const submissionTypes: { value: SubmissionType; title: string; detail: string }[] = [
  { value: "video", title: "视频投稿", detail: "短视频、长视频或过程记录" },
  { value: "article", title: "图文投稿", detail: "图文故事、知识卡或轮播" },
  { value: "project", title: "项目资料", detail: "非遗项目与工艺档案补充" },
  { value: "event", title: "活动投稿", detail: "展览、课堂与线下活动" },
];

const allowedTypes = new Set<SubmissionType>(submissionTypes.map((item) => item.value));
const maxBytes: Record<SubmissionAssetDraft["kind"], number> = {
  video: 25 * 1024 * 1024,
  image: 15 * 1024 * 1024,
  document: 10 * 1024 * 1024,
};

function normalizedType(value: string): SubmissionType {
  if (value === "image" || value === "text") return "article";
  return allowedTypes.has(value as SubmissionType) ? value as SubmissionType : "video";
}

function assetKind(file: File): SubmissionAssetDraft["kind"] {
  if (file.type.startsWith("video/")) return "video";
  if (file.type.startsWith("image/")) return "image";
  return "document";
}

function fileSize(value: number): string {
  if (value >= 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MB`;
  return `${Math.ceil(value / 1024)} KB`;
}

export function SubmissionWizard({
  initialType,
  initialDraftId,
  fromAi,
}: {
  initialType: string;
  initialDraftId: string;
  fromAi: boolean;
}) {
  const router = useRouter();
  const { snapshot, actions } = useCommunity();
  const [step, setStep] = useState(0);
  const [draftId, setDraftId] = useState(initialDraftId);
  const [type, setType] = useState<SubmissionType>(normalizedType(initialType));
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [regionId, setRegionId] = useState("");
  const [projectIds, setProjectIds] = useState<string[]>([]);
  const [personIds, setPersonIds] = useState<string[]>([]);
  const [sourceIds, setSourceIds] = useState<string[]>([]);
  const [tags, setTags] = useState("");
  const [assets, setAssets] = useState<SubmissionAssetDraft[]>([]);
  const [aiDisclosure, setAiDisclosure] = useState<SubmissionDraft["aiDisclosure"]>("none");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [exitDialogOpen, setExitDialogOpen] = useState(false);
  const loadedDraftId = useRef("");
  const loadedAiHandoff = useRef(false);
  const apiMode = snapshot.runtime.mode === "api";
  const canCreate = !apiMode || ["creator", "contributor"].includes(snapshot.viewer.roleLabel);

  const currentDraft = snapshot.drafts.find((item) => item.id === draftId);
  const editable = !currentDraft || ["draft", "needs_revision", "rejected"].includes(currentDraft.status);

  useEffect(() => {
    if (!currentDraft || loadedDraftId.current === currentDraft.id) return;
    loadedDraftId.current = currentDraft.id;
    const task = globalThis.setTimeout(() => {
      setType(currentDraft.submissionType);
      setTitle(currentDraft.title);
      setSummary(currentDraft.summary);
      setCategoryId(currentDraft.categoryId ?? "");
      setRegionId(currentDraft.regionId ?? "");
      setProjectIds(currentDraft.projectIds);
      setPersonIds(currentDraft.personIds);
      setSourceIds(currentDraft.sourceIds);
      setTags(currentDraft.tags.join("，"));
      setAssets(currentDraft.assets);
      setAiDisclosure(currentDraft.aiDisclosure);
    }, 0);
    return () => globalThis.clearTimeout(task);
  }, [currentDraft]);

  useEffect(() => {
    if (!fromAi || loadedAiHandoff.current) return;
    loadedAiHandoff.current = true;
    try {
      const raw = globalThis.localStorage?.getItem("haha.creator.submission-handoff.v1");
      if (!raw) return;
      const handoff = JSON.parse(raw) as { title?: string; summary?: string; tags?: string[] };
      const task = globalThis.setTimeout(() => {
        if (handoff.title) setTitle(handoff.title.slice(0, 200));
        if (handoff.summary) setSummary(handoff.summary.slice(0, 4000));
        if (handoff.tags) setTags(handoff.tags.join("，"));
        setAiDisclosure("assisted");
        setFeedback("已从 AI 创作台带入标题、简介和标签；事实来源仍需人工选择。 ");
      }, 0);
      return () => globalThis.clearTimeout(task);
    } catch {
      const task = globalThis.setTimeout(() => setError("AI 创作交接数据已损坏，未自动带入。 "), 0);
      return () => globalThis.clearTimeout(task);
    }
  }, [fromAi]);

  const checks = useMemo(() => [
    { label: "标题与简介完整", pass: Boolean(title.trim() && summary.trim()) },
    { label: "已关联非遗项目", pass: projectIds.length > 0 },
    { label: "至少一条可信来源", pass: sourceIds.length > 0 },
    { label: "AI 参与程度已披露", pass: Boolean(aiDisclosure) },
    { label: "素材已登记", pass: assets.length > 0 },
  ], [aiDisclosure, assets.length, projectIds.length, sourceIds.length, summary, title]);
  const checksPass = checks.every((item) => item.pass);

  function toggle(list: string[], value: string, next: (values: string[]) => void) {
    next(list.includes(value) ? list.filter((item) => item !== value) : [...list, value]);
  }

  async function selectFiles(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    setError("");
    if (apiMode) {
      setBusy(true);
      try {
        let draft = await persist();
        for (const file of files) {
          const kind = assetKind(file);
          if (kind === "document") throw new Error("服务端投稿当前只支持 MP4、WebM、JPEG 和 PNG 素材。");
          if (file.size > maxBytes[kind]) throw new Error(`${file.name} 超过${kind === "video" ? "25 MB" : "15 MB"}上传限制。`);
          draft = await actions.uploadSubmissionAsset(draft.id, file);
        }
        setAssets(draft.assets);
        setFeedback("素材内容已上传到服务端，并完成 MIME 签名与摘要校验。");
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "素材上传失败。 ");
      } finally {
        setBusy(false);
      }
      return;
    }
    const next: SubmissionAssetDraft[] = [];
    for (const file of files) {
      const kind = assetKind(file);
      if (file.size > maxBytes[kind]) {
        setError(`${file.name} 超过${kind === "video" ? "25 MB" : kind === "image" ? "15 MB" : "10 MB"}的素材登记限制。`);
        continue;
      }
      next.push({ id: crypto.randomUUID(), name: file.name, kind, mimeType: file.type || "application/octet-stream", sizeBytes: file.size, localOnly: true });
    }
    setAssets((current) => [...current, ...next].slice(0, 12));
  }

  async function removeAsset(asset: SubmissionAssetDraft) {
    if (!apiMode || asset.localOnly) {
      setAssets((items) => items.filter((item) => item.id !== asset.id));
      return;
    }
    if (!draftId) return;
    setBusy(true);
    setError("");
    try {
      const draft = await actions.deleteSubmissionAsset(draftId, asset.id);
      setAssets(draft.assets);
      setFeedback("服务端素材已移除。");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "素材移除失败。 ");
    } finally {
      setBusy(false);
    }
  }

  async function persist(): Promise<SubmissionDraft> {
    let id = draftId;
    let draft = currentDraft;
    if (!id || !draft) {
      draft = await actions.createSubmissionDraft({ submissionType: type, title });
      id = draft.id;
      setDraftId(id);
      loadedDraftId.current = id;
      router.replace(`/creator/submissions/new?draft=${encodeURIComponent(id)}`, { scroll: false });
    }
    return actions.updateSubmissionDraft(id, {
      title,
      summary,
      categoryId: categoryId || undefined,
      regionId: regionId || undefined,
      projectIds,
      personIds,
      sourceIds,
      tags: tags.split(/[，,]/).map((item) => item.trim()).filter(Boolean).slice(0, 12),
      assets,
      aiDisclosure,
    });
  }

  async function saveAndMove(nextStep: number) {
    setBusy(true);
    setError("");
    try {
      await persist();
      setStep(Math.max(0, Math.min(steps.length - 1, nextStep)));
      setFeedback(apiMode ? "草稿和新版本已保存到服务端。" : "草稿已保存到当前浏览器。");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "草稿保存失败。 ");
    } finally {
      setBusy(false);
    }
  }

  async function submitForReview() {
    if (!checksPass) {
      setError("请先完成全部投稿前检查。 ");
      return;
    }
    setBusy(true);
    setError("");
    try {
      let draft = await persist();
      if (draft.status === "rejected") draft = await actions.transitionSubmissionDraft(draft.id, "needs_revision", "创作者已重新编辑。 ");
      if (["draft", "needs_revision"].includes(draft.status)) draft = await actions.transitionSubmissionDraft(draft.id, "checking");
      if (draft.status === "checking") draft = await actions.transitionSubmissionDraft(draft.id, "submitted");
      setFeedback(apiMode ? "已进入服务端内部审核队列。" : "已进入本地演示审核队列；这不代表真实平台已收到投稿。 ");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "提交失败。 ");
    } finally {
      setBusy(false);
    }
  }

  if (!snapshot.runtime.hydrated) {
    return <ProductFrame><StateNotice kind="loading" title="正在读取投稿工作区" description={apiMode ? "正在从服务端恢复草稿和版本。" : "正在从当前浏览器恢复草稿。"} /></ProductFrame>;
  }

  if (snapshot.runtime.recoveryNotice) {
    return <ProductFrame><StateNotice kind="offline" title="投稿工作区暂时不可用" description={snapshot.runtime.recoveryNotice} /></ProductFrame>;
  }

  if (!canCreate) {
    return <ProductFrame><StateNotice kind="forbidden" title="尚未开通投稿权限" description="请先在用户中心开通创作工作台，或通过知识贡献者资格审核。" actionLabel="查看专业工作台" actionHref="/identity?manage=roles" /></ProductFrame>;
  }

  if (initialDraftId && !currentDraft) {
    return <ProductFrame><StateNotice kind="empty" title="没有找到这份投稿草稿" description={apiMode ? "草稿可能已归档，或属于另一个账户。" : "草稿可能已被清除，或属于另一个浏览器。"} actionLabel="新建投稿" actionHref="/creator/submissions/new" /></ProductFrame>;
  }

  if (currentDraft && !editable) {
    return (
      <ProductFrame>
        <div className="productDemoStrip"><b>{apiMode ? "服务端审核状态" : "本地审核状态"}</b><span>这份投稿当前为 {currentDraft.status}，内容已锁定，避免审核中被静默修改。</span></div>
        <section className="productPanel"><div className="productPanelBody"><span className="productStatusPill is-good">{currentDraft.status}</span><h1>{currentDraft.title}</h1><p>{currentDraft.summary}</p><div className="productFormActions"><Link className="productButton" href="/review">进入审核中心</Link><Link className="productButtonSecondary" href={`/profile/${encodeURIComponent(snapshot.viewer.id || "demo-user")}`}>查看投稿管理</Link></div></div></section>
      </ProductFrame>
    );
  }

  return (
    <ProductFrame>
      <div className="productDemoStrip" role="note"><b>{apiMode ? "服务端投稿工作区" : "投稿演示模式"}</b><span>{apiMode ? "文件内容、摘要和投稿版本保存在服务端；仅已发布素材可公开播放。" : "文件仅登记名称、类型和大小，提交与审核状态只保存在当前浏览器。"}</span></div>
      <div className="productPageToolbar"><button className="productButtonQuiet" type="button" onClick={() => setExitDialogOpen(true)}>← 退出投稿</button><span>{currentDraft ? "已保存草稿可从创作中心继续" : "尚未创建草稿"}</span></div>
      <div className="productWizard">
        <ol className="productWizardSteps" aria-label="投稿步骤">
          {steps.map((label, index) => <li className={index === step ? "active" : index < step ? "done" : ""} aria-current={index === step ? "step" : undefined} key={label}><span>{index < step ? "✓" : index + 1}</span><b>{label}</b></li>)}
        </ol>
        <section className="productWizardPanel" aria-live="polite">
          <small className="productEyebrow">STEP {step + 1} / {steps.length}</small>
          {step === 0 ? <><h1>选择内容类型</h1><p>四类投稿共用同一套来源、披露和审核规则。</p><div className="productTypeGrid">{submissionTypes.map((item) => <button type="button" aria-pressed={type === item.value} onClick={() => setType(item.value)} key={item.value}><b>{item.title}</b><span>{item.detail}</span></button>)}</div></> : null}
          {step === 1 ? <><h1>{apiMode ? "上传素材" : "登记素材"}</h1><p>{apiMode ? "支持 MP4、WebM、JPEG、PNG；视频最大 25 MB、图片最大 15 MB。服务端复核 MIME 签名并保存 SHA-256 摘要，病毒扫描与转码属于后续生产门禁。" : "本地演示只保存文件元数据，不上传文件内容。"}</p><label className="productButtonSecondary">{busy ? "处理中…" : "选择本地文件"}<input className="productVisuallyHidden" type="file" multiple disabled={busy} accept="video/mp4,video/webm,image/jpeg,image/png" onChange={(event) => void selectFiles(event)} /></label>{assets.length ? <ul className="productSourceList">{assets.map((asset) => <li key={asset.id}><b>{asset.name}</b><p>{asset.kind} · {asset.mimeType} · {fileSize(asset.sizeBytes)} · {asset.localOnly ? "仅登记元数据" : "服务端已上传并校验"}</p><button className="productButtonQuiet" type="button" disabled={busy} onClick={() => void removeAsset(asset)}>移除</button></li>)}</ul> : <StateNotice compact kind="empty" title={apiMode ? "尚未上传素材" : "尚未登记素材"} description={apiMode ? "选择一个小型图片或视频文件；上传成功后才能提交审核。" : "可选择一个图片或视频文件用于本地元数据登记。"} />}</> : null}
          {step === 2 ? <><h1>填写基础信息</h1><p>标题和简介将同时用于预览与事实检查。</p><div className="productForm"><label>标题<input value={title} maxLength={200} onChange={(event) => setTitle(event.target.value)} placeholder="准确描述内容，不使用夸张数字" /></label><label>内容简介<textarea value={summary} maxLength={4000} onChange={(event) => setSummary(event.target.value)} placeholder="说明人物、地方、材料、过程和内容边界" /></label><div className="productFormGrid"><label>内容分类<select value={categoryId} onChange={(event) => setCategoryId(event.target.value)}><option value="">请选择</option>{Array.from(new Map(snapshot.contents.map((item) => [item.categoryId, item.categoryLabel]))).map(([id, label]) => <option value={id} key={id}>{label}</option>)}</select></label><label>地区<select value={regionId} onChange={(event) => setRegionId(event.target.value)}><option value="">请选择</option>{snapshot.regions.map((region) => <option value={region.id} key={region.id}>{region.name}</option>)}</select></label></div><label>标签<input value={tags} onChange={(event) => setTags(event.target.value)} placeholder="用中文逗号分隔，例如：苗绣，人物故事" /></label></div></> : null}
          {step === 3 ? <><h1>关联项目、人物与来源</h1><p>来源是事实层的一部分，不能在发布时静默丢失。</p><div className="productForm"><fieldset><legend>非遗项目（至少一项）</legend>{snapshot.projects.map((project) => <label key={project.id}><input type="checkbox" checked={projectIds.includes(project.id)} onChange={() => toggle(projectIds, project.id, setProjectIds)} /> {project.name}</label>)}</fieldset><fieldset><legend>相关人物</legend>{snapshot.people.map((person) => <label key={person.id}><input type="checkbox" checked={personIds.includes(person.id)} onChange={() => toggle(personIds, person.id, setPersonIds)} /> {person.displayName}</label>)}</fieldset><fieldset><legend>事实来源（至少一条）</legend>{snapshot.sources.map((source) => <label key={source.id}><input type="checkbox" checked={sourceIds.includes(source.id)} onChange={() => toggle(sourceIds, source.id, setSourceIds)} /> {source.title} · {source.publisher}</label>)}</fieldset></div></> : null}
          {step === 4 ? <><h1>AI 披露与自动检查</h1><p>同一事实层可以被多个平台版本复用，但不能因改写而产生新事实。</p><div className="productTypeGrid">{(["none", "assisted", "generated"] as const).map((value) => <button type="button" aria-pressed={aiDisclosure === value} onClick={() => setAiDisclosure(value)} key={value}><b>{value === "none" ? "未使用 AI" : value === "assisted" ? "AI 辅助" : "AI 主要生成"}</b><span>{value === "none" ? "完全人工整理" : value === "assisted" ? "人工主导，AI 协助表达" : "需重点复核事实与归因"}</span></button>)}</div><ul className="productClaimList">{checks.map((check) => <li key={check.label}><b>{check.pass ? "✓" : "○"} {check.label}</b><small>{check.pass ? " 已完成" : " 仍需补充"}</small></li>)}</ul><div className="productInlineAlert">这是一组前端完整性检查，不等于后端 Verifier、文件安全扫描或人工文化审核。</div></> : null}
          {step === 5 ? <><h1>预览并提交</h1><p>提交后进入{apiMode ? "服务端" : "本地"}状态机，审核期间内容不可编辑。</p><article className="productPanel"><div className="productPanelBody"><span className="productStatusPill">{submissionTypes.find((item) => item.value === type)?.title}</span><h2>{title || "未填写标题"}</h2><p>{summary || "未填写简介"}</p><p>素材 {assets.length} 项 · 项目 {projectIds.length} 项 · 来源 {sourceIds.length} 条 · AI：{aiDisclosure}</p></div></article><ul className="productClaimList">{checks.map((check) => <li key={check.label}><b>{check.pass ? "✓" : "!"} {check.label}</b></li>)}</ul><button className="productButton" type="button" disabled={busy || !checksPass} onClick={() => void submitForReview()}>{busy ? "正在提交…" : apiMode ? "提交内部审核" : "提交本地审核"}</button></> : null}
          {error ? <div className="productInlineAlert" role="alert">{error}</div> : null}
          <div className="productFormActions"><button className="productButtonSecondary" type="button" disabled={busy || step === 0} onClick={() => setStep((value) => Math.max(0, value - 1))}>上一步</button>{step < steps.length - 1 ? <button className="productButton" type="button" disabled={busy} onClick={() => void saveAndMove(step + 1)}>{busy ? "保存中…" : "保存并继续"}</button> : null}</div>
        </section>
      </div>
      <ConfirmDialog open={exitDialogOpen} title="退出投稿编辑？" description="尚未通过“保存并继续”写入的更改不会保留；已经保存的草稿仍可从创作中心继续。" confirmLabel="退出投稿" cancelLabel="继续编辑" onCancel={() => setExitDialogOpen(false)} onConfirm={() => router.push("/creator")} />
      {feedback ? <div className="productToast" role="status">{feedback}</div> : null}
    </ProductFrame>
  );
}

export function SubmissionWizardFromRoute() {
  const params = useSearchParams();
  return (
    <SubmissionWizard
      initialType={params.get("type") ?? params.get("submission") ?? "video"}
      initialDraftId={params.get("draft") ?? ""}
      fromAi={params.get("from") === "ai"}
    />
  );
}
