"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { AUTH_REQUIRED, cancelRun, createBrief, createProject, createRun, DEMO_MODE, FailedJob, getRun, hasAccessToken, listFailedJobs, resolveFailedJob, retryFailedJob, RunEvent, RunResult, saveAccessToken, streamRunEvents } from "@/lib/api";

type CreatorForm = { craft:string; story_seed:string; audience:string; platform:string; tone:string; goal:string; duration:string; aspect_ratio:string; content_count:string; strictness:string; generation_mode:string };
type ScriptPayload = { title?:string; hook?:string; voiceover?:string[]; shots?:string[]; caption?:string; tags?:string[]; judgment?:[string,string][]; fact_checks?:string[]; audits?:[string,string][]; operation_notes?:[string,string][] };

const initialForm:CreatorForm = { craft:"中国剪纸",story_seed:"剪刀落下形成纹样",audience:"第一次接触非遗的人",platform:"B站",tone:"纪录片",goal:"文化科普",duration:"90秒",aspect_ratio:"16:9",content_count:"1条",strictness:"严格",generation_mode:"标准" };
const steps=["创作设定","创作判断","Master Script","结构化分镜","发布包","文化审核"];
const capabilities=[["✦","创作判断"],["⌘","结构规划"],["▦","分镜生成"],["↗","发布适配"]];
const runStages=[
  ["PENDING","等待调度"],
  ["CLAIMED","Worker 已领取"],
  ["RUNNING","准备生成"],
  ["RETRIEVING","检索知识证据"],
  ["GENERATING","生成脚本与分镜"],
  ["VALIDATING","独立质量验收"],
  ["PASSED","完成"],
] as const;

