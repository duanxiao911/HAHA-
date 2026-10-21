"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { ProductFrame } from "@/components/community/ProductFrame";
import { StateNotice } from "@/components/community/StateNotice";
import { TrustBadge } from "@/components/community/TrustBadge";
import { type ContentSummary, useCommunity } from "@/lib/community";

const channels = [["embroidery","刺绣"],["dyeing","染织"],["ceramics","陶瓷"],["woodwork","木作"],["bamboo","竹编"],["papercut","剪纸"],["opera","戏曲"],["folklore","民俗"]] as const;
const expandedChannels = [
  ["工艺类",["刺绣","染织","陶瓷","木作","竹编","剪纸","雕刻","漆艺","金工"]],
  ["表演类",["戏曲","曲艺","传统音乐","传统舞蹈","杂技"]],
  ["生活类",["民俗","节庆","礼俗","饮食技艺","传统服饰","传统医药"]],
  ["探索",["文化地图","非遗项目","传承人","专题","课堂","活动"]],
] as const;
const topics = [["中国蓝染地图","从植物、河流与村落出发，理解蓝色如何在不同地方生长。","染"],["100 位年轻传承人","记录年轻一代如何学习、改变并继续一门手艺。","人"],["从泥土到瓷器","跟随材料经历塑形、施釉与火的考验。","器"]] as const;

const compactNumber = new Intl.NumberFormat("zh-CN", { notation: "compact", maximumFractionDigits: 1 });

function formatDuration(seconds?: number): string {
  const safe = Math.max(0, Math.round(seconds ?? 0));
  return `${String(Math.floor(safe / 60)).padStart(2,"0")}:${String(safe % 60).padStart(2,"0")}`;
}

