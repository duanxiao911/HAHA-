"use client";
/* eslint-disable @next/next/no-img-element -- private authenticated media bypasses the public optimizer */

import { FormEvent, useState } from "react";
import {
  createImageRun, CreatorModelCapabilities, getRun, RunResult, streamRunEvents,
} from "@/lib/api";

export function CreatorImageStudio({
  sourceRun, capabilities,
}: {
  sourceRun: RunResult | null;
  capabilities: CreatorModelCapabilities | null;
}) {
  const [prompt, setPrompt] = useState("");
  const [negativePrompt, setNegativePrompt] = useState("文字、标志、错误手指、虚构人物信息");
  const [size, setSize] = useState<"1K" | "2K" | "4K">("2K");
  const [count, setCount] = useState(1);
  const [imageRun, setImageRun] = useState<RunResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const reviewed = sourceRun?.latest_revision?.review_status === "reviewed";
  const available = capabilities?.image.available === true;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!sourceRun || !reviewed || !available) return;
    setBusy(true);
    setError("");
    try {
      const created = await createImageRun({
        source_run_id: sourceRun.id, prompt, negative_prompt: negativePrompt,
        size, count, watermark: true, reference_asset_ids: [],
      });
      setImageRun({ id: created.id, status: "PENDING", error_message: "", script: null });
      await streamRunEvents(created.id, (event) => {
        if (event.data.status) setImageRun((current) => ({
          id: created.id, status: event.data.status ?? current?.status ?? "PENDING",
          attempt: event.data.attempt, error_code: event.data.error_code,
          error_message: event.data.error_message ?? "", script: null,
        }));
      });
      setImageRun(await getRun(created.id));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "图片生成失败");
    } finally {
      setBusy(false);
    }
  }

  return <section className="surface creatorImageStudio" aria-labelledby="creator-image-title" data-testid="creator-image-studio" data-capability-status={available ? "available" : "blocked"}>
    <div className="sectionHeading"><span>05</span><div><h2 id="creator-image-title">图片创作与资产画廊</h2><p>从已人工复核的脚本生成图片；文件、哈希、模型请求和版本均由服务端保存。</p></div><div className={`runStatus ${available ? "PASSED" : "FAILED"}`}>{available ? capabilities?.image.model : "真实模型未接通"}</div></div>
    {!available ? <div className="authGate"><b>BLOCKED</b>　{capabilities?.image.reason ?? "图片能力状态加载中。"} 不会使用占位图或模板结果冒充 AI 生图。</div> : null}
    {!reviewed ? <div className="operationsEmpty"><b>先完成脚本人工复核</b><p>图片任务必须绑定一份已复核的 S09 脚本，防止未确认内容直接进入媒体生成。</p></div> : null}
    <form className="revisionEditor" onSubmit={submit}>
      <label>画面描述<textarea required maxLength={4000} value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="描述主体、环境、构图、光线与镜头，不要把未经证实的非遗事实写成画面事实。" /></label>
      <label>排除内容<textarea maxLength={2000} value={negativePrompt} onChange={(event) => setNegativePrompt(event.target.value)} /></label>
      <div className="splitFields"><label>清晰度<select value={size} onChange={(event) => setSize(event.target.value as "1K" | "2K" | "4K")}><option>1K</option><option>2K</option><option>4K</option></select></label><label>数量<select value={count} onChange={(event) => setCount(Number(event.target.value))}>{[1, 2, 3, 4].map((value) => <option key={value}>{value}</option>)}</select></label></div>
      <small>当前固定保留供应商水印。参考图与图片编辑在账号能力真实实测前保持关闭。</small>
      <button className="generateButton" disabled={busy || !available || !reviewed || !prompt.trim()}>{busy ? "正在生成、下载并校验…" : "生成真实图片"}</button>
    </form>
    {error ? <p className="error consoleError">{error}</p> : null}
    {imageRun ? <p className="saveState" aria-live="polite">任务 {imageRun.status}{imageRun.error_message ? ` · ${imageRun.error_message}` : ""}</p> : null}
    {imageRun?.image_assets?.length ? <div className="creatorImageGallery">{imageRun.image_assets.map((asset) => <figure key={asset.id}><img src={asset.url} alt={`生成图片版本 ${asset.version}`} /><figcaption><b>版本 {asset.version} · {asset.width}×{asset.height}</b><small>{asset.mime_type} · SHA-256 {asset.sha256.slice(0, 12)}…</small><small>{asset.evidence.provider} / {asset.evidence.model} · request {asset.evidence.request_id || "UNKNOWN"}</small></figcaption></figure>)}</div> : null}
  </section>;
}