function ResultWorkspace({run,busy,onStart}:{run:RunResult|null;busy:boolean;onStart:()=>void}) {
  const script=(run?.script?.payload??{}) as ScriptPayload;
  if(!run?.script) return <div className="emptyState"><div className="sparkMark">✦</div><h3>{busy?"正在建立本次创作方案":"从一个想法开始"}</h3><p>{busy?"正在检索知识库、生成内容并执行独立质量验收。":"填写创作设定后，AI 会分析方向并生成完整方案。"}</p>{!busy&&<button className="startButton" type="button" onClick={onStart}>开始创作 <span>↓</span></button>}<div className="capabilityGrid" aria-label="创作能力">{capabilities.map(([icon,label])=><div key={label}><i>{icon}</i><b>{label}</b></div>)}</div></div>;
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

function RunProgress({run,streaming,onCancel}:{run:RunResult|null;streaming:boolean;onCancel:()=>void}) {
  if(!run)return null;
  const activeIndex=run.status==="RETRYING"?0:runStages.findIndex(([status])=>status===run.status);
  const terminal=["PASSED","FAILED","CANCELLED"].includes(run.status);
  return <div className="runProgress" aria-live="polite">
    <div className="progressSummary"><div><span className={`liveDot ${streaming?"connected":""}`}/><b>{streaming?"实时进度 · SSE":"运行状态"}</b><small>{run.status}{run.attempt?` · 第 ${run.attempt} 次尝试`:""}</small></div>{!terminal&&<button type="button" onClick={onCancel}>取消本次运行</button>}</div>
    <ol>{runStages.map(([status,label],index)=>{const state=index<activeIndex?"done":index===activeIndex?"active":"";return <li className={state} key={status}><span>{state==="done"?"✓":String(index+1).padStart(2,"0")}</span><b>{label}</b></li>;})}</ol>
    {run.status==="CANCELLED"&&<p className="terminalNote cancelled">运行已取消，Worker 不会继续写入脚本。</p>}
    {run.status==="FAILED"&&<p className="terminalNote failed">运行失败：{run.error_message||run.error_code||"未知原因"}</p>}
  </div>;
}

function OperationsPanel({jobs,loading,activeJob,onRefresh,onRetry,onResolve}:{jobs:FailedJob[];loading:boolean;activeJob:string;onRefresh:()=>void;onRetry:(job:FailedJob)=>void;onResolve:(job:FailedJob)=>void}) {
  return <section className="operationsPanel surface"><div className="sectionHeading"><span>04</span><div><h2>失败任务运维</h2><p>仅显示当前工作空间未解决任务；重试最多消耗三次尝试。</p></div><button className="refreshJobs" type="button" onClick={onRefresh} disabled={loading}>{loading?"刷新中…":"刷新列表"}</button></div>
    {jobs.length===0?<div className="operationsEmpty"><b>当前没有待处理失败任务</b><p>失败任务会在这里显示原因、尝试次数与可执行动作。</p></div>:<div className="failedJobList">{jobs.map(job=><article key={job.id}><div><span>{job.run.error_code||job.reason}</span><h3>{job.run_id}</h3><p>{job.run.error_message||job.reason}</p><small>第 {job.run.attempt} / 3 次尝试 · {new Date(job.created_at).toLocaleString("zh-CN")}</small></div><div><button type="button" onClick={()=>onRetry(job)} disabled={Boolean(activeJob)}>重新入队</button><button type="button" className="quietAction" onClick={()=>onResolve(job)} disabled={Boolean(activeJob)}>标记已处理</button></div></article>)}</div>}
  </section>;
}

export function CreatorWorkbench(){
  const [form,setForm]=useState<CreatorForm>(initialForm); const [run,setRun]=useState<RunResult|null>(null); const [busy,setBusy]=useState(false); const [streaming,setStreaming]=useState(false); const [error,setError]=useState(""); const [accessToken,setAccessToken]=useState(()=>globalThis.sessionStorage?.getItem("haha_access_token")??""); const [drawerOpen,setDrawerOpen]=useState(false); const [savedAt,setSavedAt]=useState(""); const [copied,setCopied]=useState(false); const [failedJobs,setFailedJobs]=useState<FailedJob[]>([]); const [jobsLoading,setJobsLoading]=useState(false); const [activeJob,setActiveJob]=useState(""); const draftLoaded=useRef(false); const streamAbortRef=useRef<AbortController|null>(null);
  const consoleRef=useRef<HTMLFormElement>(null); const craftRef=useRef<HTMLInputElement>(null); const workRef=useRef<HTMLElement>(null); const reviewRef=useRef<HTMLElement>(null); const operationsRef=useRef<HTMLDivElement>(null);
  useEffect(()=>{const timer=globalThis.setTimeout(()=>{const saved=globalThis.localStorage?.getItem("haha_creator_draft");if(saved){try{const parsed=JSON.parse(saved);if(parsed&&typeof parsed==="object"&&!Array.isArray(parsed))setForm(previous=>({...previous,...parsed as Partial<CreatorForm>}));}catch{globalThis.localStorage?.removeItem("haha_creator_draft");}}draftLoaded.current=true;},0);return()=>globalThis.clearTimeout(timer);},[]);
  useEffect(()=>()=>streamAbortRef.current?.abort(),[]);
  useEffect(()=>{document.body.style.overflow=drawerOpen?"hidden":"";function closeOnEscape(event:KeyboardEvent){if(event.key==="Escape")setDrawerOpen(false);}document.addEventListener("keydown",closeOnEscape);return()=>{document.body.style.overflow="";document.removeEventListener("keydown",closeOnEscape);};},[drawerOpen]);
  useEffect(()=>{if(!draftLoaded.current)return;const timer=globalThis.setTimeout(()=>{globalThis.localStorage?.setItem("haha_creator_draft",JSON.stringify(form));setSavedAt(new Date().toLocaleTimeString("zh-CN",{hour:"2-digit",minute:"2-digit"}));},350);return()=>globalThis.clearTimeout(timer);},[form]);
  const parameterSummary=useMemo(()=>`${form.platform} · ${form.duration} · ${form.aspect_ratio} · ${form.tone}`,[form]); const currentStep=run?.script?6:busy?2:1; const projectName=`${form.craft||"未命名"}创作项目`;
  function update<K extends keyof CreatorForm>(key:K,value:CreatorForm[K]){setForm(previous=>({...previous,[key]:value}));}
  function navigateTo(target:"work"|"settings"|"review"|"operations"){setDrawerOpen(false);const element=target==="work"?workRef.current:target==="review"?reviewRef.current:target==="operations"?operationsRef.current:consoleRef.current;element?.scrollIntoView({behavior:"smooth",block:"start"});if(target==="settings")globalThis.setTimeout(()=>craftRef.current?.focus(),450);}
  function applyRunEvent(event:RunEvent){if(!event.data.status)return;setRun(previous=>({id:event.data.run_id,status:event.data.status??previous?.status??"PENDING",attempt:event.data.attempt,error_code:event.data.error_code,error_message:event.data.error_message??"",updated_at:event.data.updated_at,script:previous?.id===event.data.run_id?previous.script:null}));}
  async function refreshFailedJobs(){if(DEMO_MODE){setFailedJobs([]);return;}saveAccessToken(accessToken);if(!hasAccessToken()){setError("请先填写 Staging 访问令牌");return;}setJobsLoading(true);try{const result=await listFailedJobs();setFailedJobs(result.items);}catch(cause){setError(cause instanceof Error?cause.message:"失败任务加载失败");}finally{setJobsLoading(false);}}
  async function watchRun(runId:string,controller:AbortController){setStreaming(true);try{await streamRunEvents(runId,applyRunEvent,controller.signal);const current=await getRun(runId);setRun(current);if(current.status==="FAILED")await refreshFailedJobs();return current;}finally{setStreaming(false);if(streamAbortRef.current===controller)streamAbortRef.current=null;}}
  async function cancelCurrentRun(){if(!run?.id||DEMO_MODE)return;setError("");try{const cancelled=await cancelRun(run.id);streamAbortRef.current?.abort();setRun(cancelled);setBusy(false);}catch(cause){setError(cause instanceof Error?cause.message:"取消失败");}}
  async function retryJob(job:FailedJob){saveAccessToken(accessToken);setActiveJob(job.id);setError("");try{const result=await retryFailedJob(job.id);setRun(result.run);setBusy(true);await refreshFailedJobs();const controller=new AbortController();streamAbortRef.current?.abort();streamAbortRef.current=controller;await watchRun(result.run.id,controller);}catch(cause){if(!(cause instanceof DOMException&&cause.name==="AbortError"))setError(cause instanceof Error?cause.message:"重试失败");}finally{setBusy(false);setActiveJob("");}}
  async function resolveJob(job:FailedJob){saveAccessToken(accessToken);setActiveJob(job.id);setError("");try{await resolveFailedJob(job.id);await refreshFailedJobs();}catch(cause){setError(cause instanceof Error?cause.message:"标记失败");}finally{setActiveJob("");}}
  async function submit(event:FormEvent<HTMLFormElement>){event.preventDefault();setError("");saveAccessToken(accessToken);if(!hasAccessToken()){setError("Staging 环境需要访问令牌");return;}setBusy(true);setRun(null);try{if(DEMO_MODE){await new Promise(resolve=>setTimeout(resolve,900));const platformTip=form.platform==="B站"?"用章节感和信息密度建立观看价值":form.platform==="抖音"?"前三秒直接呈现动作与视觉反差":form.platform==="小红书"?"用可收藏的知识点与审美画面组织内容":"用熟人传播语境强化文化认同";setRun({id:"github-pages-demo",status:"PASSED",error_message:"",script:{payload:{title:`${form.craft}｜${form.platform} ${form.duration}创作方案`,hook:`${form.story_seed}——从这个真实瞬间进入${form.craft}的材料、技艺与人的故事。`,voiceover:[`这是一条面向${form.audience}的${form.goal}内容。`,`镜头从“${form.story_seed}”开始，让动作先于解释发生。`,`随后补充${form.craft}的材料、工序与地方语境，不虚构未经证实的人物与年代。`,`结尾邀请观众继续认识手艺背后的人，并保留可验证的知识来源。`],shots:[`近景｜${form.story_seed}，以${form.tone}的节奏建立视觉钩子`,`中景｜呈现材料与关键工序，画幅 ${form.aspect_ratio}`,`特写｜手部动作与纹理变化，强调真实细节`,`收束｜人物、地方与当代生活的连接`],caption:`${form.craft}不只是一个结果，更是材料、时间与人的共同工作。这支${form.duration}内容为${form.platform}重新组织观看节奏。`,tags:[form.craft,"非遗",form.platform,form.goal],judgment:[["发布平台",form.platform],["成片规格",`${form.duration} · ${form.aspect_ratio}`],["表达气质",form.tone],["目标受众",form.audience]],audits:[["事实边界","演示内容未补写具体传承人、年代或地域结论，正式发布前需引用知识证据。"]],operation_notes:[["平台策略",platformTip],["演示说明","当前为 GitHub Pages 前端演示结果；正式环境由后端模型与独立验收服务生成。"]]},evidence:{verification:{checked_at:new Date().toISOString()},retrieval:{user_query:`${form.craft} ${form.story_seed}`,creative_chunks_used:["demo-creative-method"],operation_chunks_used:[`demo-${form.platform}`],fact_chunks_used:["demo-fact-boundary"]}}}});return;}const project=await createProject(projectName);const brief=await createBrief(project.id,{craft:form.craft,story_seed:form.story_seed,audience:form.audience,platform:form.platform,tone:form.tone,goal:form.goal,duration:form.duration,aspect_ratio:form.aspect_ratio,asset_context:`内容数量：${form.content_count}；事实严格度：${form.strictness}；生成模式：${form.generation_mode}`});const created=await createRun(project.id,brief.id);setRun({id:created.id,status:"PENDING",error_message:"",script:null});const controller=new AbortController();streamAbortRef.current?.abort();streamAbortRef.current=controller;await watchRun(created.id,controller);}catch(cause){if(!(cause instanceof DOMException&&cause.name==="AbortError"))setError(cause instanceof Error?cause.message:"发生未知错误");}finally{setBusy(false);}}
  async function copyPublishPack(){const script=(run?.script?.payload??{}) as ScriptPayload;if(!script.caption)return;await navigator.clipboard.writeText(`${script.caption}\n\n${(script.tags??[]).map(tag=>`#${tag.replace(/^#/,"")}`).join(" ")}`);setCopied(true);setTimeout(()=>setCopied(false),1800);}
  return <main className="appShell" id="main-content">
    {DEMO_MODE&&<div className="demoNotice"><b>演示模式</b><span>当前站点用于产品展示；生成结果会实时响应所选参数，正式发布版将连接模型、知识库与独立验收服务。</span></div>}
    <button className={`drawerBackdrop ${drawerOpen?"visible":""}`} type="button" onClick={()=>setDrawerOpen(false)} aria-label="关闭导航遮罩" tabIndex={drawerOpen?0:-1}/><aside id="creator-navigation" className={`drawer ${drawerOpen?"open":""}`} aria-hidden={!drawerOpen} aria-modal="true" role="dialog" inert={drawerOpen?undefined:true}><div className="drawerBrand"><span>HA</span>HA <small>创作中心</small></div><button className="drawerClose" type="button" onClick={()=>setDrawerOpen(false)} aria-label="关闭导航">×</button><nav><button type="button" onClick={()=>navigateTo("work")}>创作工作台</button><button type="button" onClick={()=>navigateTo("operations")}>失败任务运维 <small>{failedJobs.length?`${failedJobs.length} 待处理`:"C4"}</small></button><button type="button" disabled>数据中心 <small>即将开放</small></button><button type="button" disabled>互动管理 <small>即将开放</small></button><button type="button" onClick={()=>navigateTo("review")}>文化审核</button><hr/><Link href="/community">← 返回视频社区</Link><button type="button" disabled>视频投稿 <small>即将开放</small></button><button type="button" className="active" onClick={()=>navigateTo("settings")}>图文脚本</button></nav></aside>
    <div className="stickyChrome"><header className="appHeader"><button className="menuButton" type="button" onClick={()=>setDrawerOpen(true)} aria-label="打开导航" aria-controls="creator-navigation" aria-expanded={drawerOpen}><span/><span/><span/></button><div className="headerBrand"><b>HAHA 创作中心</b><small>人工智能创意工作室 · V2.0</small></div><div className="headerCopy"><strong>把一个想法变成可拍、可审、可发布的内容</strong><span>事实库 × 创作方法库 × 运营策略库</span></div><div className="headerActions"><span className="saveState"><i/>已自动保存{savedAt&&` · ${savedAt}`}</span><b>{projectName}</b></div></header><nav className="stepNav" aria-label="创作流程">{steps.map((step,index)=>{const number=index+1;const state=number<currentStep?"done":number===currentStep?"active":"";return <div className={state} key={step}><span>{number<currentStep?"✓":String(number).padStart(2,"0")}</span><b>{step}</b></div>;})}</nav></div>
    <div className="pageContent">
      <section ref={workRef} className="workPanel surface"><div className="sectionHeading"><span>02</span><div><h1>AI 创作工作区</h1><p>从创作判断开始，逐步完成脚本、分镜与发布适配。</p></div><div className={`runStatus ${run?.status??"idle"}`}>{busy?"处理中":run?.status==="PASSED"?"验收通过":run?.status==="CANCELLED"?"已取消":run?.status??"等待创作"}</div></div><RunProgress run={run} streaming={streaming} onCancel={cancelCurrentRun}/>{run?.error_message&&run.status!=="FAILED"&&<p className="error">{run.error_message}</p>}<ResultWorkspace run={run} busy={busy} onStart={()=>navigateTo("settings")}/>{run?.script&&<div className="resultActions"><span className="saveState">✓ 已保存为不可变版本</span><button type="button" className="primaryAction" onClick={copyPublishPack}>{copied?"已复制发布包":"复制发布包"}</button></div>}</section>
      <aside ref={reviewRef} className="reviewPanel surface"><div className="sectionHeading"><span>03</span><div><h2>判断与审核</h2><p>核对事实来源、文化风险与平台适配度。</p></div></div><Inspector run={run}/></aside>
    <form ref={consoleRef} className="controlConsole surface" onSubmit={submit}><div className="consoleHeading"><div><span>01</span><div><h2>创作设定</h2><p>定义这次内容要讲什么、讲给谁、用什么规格生成。</p></div></div><div className="parameterPill">本次规格 · <b>{parameterSummary}</b></div></div>
      {AUTH_REQUIRED&&<label className="authGate">Staging 访问令牌<input type="password" autoComplete="off" value={accessToken} onChange={event=>setAccessToken(event.target.value)} placeholder="粘贴短期 JWT"/></label>}
      <div className="consoleGrid">
        <fieldset><legend><i>A</i>创作核心</legend><label>创作主题<input ref={craftRef} value={form.craft} onChange={event=>update("craft",event.target.value)}/></label><label>想讲的一个瞬间<textarea value={form.story_seed} onChange={event=>update("story_seed",event.target.value)}/></label></fieldset>
        <fieldset><legend><i>B</i>受众与平台</legend><label>内容目标<select value={form.goal} onChange={event=>update("goal",event.target.value)}><option>文化科普</option><option>故事传播</option><option>活动推广</option><option>技艺记录</option></select></label><label>目标受众<input value={form.audience} onChange={event=>update("audience",event.target.value)}/></label><label>发布平台<select value={form.platform} onChange={event=>update("platform",event.target.value)}><option>B站</option><option>抖音</option><option>小红书</option><option>视频号</option></select></label></fieldset>
        <fieldset><legend><i>C</i>成片规格</legend><div className="splitFields"><label>成片时长<select value={form.duration} onChange={event=>update("duration",event.target.value)}><option>15秒</option><option>30秒</option><option>45秒</option><option>60秒</option><option>90秒</option></select></label><label>画幅<select value={form.aspect_ratio} onChange={event=>update("aspect_ratio",event.target.value)}><option>9:16</option><option>16:9</option><option>3:4</option><option>1:1</option></select></label></div><label>内容数量<select value={form.content_count} onChange={event=>update("content_count",event.target.value)}><option>1条</option><option>3条</option><option>5条</option></select></label></fieldset>
        <fieldset><legend><i>D</i>风格与生成</legend><label>表达气质<select value={form.tone} onChange={event=>update("tone",event.target.value)}><option>纪录片</option><option>安静观察</option><option>年轻轻快</option><option>诗意东方</option></select></label><label>事实严格度<div className="segment three">{["灵活","平衡","严格"].map(value=><button type="button" className={form.strictness===value?"selected":""} key={value} onClick={()=>update("strictness",value)}>{value}</button>)}</div></label><label>生成模式<div className="segment">{["快速","标准","精创"].map(value=><button type="button" className={form.generation_mode===value?"selected":""} key={value} onClick={()=>update("generation_mode",value)}>{value}</button>)}</div></label><button className="generateButton" disabled={busy}>{busy?"正在生成并验收…":"✦ 生成本次创作判断"}</button></fieldset>
      </div>{error&&<p className="error consoleError">{error}</p>}
    </form>
      {!DEMO_MODE&&<div ref={operationsRef} className="operationsAnchor"><OperationsPanel jobs={failedJobs} loading={jobsLoading} activeJob={activeJob} onRefresh={refreshFailedJobs} onRetry={retryJob} onResolve={resolveJob}/></div>}
    </div><footer><span>HAHA CREATOR SYSTEM</span><p>非遗知识与智能创作基础设施 · Production Workbench</p></footer>
  </main>;
}

export { default } from "./community";
