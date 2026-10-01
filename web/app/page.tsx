"use client";

import { FormEvent, useMemo, useState } from "react";
import { AUTH_REQUIRED, createBrief, createProject, createRun, getRun, hasAccessToken, RunResult, saveAccessToken } from "@/lib/api";

const initialForm = { craft: "中国剪纸", story_seed: "剪刀落下形成纹样", audience: "第一次接触非遗的人", platform: "B站", tone: "纪录片", goal: "文化科普", duration: "90秒", aspect_ratio: "16:9" };
type ScriptPayload = { title?: string; hook?: string; voiceover?: string[]; shots?: string[]; caption?: string; tags?: string[]; judgment?: [string,string][]; fact_checks?: string[] };

function ResultView({ run }: { run: RunResult }) {
  const script = (run.script?.payload ?? {}) as ScriptPayload;
  const evidence = run.script?.evidence ?? {};
  const verification = (evidence.verification ?? {}) as { checked_at?: string };
  const retrieval = (evidence.retrieval ?? {}) as { user_query?: string; creative_chunks_used?: string[]; operation_chunks_used?: string[]; fact_chunks_used?: string[] };
  const evidenceCount = (retrieval.creative_chunks_used?.length ?? 0) + (retrieval.operation_chunks_used?.length ?? 0) + (retrieval.fact_chunks_used?.length ?? 0);
  return <div className="resultBody">
    <section className="resultHero"><span className="sectionTag">创作方案</span><h3>{script.title ?? "未命名脚本"}</h3><p>{script.hook}</p><div className="chips">{(script.judgment ?? []).map(([key,value]) => <span key={key}>{key} · {value}</span>)}</div></section>
    <div className="resultGrid">
      <section className="contentCard"><div className="cardTitle"><span>01</span><h4>旁白脚本</h4></div><ol className="scriptLines">{(script.voiceover ?? []).map((line,index) => <li key={`${index}-${line}`}>{line}</li>)}</ol></section>
      <section className="contentCard"><div className="cardTitle"><span>02</span><h4>镜头清单</h4></div><ol className="shotList">{(script.shots ?? []).map((shot,index) => <li key={`${index}-${shot}`}><b>{String(index+1).padStart(2,"0")}</b><span>{shot}</span></li>)}</ol></section>
    </div>
    <section className="publishCard"><div><span className="sectionTag">发布文案</span><p>{script.caption}</p></div><div className="tags">{(script.tags ?? []).map(tag => <span key={tag}>#{tag.replace(/^#/,"")}</span>)}</div></section>
    <section className="evidenceCard"><div className="evidenceHead"><div><span className="verifiedDot" />独立验证通过</div><span>{verification.checked_at ? new Date(verification.checked_at).toLocaleString("zh-CN") : "本次运行"}</span></div><div className="evidenceStats"><div><b>{evidenceCount}</b><span>知识证据</span></div><div><b>{script.fact_checks?.length ?? 0}</b><span>事实检查</span></div><div><b>{script.shots?.length ?? 0}</b><span>镜头节点</span></div></div>{retrieval.user_query && <p className="query"><b>检索上下文</b>{retrieval.user_query}</p>}</section>
  </div>;
}

export default function CreatorPage() {
  const [form,setForm] = useState(initialForm); const [run,setRun] = useState<RunResult|null>(null); const [busy,setBusy] = useState(false); const [error,setError] = useState(""); const [accessToken,setAccessToken] = useState("");
  const parameterSummary = useMemo(() => `${form.platform} · ${form.duration} · ${form.aspect_ratio} · ${form.tone}`,[form]);
  async function submit(event:FormEvent<HTMLFormElement>) { event.preventDefault(); setError(""); saveAccessToken(accessToken); if(!hasAccessToken()){setError("Staging 环境需要访问令牌");return;} setBusy(true); setRun(null); try { const project=await createProject(`${form.craft}创作项目`); const brief=await createBrief(project.id,form); const created=await createRun(project.id,brief.id); for(let index=0;index<30;index+=1){const current=await getRun(created.id);setRun(current);if(["PASSED","FAILED","CANCELLED"].includes(current.status))break;await new Promise(resolve=>setTimeout(resolve,1000));}} catch(cause){setError(cause instanceof Error?cause.message:"发生未知错误");} finally{setBusy(false);} }
  return <main className="shell">
    <nav className="topbar"><div className="brand"><span>HA</span>HA <small>CREATOR</small></div><div className="navStatus"><span />服务正常 <b>生产工作台</b></div></nav>
    <header className="hero"><div><span className="eyebrow">INTANGIBLE CULTURAL HERITAGE · AI STUDIO</span><h1>让非遗内容创作<br/>有据可查，有法可循。</h1><p>从知识检索、创作生成到独立验收，每一次输出都有完整证据链。</p></div><div className="heroMetric"><b>01</b><span>参数版本</span><b>02</b><span>知识证据</span><b>03</b><span>质量验收</span></div></header>
    <section className="workspace">
      <form className="panel controls" onSubmit={submit}><div className="panelHeading"><div><span className="panelNumber">01</span><h2>创作参数</h2></div><span>已自动保存</span></div>
        {AUTH_REQUIRED&&<label className="authGate">Staging 访问令牌<input type="password" autoComplete="off" value={accessToken} onChange={e=>setAccessToken(e.target.value)} placeholder="粘贴短期 JWT"/></label>}
        <label>创作主题<input value={form.craft} onChange={e=>setForm({...form,craft:e.target.value})}/></label><label>想讲的瞬间<textarea value={form.story_seed} onChange={e=>setForm({...form,story_seed:e.target.value})}/></label><label>目标受众<input value={form.audience} onChange={e=>setForm({...form,audience:e.target.value})}/></label>
        <div className="grid"><label>发布平台<select value={form.platform} onChange={e=>setForm({...form,platform:e.target.value})}><option>B站</option><option>抖音</option><option>小红书</option><option>视频号</option></select></label><label>时长<select value={form.duration} onChange={e=>setForm({...form,duration:e.target.value})}><option>15秒</option><option>30秒</option><option>45秒</option><option>60秒</option><option>90秒</option></select></label><label>画幅<select value={form.aspect_ratio} onChange={e=>setForm({...form,aspect_ratio:e.target.value})}><option>9:16</option><option>16:9</option><option>3:4</option><option>1:1</option></select></label><label>表达气质<select value={form.tone} onChange={e=>setForm({...form,tone:e.target.value})}><option>纪录片</option><option>安静观察</option><option>年轻轻快</option><option>诗意东方</option></select></label></div>
        <div className="parameterSummary"><span>本次创作规格</span><b>{parameterSummary}</b></div><button disabled={busy}>{busy?"正在检索、生成并验证…":"生成完整创作方案"}<span>↗</span></button>{error&&<p className="error">{error}</p>}
      </form>
      <section className="result panel"><div className="panelHeading resultHeader"><div><span className="panelNumber">02</span><h2>生成结果</h2></div><span className={`status ${run?.status??"idle"}`}>{busy?"处理中":run?.status==="PASSED"?"验收通过":run?.status??"等待提交"}</span></div>{!run?.script&&<div className="empty"><div className="emptyMark">文</div><h3>{busy?"正在生成创作方案":"等待一份新的创作任务"}</h3><p>{busy?"正在检索知识库并执行质量验收，请稍候。":"填写左侧参数后，系统将在这里呈现脚本、分镜、发布文案和证据链。"}</p></div>}{run?.error_message&&<p className="error">{run.error_message}</p>}{run?.script&&<ResultView run={run}/>}</section>
    </section><footer><span>HAHA CREATOR SYSTEM</span><p>非遗知识与智能创作基础设施 · 本地开发环境</p></footer>
  </main>;
}
