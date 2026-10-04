"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { AUTH_REQUIRED, createBrief, createProject, createRun, getRun, hasAccessToken, RunResult, saveAccessToken } from "@/lib/api";

type CreatorForm = { craft:string; story_seed:string; audience:string; platform:string; tone:string; goal:string; duration:string; aspect_ratio:string; content_count:string; strictness:string; generation_mode:string };
type ScriptPayload = { title?:string; hook?:string; voiceover?:string[]; shots?:string[]; caption?:string; tags?:string[]; judgment?:[string,string][]; fact_checks?:string[]; audits?:[string,string][]; operation_notes?:[string,string][] };

const initialForm:CreatorForm = { craft:"中国剪纸",story_seed:"剪刀落下形成纹样",audience:"第一次接触非遗的人",platform:"B站",tone:"纪录片",goal:"文化科普",duration:"90秒",aspect_ratio:"16:9",content_count:"1条",strictness:"严格",generation_mode:"标准" };
const steps=["创作设定","创作判断","Master Script","结构化分镜","发布包","文化审核"];
const capabilities=[["✦","创作判断"],["⌘","结构规划"],["▦","分镜生成"],["↗","发布适配"]];

function ResultWorkspace({run,busy}:{run:RunResult|null;busy:boolean}) {
  const script=(run?.script?.payload??{}) as ScriptPayload;
  if(!run?.script) return <div className="emptyState"><div className="sparkMark">✦</div><h3>{busy?"正在建立本次创作方案":"从一个想法开始"}</h3><p>{busy?"正在检索知识库、生成内容并执行独立质量验收。":"完成下方创作设定后，AI 会先分析内容方向，再生成完整创作方案。"}</p><div className="capabilityGrid">{capabilities.map(([icon,label])=><div key={label}><i>{icon}</i><b>{label}</b></div>)}</div></div>;
  return <div className="resultStack">
    <article className="resultCard judgmentCard"><div className="cardHead"><span>01</span><h3>本次创作判断</h3></div><h2>{script.title??"未命名脚本"}</h2><p>{script.hook}</p><div className="chips">{(script.judgment??[]).map(([key,value])=><span key={key}>{key} · {value}</span>)}</div></article>
    <article className="resultCard"><div className="cardHead"><span>02</span><h3>Master Script</h3></div><ol className="scriptLines">{(script.voiceover??[]).map((line,index)=><li key={`${index}-${line}`}>{line}</li>)}</ol></article>
    <article className="resultCard"><div className="cardHead"><span>03</span><h3>结构化分镜</h3></div><ol className="shotList">{(script.shots??[]).map((shot,index)=><li key={`${index}-${shot}`}><b>{String(index+1).padStart(2,"0")}</b><span>{shot}</span></li>)}</ol></article>
    <article className="resultCard publishPack"><div><div className="cardHead"><span>04</span><h3>发布包</h3></div><p>{script.caption}</p></div><div className="tags">{(script.tags??[]).map(tag=><span key={tag}>#{tag.replace(/^#/,"")}</span>)}</div></article>
  </div>;
}

function Inspector({run}:{run:RunResult|null}) {
  const script=(run?.script?.payload??{}) as ScriptPayload;
  const evidence=run?.script?.evidence??{};
  const verification=(evidence.verification??{}) as {checked_at?:string};
  const retrieval=(evidence.retrieval??{}) as {user_query?:string;creative_chunks_used?:string[];operation_chunks_used?:string[];fact_chunks_used?:string[]};
  const evidenceCount=(retrieval.creative_chunks_used?.length??0)+(retrieval.operation_chunks_used?.length??0)+(retrieval.fact_chunks_used?.length??0);
  const auditItems=script.audits??[];
  return <div className="inspectorBody">
    <article className="auditCard"><div className="auditIcon">⌕</div><div><b>事实来源</b><p>{run?.script?`本次使用 ${evidenceCount} 条知识证据`:"生成后显示检索来源与引用证据"}</p>{retrieval.user_query&&<small>{retrieval.user_query}</small>}</div></article>
    <article className="auditCard"><div className="auditIcon">✓</div><div><b>文化审核</b><p>{run?.status==="PASSED"?"独立验收已通过":"等待脚本进入审核流程"}</p>{verification.checked_at&&<small>{new Date(verification.checked_at).toLocaleString("zh-CN")}</small>}</div></article>
    <article className="auditCard"><div className="auditIcon">!</div><div><b>风险提示</b><p>{auditItems.length?auditItems.map(([,text])=>text).join("；"):"尚未发现待处理风险"}</p></div></article>
    <article className="auditCard"><div className="auditIcon">↗</div><div><b>运营建议</b><p>{script.operation_notes?.length?script.operation_notes.map(([,text])=>text).join("；"):"生成后给出平台适配与发布建议"}</p></div></article>
  </div>;
}

export default function CreatorPage(){
  const [form,setForm]=useState<CreatorForm>(initialForm); const [run,setRun]=useState<RunResult|null>(null); const [busy,setBusy]=useState(false); const [error,setError]=useState(""); const [accessToken,setAccessToken]=useState(""); const [drawerOpen,setDrawerOpen]=useState(false); const [savedAt,setSavedAt]=useState(""); const [copied,setCopied]=useState(false); const draftLoaded=useRef(false);
  useEffect(()=>{const timer=globalThis.setTimeout(()=>{const saved=globalThis.localStorage?.getItem("haha_creator_draft");if(saved){try{const parsed=JSON.parse(saved);if(parsed&&typeof parsed==="object"&&!Array.isArray(parsed))setForm(previous=>({...previous,...parsed as Partial<CreatorForm>}));}catch{globalThis.localStorage?.removeItem("haha_creator_draft");}}draftLoaded.current=true;},0);return()=>globalThis.clearTimeout(timer);},[]);
  useEffect(()=>{if(!draftLoaded.current)return;const timer=globalThis.setTimeout(()=>{globalThis.localStorage?.setItem("haha_creator_draft",JSON.stringify(form));setSavedAt(new Date().toLocaleTimeString("zh-CN",{hour:"2-digit",minute:"2-digit"}));},350);return()=>globalThis.clearTimeout(timer);},[form]);
  const parameterSummary=useMemo(()=>`${form.platform} · ${form.duration} · ${form.aspect_ratio} · ${form.tone}`,[form]); const currentStep=run?.script?6:busy?2:1; const projectName=`${form.craft||"未命名"}创作项目`;
  function update<K extends keyof CreatorForm>(key:K,value:CreatorForm[K]){setForm(previous=>({...previous,[key]:value}));}
  async function submit(event:FormEvent<HTMLFormElement>){event.preventDefault();setError("");saveAccessToken(accessToken);if(!hasAccessToken()){setError("Staging 环境需要访问令牌");return;}setBusy(true);setRun(null);try{const project=await createProject(projectName);const brief=await createBrief(project.id,{craft:form.craft,story_seed:form.story_seed,audience:form.audience,platform:form.platform,tone:form.tone,goal:form.goal,duration:form.duration,aspect_ratio:form.aspect_ratio,asset_context:`内容数量：${form.content_count}；事实严格度：${form.strictness}；生成模式：${form.generation_mode}`});const created=await createRun(project.id,brief.id);for(let index=0;index<30;index+=1){const current=await getRun(created.id);setRun(current);if(["PASSED","FAILED","CANCELLED"].includes(current.status))break;await new Promise(resolve=>setTimeout(resolve,1000));}}catch(cause){setError(cause instanceof Error?cause.message:"发生未知错误");}finally{setBusy(false);}}
  async function copyPublishPack(){const script=(run?.script?.payload??{}) as ScriptPayload;if(!script.caption)return;await navigator.clipboard.writeText(`${script.caption}\n\n${(script.tags??[]).map(tag=>`#${tag.replace(/^#/,"")}`).join(" ")}`);setCopied(true);setTimeout(()=>setCopied(false),1800);}
  return <main className="appShell">
    <div className={`drawerBackdrop ${drawerOpen?"visible":""}`} onClick={()=>setDrawerOpen(false)}/><aside className={`drawer ${drawerOpen?"open":""}`} aria-hidden={!drawerOpen}><div className="drawerBrand"><span>HA</span>HA <small>创作中心</small></div><button className="drawerClose" type="button" onClick={()=>setDrawerOpen(false)} aria-label="关闭导航">×</button><nav><a>创作工作台</a><a>内容管理</a><a>数据中心</a><a>互动管理</a><a>文化审核</a><hr/><a>返回社区</a><a>视频投稿</a><a className="active">图文脚本</a></nav></aside>
    <div className="stickyChrome"><header className="appHeader"><button className="menuButton" type="button" onClick={()=>setDrawerOpen(true)} aria-label="打开导航"><span/><span/><span/></button><div className="headerBrand"><b>HAHA 创作中心</b><small>人工智能创意工作室 · V2.0</small></div><div className="headerCopy"><strong>把一个想法变成可拍、可审、可发布的内容</strong><span>事实库 × 创作方法库 × 运营策略库</span></div><div className="headerActions"><span className="saveState"><i/>已自动保存{savedAt&&` · ${savedAt}`}</span><b>{projectName}</b><button type="button" aria-label="更多操作">•••</button></div></header><nav className="stepNav" aria-label="创作流程">{steps.map((step,index)=>{const number=index+1;const state=number<currentStep?"done":number===currentStep?"active":"";return <div className={state} key={step}><span>{number<currentStep?"✓":String(number).padStart(2,"0")}</span><b>{step}</b></div>;})}</nav></div>
    <div className="pageContent"><section className="mainLayer">
      <section className="workPanel surface"><div className="sectionHeading"><span>02</span><div><h1>AI 创作工作区</h1><p>从创作判断开始，逐步完成脚本、分镜与发布适配。</p></div><div className={`runStatus ${run?.status??"idle"}`}>{busy?"处理中":run?.status==="PASSED"?"验收通过":run?.status??"等待创作"}</div></div>{run?.error_message&&<p className="error">{run.error_message}</p>}<ResultWorkspace run={run} busy={busy}/>{run?.script&&<div className="resultActions"><span className="saveState">✓ 已保存为不可变版本</span><button type="button" className="primaryAction" onClick={copyPublishPack}>{copied?"已复制发布包":"复制发布包"}</button></div>}</section>
      <aside className="reviewPanel surface"><div className="sectionHeading"><span>03</span><div><h2>判断与审核</h2><p>核对事实来源、文化风险与平台适配度。</p></div></div><Inspector run={run}/></aside>
    </section>
    <form className="controlConsole surface" onSubmit={submit}><div className="consoleHeading"><div><span>01</span><div><h2>创作设定</h2><p>定义这次内容要讲什么、讲给谁、用什么规格生成。</p></div></div><div className="parameterPill">本次规格 · <b>{parameterSummary}</b></div></div>
      {AUTH_REQUIRED&&<label className="authGate">Staging 访问令牌<input type="password" autoComplete="off" value={accessToken} onChange={event=>setAccessToken(event.target.value)} placeholder="粘贴短期 JWT"/></label>}
      <div className="consoleGrid">
        <fieldset><legend><i>A</i>创作核心</legend><label>创作主题<input value={form.craft} onChange={event=>update("craft",event.target.value)}/></label><label>想讲的一个瞬间<textarea value={form.story_seed} onChange={event=>update("story_seed",event.target.value)}/></label></fieldset>
        <fieldset><legend><i>B</i>受众与平台</legend><label>内容目标<select value={form.goal} onChange={event=>update("goal",event.target.value)}><option>文化科普</option><option>故事传播</option><option>活动推广</option><option>技艺记录</option></select></label><label>目标受众<input value={form.audience} onChange={event=>update("audience",event.target.value)}/></label><label>发布平台<select value={form.platform} onChange={event=>update("platform",event.target.value)}><option>B站</option><option>抖音</option><option>小红书</option><option>视频号</option></select></label></fieldset>
        <fieldset><legend><i>C</i>成片规格</legend><div className="splitFields"><label>成片时长<select value={form.duration} onChange={event=>update("duration",event.target.value)}><option>15秒</option><option>30秒</option><option>45秒</option><option>60秒</option><option>90秒</option></select></label><label>画幅<select value={form.aspect_ratio} onChange={event=>update("aspect_ratio",event.target.value)}><option>9:16</option><option>16:9</option><option>3:4</option><option>1:1</option></select></label></div><label>内容数量<select value={form.content_count} onChange={event=>update("content_count",event.target.value)}><option>1条</option><option>3条</option><option>5条</option></select></label></fieldset>
        <fieldset><legend><i>D</i>风格与生成</legend><label>表达气质<select value={form.tone} onChange={event=>update("tone",event.target.value)}><option>纪录片</option><option>安静观察</option><option>年轻轻快</option><option>诗意东方</option></select></label><label>事实严格度<div className="segment three">{["灵活","平衡","严格"].map(value=><button type="button" className={form.strictness===value?"selected":""} key={value} onClick={()=>update("strictness",value)}>{value}</button>)}</div></label><label>生成模式<div className="segment">{["快速","标准","精创"].map(value=><button type="button" className={form.generation_mode===value?"selected":""} key={value} onClick={()=>update("generation_mode",value)}>{value}</button>)}</div></label><button className="generateButton" disabled={busy}>{busy?"正在生成并验收…":"✦ 生成本次创作判断"}</button></fieldset>
      </div>{error&&<p className="error consoleError">{error}</p>}
    </form></div><footer><span>HAHA CREATOR SYSTEM</span><p>非遗知识与智能创作基础设施 · Production Workbench</p></footer>
  </main>;
}