function ContentCard({item,onPlay}:{item:ContentSummary;onPlay?:(item:ContentSummary)=>void}) {
  const placeholder=item.cover.placeholder;
  return <article className="contentCard"><button className={`contentThumb ${placeholder?.tone??"green"}${item.cover.url?" has-image":""}`} style={item.cover.url?{backgroundImage:`url(${JSON.stringify(item.cover.url)})`}:undefined} type="button" aria-label={`预览《${item.title}》`} onClick={()=>onPlay?.(item)}>{!item.cover.url?<span aria-hidden="true">{placeholder?.mark??"影"}</span>:null}<i className="playIcon" aria-hidden="true">▶</i><small className="contentStats">▷ {compactNumber.format(item.metrics.viewCount)}　◇ {compactNumber.format(item.metrics.interactionCount)}</small><b>{formatDuration(item.durationSeconds)}</b></button><div className="contentCopy"><span>{item.categoryLabel} · {item.regionLabel}</span><h3><Link href={`/content/${encodeURIComponent(item.id)}`} style={{color:"inherit",textDecoration:"none"}}>{item.title}</Link></h3><p>{item.creator.displayName}</p><TrustBadge status={item.trust.status} label={item.trust.label} sourceCount={item.trust.sourceCount} aiAssisted={item.trust.aiAssisted} compact/></div></article>;
}
function SectionHeading({eyebrow,title,action="查看全部 →",onAction}:{eyebrow?:string;title:string;action?:string;onAction?:()=>void}) { return <div className="feedHeading"><div>{eyebrow&&<p>{eyebrow}</p>}<h2>{title}</h2></div><button type="button" onClick={onAction}>{action}</button></div>; }
export default function CommunityPage() {
  const router=useRouter();
  const {snapshot,actions}=useCommunity();
  const apiMode=snapshot.runtime.mode==="api";
  const content=snapshot.contents;
  const [channelState,setChannelState]=useState<"collapsed"|"expanded">("collapsed");
  const [activeChannel,setActiveChannel]=useState("hot");
  const [feedOffset,setFeedOffset]=useState(0);
  const [feedItems,setFeedItems]=useState<ContentSummary[]>([]);
  const [feedCursor,setFeedCursor]=useState<string|null>(null);
  const [feedState,setFeedState]=useState<"loading"|"success"|"error">("loading");
  const [feedError,setFeedError]=useState("");
  const [trendTab,setTrendTab]=useState("综合"); const [previewId,setPreviewId]=useState<string|null>(null); const [toast,setToast]=useState("");
  useEffect(()=>{const frame=globalThis.requestAnimationFrame(()=>{const initial=new URLSearchParams(globalThis.location.search).get("channel");if(initial)setActiveChannel(initial);});return()=>globalThis.cancelAnimationFrame(frame);},[]);
  useEffect(()=>{function close(event:KeyboardEvent){if(event.key==="Escape"){setChannelState("collapsed");setPreviewId(null);}}document.addEventListener("keydown",close);return()=>document.removeEventListener("keydown",close);},[]);
  useEffect(()=>{if(!toast)return;const timer=globalThis.setTimeout(()=>setToast(""),2200);return()=>globalThis.clearTimeout(timer);},[toast]);

  function resetFeed(){setFeedState("loading");setFeedError("");setFeedItems([]);setFeedCursor(null);}
  function chooseChannel(value:string){resetFeed();setActiveChannel(value);const url=new URL(globalThis.location.href);url.searchParams.set("channel",value);globalThis.history.replaceState({},"",url);}
  function refreshFeed(){resetFeed();setFeedOffset(value=>value+1);}
  const nearbyRegion=snapshot.regions.find(region=>region.id==="region-guizhou")??snapshot.regions[0];
  const filtered=useMemo(()=>{
    if(activeChannel==="hot")return content;
    if(activeChannel==="following")return content.filter(item=>snapshot.followingPersonIds.includes(item.creatorId));
    if(activeChannel==="nearby")return nearbyRegion?content.filter(item=>item.regionId===nearbyRegion.id):[];
    if(activeChannel==="learning")return content.filter(item=>item.viewer.reactions.includes("want_to_learn"));
    const normalized=activeChannel.toLocaleLowerCase("zh-CN");
    return content.filter(item=>item.categoryId.toLocaleLowerCase("zh-CN")===normalized||item.categoryLabel.toLocaleLowerCase("zh-CN")===normalized);
  },[activeChannel,content,nearbyRegion,snapshot.followingPersonIds]);
  useEffect(()=>{
    if(!snapshot.runtime.hydrated)return;
    const controller=new AbortController();
    const mode=activeChannel==="following"?"following":activeChannel==="nearby"?"nearby":activeChannel==="learning"?"learning":"recommended";
    const channelId=["hot","following","nearby","learning"].includes(activeChannel)?undefined:activeChannel;
    void actions.getFeed({mode,channelId,regionId:mode==="nearby"?nearbyRegion?.id:undefined,limit:10},controller.signal)
      .then(page=>{setFeedItems(page.items);setFeedCursor(page.nextCursor);setFeedState("success");})
      .catch((error:unknown)=>{if(controller.signal.aborted)return;setFeedError(error instanceof Error?error.message:"内容 Feed 加载失败");setFeedState("error");});
    return()=>controller.abort();
  },[actions,activeChannel,feedOffset,nearbyRegion?.id,snapshot.runtime.hydrated]);
  const feed=feedItems.length?feedItems:filtered.slice(0,10);
  async function loadMore(){if(!feedCursor||feedState==="loading")return;setFeedState("loading");setFeedError("");try{const mode=activeChannel==="following"?"following":activeChannel==="nearby"?"nearby":activeChannel==="learning"?"learning":"recommended";const channelId=["hot","following","nearby","learning"].includes(activeChannel)?undefined:activeChannel;const page=await actions.getFeed({mode,channelId,regionId:mode==="nearby"?nearbyRegion?.id:undefined,cursor:feedCursor,limit:10});setFeedItems(items=>[...items,...page.items.filter(item=>!items.some(current=>current.id===item.id))]);setFeedCursor(page.nextCursor);setFeedState("success");}catch(error){setFeedError(error instanceof Error?error.message:"更多内容加载失败");setFeedState("error");}}
  const activeChannelLabel=activeChannel==="hot"?"推荐":activeChannel==="following"?"关注":activeChannel==="nearby"?`附近 · ${nearbyRegion?.name??"未设置"}`:activeChannel==="learning"?"正在学习":channels.find(([value])=>value===activeChannel)?.[1]??activeChannel;
  const emptyCopy=activeChannel==="following"?["还没有关注内容","先去认识传承人和创作者，关注后内容会出现在这里。","发现人物"]:activeChannel==="learning"?["还没有“想学”的内容","在内容详情点击“想学”，就能形成你的学习清单。","浏览推荐"]:activeChannel==="nearby"?["附近暂无内容",`当前地区是${nearbyRegion?.name??"未设置"}，可以进入文化地图继续探索。`,"打开地图"]:["这个频道还在准备内容","你可以先回到推荐，或者从其他工艺频道继续发现。","返回推荐"];
  const preview=previewId?content.find(item=>item.id===previewId)??null:null;
  const hero=content[0];
  const trendPool=trendTab==="视频"?content.filter(item=>item.contentType==="short_video"||item.contentType==="long_video"):trendTab==="项目"?content.filter(item=>item.projectIds.length>0):trendTab==="传承人"?content.filter(item=>item.creator.role==="inheritor"):content;
  return <ProductFrame className="communityV2" mainClassName="communityPage">
    <section className="brandBanner" aria-label="HAHA 品牌专题"><div><p>HAHA CULTURE COMMUNITY</p><h1>让手艺继续发生，<br/><em>让文化被今天看见。</em></h1><span>人物 · 地方 · 材料 · 日常 · {apiMode?"服务端内部测试数据":"本地演示数据"}</span></div><div className="bannerArtwork" aria-hidden="true"><i>非</i><i>遗</i><i>今</i></div></section>
    <div className={`communityNavSystem ${channelState}`}>
      <nav className="channelNavigation" aria-label="内容频道"><div className="channelCompact"><button className={activeChannel==="following"?"active special":"special"} type="button" onClick={()=>chooseChannel("following")}>◎ 关注</button><button className={activeChannel==="hot"?"active special":"special"} type="button" onClick={()=>chooseChannel("hot")}>🔥 推荐</button><button className={activeChannel==="nearby"?"active special":"special"} type="button" onClick={()=>chooseChannel("nearby")}>⌖ 附近</button><button className={activeChannel==="learning"?"active special":"special"} type="button" onClick={()=>chooseChannel("learning")}>◇ 正在学习</button><i aria-hidden="true"/>{channels.map(([value,label])=><button className={activeChannel===value?"active":""} type="button" key={value} onClick={()=>chooseChannel(value)} aria-current={activeChannel===value?"page":undefined}>{label}</button>)}<i aria-hidden="true"/><Link href="/topics">专题</Link><Link href="/events">活动</Link><Link href="/map">文化地图</Link><Link href="/learning">课堂</Link><button className="channelToggle" type="button" onClick={()=>setChannelState(value=>value==="expanded"?"collapsed":"expanded")} aria-expanded={channelState==="expanded"} aria-controls="expanded-channels">{channelState==="expanded"?"收起 ▲":"更多 ▼"}</button></div><div className="expandedChannels" id="expanded-channels" aria-hidden={channelState!=="expanded"}>{expandedChannels.map(([group,items])=><div key={group}><b>{group}</b><div>{items.map(item=><button type="button" key={item} onClick={()=>{if(item==="文化地图")router.push("/map");else if(item==="非遗项目")router.push("/heritage-projects");else if(item==="传承人")router.push("/inheritors");else if(item==="专题")router.push("/topics");else if(item==="活动")router.push("/events");else if(item==="课堂")router.push("/learning");else chooseChannel(item);setChannelState("collapsed");}}>{item}</button>)}</div></div>)}</div></nav>
    </div>
    <div className="communityContent">
      {hero?<section className="heroRecommendation" aria-labelledby="hero-title"><div className="largeFeature"><button className={`featureVisual ${hero.cover.placeholder?.tone??"red"}`} type="button" onClick={()=>setPreviewId(hero.id)} aria-label={`预览《${hero.title}》`}><span>{hero.cover.placeholder?.mark??"影"}</span><small>今日重点 · {hero.regionLabel}</small><b>{formatDuration(hero.durationSeconds)}</b></button><div className="featureCopy"><span>{hero.categoryLabel} · 编辑精选</span><h2 id="hero-title"><Link href={`/content/${encodeURIComponent(hero.id)}`} style={{color:"inherit",textDecoration:"none"}}>{hero.title}</Link></h2><p>{hero.summary}</p><div><b>{hero.creator.displayName}</b><span>{compactNumber.format(hero.metrics.viewCount)}播放 · {compactNumber.format(hero.metrics.interactionCount)}互动</span></div><TrustBadge status={hero.trust.status} label={hero.trust.label} sourceCount={hero.trust.sourceCount} compact/></div></div><div className="heroRecommendations">{content.slice(1,5).map(item=><ContentCard item={item} onPlay={item=>setPreviewId(item.id)} key={item.id}/>)}</div></section>:null}
      <section className="feedSection" id="recommended" aria-busy={feedState==="loading"}><SectionHeading eyebrow="FOR YOU" title={`内容 Feed · ${activeChannelLabel}`} action="刷新内容 ↻" onAction={refreshFeed}/>{!snapshot.runtime.hydrated||feedState==="loading"&&!feedItems.length?<div className="contentGrid skeletonGrid" aria-label="正在加载内容状态">{Array.from({length:10},(_,index)=><div className="contentSkeleton" key={index}><i/><b/><span/></div>)}</div>:snapshot.runtime.recoveryNotice?<StateNotice kind="offline" title="服务端内容暂时不可用" description={snapshot.runtime.recoveryNotice}/>:feedState==="error"&&!feedItems.length?<StateNotice kind="error" title="内容 Feed 没有加载完成" description={feedError} actionLabel="重新加载" onAction={refreshFeed}/>:feed.length?<><div className="contentGrid">{feed.map(item=><ContentCard item={item} onPlay={item=>setPreviewId(item.id)} key={item.id}/>)}</div>{feedError?<StateNotice kind="error" compact title="更多内容没有加载完成" description={feedError} actionLabel="重试" onAction={()=>void loadMore()}/>:null}{feedCursor?<div className="communityFeedMore"><button className="productButtonSecondary" type="button" disabled={feedState==="loading"} onClick={()=>void loadMore()}>{feedState==="loading"?"正在加载…":"加载更多"}</button></div>:null}</>:<div className="emptyState"><b>{emptyCopy[0]}</b><p>{emptyCopy[1]}</p><button type="button" onClick={()=>{if(activeChannel==="following")router.push("/inheritors");else if(activeChannel==="learning")chooseChannel("hot");else if(activeChannel==="nearby")router.push("/map");else chooseChannel("hot");}}>{emptyCopy[2]}</button></div>}</section>
      <section className="trendingSection"><SectionHeading eyebrow="TRENDING NOW" title="正在热门" onAction={()=>router.push("/search?sort=popular")}/><div className="trendTabs" role="tablist" aria-label="热门内容类型">{["综合","视频","项目","传承人"].map(tab=><button className={trendTab===tab?"active":""} type="button" role="tab" aria-selected={trendTab===tab} onClick={()=>setTrendTab(tab)} key={tab}>{tab}</button>)}</div><div className="trendingLayout"><div className="trendCards">{trendPool.slice(0,3).map(item=><ContentCard item={item} onPlay={item=>setPreviewId(item.id)} key={item.id}/>)}</div><ol className="rankingList">{[...content].sort((a,b)=>b.metrics.viewCount-a.metrics.viewCount).slice(0,6).map((item,index)=><li key={item.id}><b>{String(index+1).padStart(2,"0")}</b><Link href={`/content/${encodeURIComponent(item.id)}`}><h3>{item.title}</h3><p>{item.categoryLabel} · {compactNumber.format(item.metrics.viewCount)}播放</p></Link></li>)}</ol></div></section>
      {["刺绣","陶瓷","竹编","戏曲"].map(category=>{const items=content.filter(item=>item.categoryLabel===category).slice(0,5);return <section className="categorySection" key={category}><SectionHeading title={category} onAction={()=>chooseChannel(channels.find(([,label])=>label===category)?.[0]??category)}/>{items.length?<div className="contentGrid categoryGrid">{items.map(item=><ContentCard item={item} onPlay={item=>setPreviewId(item.id)} key={item.id}/>)}</div>:<div className="emptyState"><b>暂无{category}内容</b><p>这是由当前领域数据计算出的空状态。</p><button type="button" onClick={()=>chooseChannel("hot")}>浏览推荐</button></div>}</section>;})}
      <section className="regionDiscovery" id="regions"><SectionHeading eyebrow="EXPLORE BY PLACE" title="按地区发现非遗" action="进入文化地图 →" onAction={()=>router.push("/map")}/><div className="regionGrid">{snapshot.regions.map((region,index)=><Link href={`/map?region=${encodeURIComponent(region.id)}`} className={`regionCard regionTone${index%4}`} key={region.id}><span>{String(index+1).padStart(2,"0")}</span><h3>{region.name}</h3><p>{region.featuredCrafts.join(" · ")}</p><b>{region.projectCount} 个项目　→</b></Link>)}</div></section>
      <section className="topicSection" id="topics"><SectionHeading eyebrow="CURATED BY HAHA" title="专题策展" onAction={()=>router.push("/topics")}/><div className="topicGrid">{topics.map(([title,copy,mark],index)=><article className={`topicCard topicTone${index}`} key={title}><span>{mark}</span><div><small>HAHA 专题 · 0{index+1}</small><h3>{title}</h3><p>{copy}</p><Link href="/topics">进入专题 →</Link></div></article>)}</div></section>
      <section className="creatorTools" id="creator-tools"><SectionHeading eyebrow="HAHA CREATOR" title="创作者工具" onAction={()=>router.push("/creator")}/><div className="toolGrid"><Link href="/creator/submissions/new?type=video"><i>↑</i><div><h3>视频投稿</h3><p>进入可保存、可检查的投稿向导</p></div></Link><Link className="featuredTool" href="/creator"><i>✦</i><div><h3>AI 图文脚本</h3><p>从想法生成策划、脚本、分镜与发布建议</p></div></Link><Link href="/creator"><i>⌘</i><div><h3>创作参数工作台</h3><p>用明确参数推进脚本生成与质量验收</p></div></Link><Link href="/heritage-projects"><i>库</i><div><h3>文化资料库</h3><p>查找事实、来源与创作方法</p></div></Link><Link href="/creator"><i>↗</i><div><h3>创作中心</h3><p>管理项目、版本和审核状态</p></div></Link></div></section>
    </div>
    <footer className="communityFooterV2"><div><Link className="communityBrand" href="/"><span>HA</span>HA</Link><p>非遗知识与智能创作基础设施 · {apiMode?"内部测试":"本地演示"}</p></div><nav><a href="#recommended">内容发现</a><Link href="/map">文化地图</Link><Link href="/creator">创作中心</Link></nav><span>© 2026 HAHA CULTURE MEDIA</span></footer>
    {preview&&<div className="previewBackdrop" role="presentation" onMouseDown={event=>{if(event.target===event.currentTarget)setPreviewId(null);}}><section className="contentPreview" role="dialog" aria-modal="true" aria-labelledby="preview-title"><button className="previewClose" type="button" aria-label="关闭预览" onClick={()=>setPreviewId(null)}>×</button><div className={`previewVisual ${preview.cover.placeholder?.tone??"green"}`}><span>{preview.cover.placeholder?.mark??"影"}</span><i>▶</i></div><div><small>{preview.categoryLabel} · {preview.regionLabel}</small><h2 id="preview-title">{preview.title}</h2><p>来自 {preview.creator.displayName} · {compactNumber.format(preview.metrics.viewCount)} 播放 · {compactNumber.format(preview.metrics.interactionCount)} 互动</p><TrustBadge status={preview.trust.status} label={preview.trust.label} sourceCount={preview.trust.sourceCount} aiAssisted={preview.trust.aiAssisted}/><p className="previewNotice">当前没有接入真实视频流；进入详情可体验来源、互动、评论与知识注释闭环。{apiMode?"互动将写入服务端账户。":"互动仅保存为本地演示数据。"}</p><Link className="productButton" href={`/content/${encodeURIComponent(preview.id)}`}>查看完整内容 →</Link></div></section></div>}
    {toast&&<div className="communityToast" role="status" aria-live="polite">{toast}</div>}
  </ProductFrame>;
}
