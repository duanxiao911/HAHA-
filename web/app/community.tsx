"use client";

import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";

type ContentItem = { id:string; mark:string; category:string; region:string; title:string; author:string; views:string; interactions:string; duration:string; tone:string };

const channels = [["embroidery","刺绣"],["dyeing","染织"],["ceramics","陶瓷"],["woodwork","木作"],["bamboo","竹编"],["papercut","剪纸"],["opera","戏曲"],["folklore","民俗"]] as const;
const expandedChannels = [
  ["工艺类",["刺绣","染织","陶瓷","木作","竹编","剪纸","雕刻","漆艺","金工"]],
  ["表演类",["戏曲","曲艺","传统音乐","传统舞蹈","杂技"]],
  ["生活类",["民俗","节庆","礼俗","饮食技艺","传统服饰","传统医药"]],
  ["探索",["文化地图","非遗项目","传承人","专题","课堂","活动"]],
] as const;
const content:ContentItem[] = [
  {id:"embroidery-01",mark:"绣",category:"刺绣",region:"贵州",title:"一根线，怎样绣出远方？",author:"阿锦的绣房",views:"8.6万",interactions:"3,214",duration:"02:18",tone:"red"},
  {id:"ceramics-01",mark:"陶",category:"陶瓷",region:"景德镇",title:"泥土被火记住的声音",author:"泥与火工作室",views:"6.2万",interactions:"2,038",duration:"03:42",tone:"green"},
  {id:"dyeing-01",mark:"染",category:"染织",region:"云南",title:"蓝染为什么会留下冰裂纹？",author:"山野染房",views:"5.8万",interactions:"1,926",duration:"01:56",tone:"blue"},
  {id:"bamboo-01",mark:"编",category:"竹编",region:"四川",title:"竹丝在指尖慢慢成形",author:"青篾计划",views:"4.9万",interactions:"1,488",duration:"02:31",tone:"gold"},
  {id:"papercut-01",mark:"剪",category:"剪纸",region:"陕西",title:"窗花里藏着怎样的生活？",author:"纸上村落",views:"4.1万",interactions:"1,125",duration:"01:48",tone:"red"},
  {id:"opera-01",mark:"戏",category:"戏曲",region:"福建",title:"后台三分钟，台上一出戏",author:"古戏台记录",views:"3.7万",interactions:"986",duration:"04:12",tone:"blue"},
  {id:"woodwork-01",mark:"木",category:"木作",region:"浙江",title:"一榫一卯，不用一枚钉",author:"木间档案",views:"3.2万",interactions:"842",duration:"02:46",tone:"green"},
  {id:"folklore-01",mark:"俗",category:"民俗",region:"广东",title:"醒狮之前，人们在准备什么？",author:"南方节庆志",views:"2.9万",interactions:"771",duration:"03:08",tone:"gold"},
  {id:"embroidery-02",mark:"针",category:"刺绣",region:"江苏",title:"双面绣的另一面是什么？",author:"苏绣新语",views:"2.6万",interactions:"659",duration:"02:04",tone:"blue"},
  {id:"ceramics-02",mark:"瓷",category:"陶瓷",region:"福建",title:"一只白瓷杯的七十二道工序",author:"德化造物",views:"2.4万",interactions:"612",duration:"05:20",tone:"green"},
];
const regions = [["云南","扎染 · 银饰 · 民族舞蹈","128"],["贵州","苗绣 · 银饰 · 古歌","116"],["四川","竹编 · 漆器 · 川剧","142"],["浙江","木作 · 青瓷 · 丝织","135"],["江苏","刺绣 · 云锦 · 昆曲","121"],["福建","木偶戏 · 白瓷 · 茶技","109"],["广东","醒狮 · 粤剧 · 彩扎","148"],["新疆","木卡姆 · 刺绣 · 乐器","93"]] as const;
const topics = [["中国蓝染地图","从植物、河流与村落出发，理解蓝色如何在不同地方生长。","染"],["100 位年轻传承人","记录年轻一代如何学习、改变并继续一门手艺。","人"],["从泥土到瓷器","跟随材料经历塑形、施釉与火的考验。","器"]] as const;

function ContentCard({item}:{item:ContentItem}) { return <article className="contentCard"><button className={`contentThumb ${item.tone}`} type="button" aria-label={`播放《${item.title}》`}><span aria-hidden="true">{item.mark}</span><i className="playIcon" aria-hidden="true">▶</i><small className="contentStats">▷ {item.views}　◇ {item.interactions}</small><b>{item.duration}</b></button><div className="contentCopy"><span>{item.category} · {item.region}</span><h3>{item.title}</h3><p>{item.author}</p></div></article>; }
function SectionHeading({eyebrow,title,action="查看全部 →"}:{eyebrow?:string;title:string;action?:string}) { return <div className="feedHeading"><div>{eyebrow&&<p>{eyebrow}</p>}<h2>{title}</h2></div><button type="button">{action}</button></div>; }
function ActionIcon({type}:{type:"member"|"message"|"activity"|"favorite"|"history"|"profile"|"creator"}) {
  const paths={
    member:<><circle cx="12" cy="12" r="9"/><path d="m9 8 3 2 3-2-1 7h-4L9 8Z"/></>,
    message:<><rect x="3" y="5" width="18" height="14" rx="3"/><path d="m5 8 7 5 7-5"/></>,
    activity:<><path d="M4 14h3l2-7 4 10 2-6h5"/><circle cx="12" cy="12" r="9"/></>,
    favorite:<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9L12 3Z"/>,
    history:<><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2M5 5 3 8"/></>,
    profile:<><path d="M6 4h12v16H6z"/><circle cx="12" cy="9" r="2"/><path d="M9 16c.8-2 5.2-2 6 0"/></>,
    creator:<><path d="M12 3 13.8 8.2 19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z"/><path d="m18 16 .7 2.3L21 19l-2.3.7L18 22l-.7-2.3L15 19l2.3-.7L18 16Z"/></>,
  };
  return <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[type]}</svg>;
}

export default function CommunityPage() {
  const [headerState,setHeaderState]=useState<"top"|"compact">("top");
  const [channelState,setChannelState]=useState<"collapsed"|"expanded">("collapsed");
  const [activeChannel,setActiveChannel]=useState("hot");
  const [searchOpen,setSearchOpen]=useState(false); const [submitOpen,setSubmitOpen]=useState(false); const [query,setQuery]=useState("");
  const previousScroll=useRef(0); const [scrollDirection,setScrollDirection]=useState<"up"|"down">("down");
  useEffect(()=>{let scheduled=false;const update=()=>{scheduled=false;const y=globalThis.scrollY;setScrollDirection(y>=previousScroll.current?"down":"up");previousScroll.current=y;setHeaderState(current=>{if(y<=32){setChannelState("collapsed");return "top";}if(y>96)return "compact";return current;});};const onScroll=()=>{if(!scheduled){scheduled=true;globalThis.requestAnimationFrame(update);}};const initialFrame=globalThis.requestAnimationFrame(()=>{const initial=new URLSearchParams(globalThis.location.search).get("channel");if(initial)setActiveChannel(initial);update();});globalThis.addEventListener("scroll",onScroll,{passive:true});return()=>{globalThis.cancelAnimationFrame(initialFrame);globalThis.removeEventListener("scroll",onScroll);};},[]);
  useEffect(()=>{function close(event:KeyboardEvent){if(event.key==="Escape"){setChannelState("collapsed");setSearchOpen(false);setSubmitOpen(false);}}document.addEventListener("keydown",close);return()=>document.removeEventListener("keydown",close);},[]);
  function chooseChannel(value:string){setActiveChannel(value);const url=new URL(globalThis.location.href);url.searchParams.set("channel",value);globalThis.history.replaceState({},"",url);}
  function submitSearch(event:FormEvent){event.preventDefault();if(query.trim())setSearchOpen(true);}
  const filtered=activeChannel==="hot"||activeChannel==="following"?content:content.filter(item=>item.id.startsWith(activeChannel)); const feed=(filtered.length?filtered:content).slice(0,10);
  const activeChannelLabel=activeChannel==="hot"?"热门":activeChannel==="following"?"动态":channels.find(([value])=>value===activeChannel)?.[1]??activeChannel;
  return <main className="communityPage communityV2" id="main-content" data-scroll-direction={scrollDirection}>
    <section className="brandBanner" aria-label="HAHA 品牌专题"><div><p>HAHA CULTURE COMMUNITY</p><h1>让手艺继续发生，<br/><em>让文化被今天看见。</em></h1><span>人物 · 地方 · 材料 · 日常</span></div><div className="bannerArtwork" aria-hidden="true"><i>非</i><i>遗</i><i>今</i></div></section>
    <div className={`communityNavSystem ${headerState} ${channelState}`}>
      <header className="globalHeader"><div className="globalHeaderInner"><Link className="communityBrand" href="/"><span>HA</span>HA</Link><nav className="globalPrimary" aria-label="全局导航"><Link aria-current="page" href="/">首页</Link><a href="#recommended">非遗影像</a><a href="#regions">非遗礼遇</a><a href="#regions">文化地图</a><a href="#creator-tools">AI 学习</a></nav>
        <form className="globalSearch" role="search" onSubmit={submitSearch}><input value={query} onChange={event=>setQuery(event.target.value)} onFocus={()=>setSearchOpen(true)} placeholder="搜一搜：竹编、蓝染、手艺人的一天" aria-label="搜索全站内容" aria-controls="search-suggestions"/><button type="submit" aria-label="搜索">⌕</button>{searchOpen&&<div className="searchPanel" id="search-suggestions"><div><b>热门搜索</b>{["年轻传承人","蓝染","景德镇"].map(term=><button type="button" onClick={()=>setQuery(term)} key={term}>{term}</button>)}</div><div><b>可搜索</b><span>视频　非遗项目　传承人　工艺　地区　专题　活动</span></div></div>}</form>
        <nav className="userActions" aria-label="用户功能"><button type="button" aria-label="文化会员"><ActionIcon type="member"/><span>文化会员</span></button><button type="button" aria-label="消息"><ActionIcon type="message"/><span>消息</span></button><button type="button" aria-label="动态"><ActionIcon type="activity"/><span>动态</span></button><button type="button" aria-label="收藏"><ActionIcon type="favorite"/><span>收藏</span></button><button type="button" aria-label="观看历史"><ActionIcon type="history"/><span>历史</span></button><a href="#regions" aria-label="文化档案"><ActionIcon type="profile"/><span>文化档案</span></a><Link href="/creator" aria-label="创作中心"><ActionIcon type="creator"/><span>创作中心</span></Link></nav>
        <div className="submitMenu"><button className="submitPrimary" type="button" onClick={()=>setSubmitOpen(value=>!value)} aria-expanded={submitOpen} aria-controls="submit-options">＋ 投稿</button>{submitOpen&&<div id="submit-options" className="submitOptions">{["视频投稿","图文投稿","项目资料投稿","活动投稿"].map(item=><button type="button" key={item}>{item}</button>)}</div>}</div><button className="avatarButton" type="button" aria-label="登录或打开用户菜单">登录</button></div></header>
      <nav className="channelNavigation" aria-label="内容频道"><div className="channelCompact"><button className={activeChannel==="following"?"active special":"special"} type="button" onClick={()=>chooseChannel("following")}>◎ 动态</button><button className={activeChannel==="hot"?"active special":"special"} type="button" onClick={()=>chooseChannel("hot")}>🔥 热门</button><i aria-hidden="true"/>{channels.map(([value,label])=><button className={activeChannel===value?"active":""} type="button" key={value} onClick={()=>chooseChannel(value)} aria-current={activeChannel===value?"page":undefined}>{label}</button>)}<i aria-hidden="true"/><a href="#topics">专题</a><a href="#creator-tools">活动</a><a href="#regions">文化地图</a><a href="#creator-tools">课堂</a><button className="channelToggle" type="button" onClick={()=>setChannelState(value=>value==="expanded"?"collapsed":"expanded")} aria-expanded={channelState==="expanded"} aria-controls="expanded-channels">{channelState==="expanded"?"收起 ▲":"更多 ▼"}</button></div><div className="expandedChannels" id="expanded-channels" aria-hidden={channelState!=="expanded"}>{expandedChannels.map(([group,items])=><div key={group}><b>{group}</b><div>{items.map(item=><button type="button" key={item} onClick={()=>{chooseChannel(item);setChannelState("collapsed");}}>{item}</button>)}</div></div>)}</div></nav>
    </div>
    <div className="communityContent">
      <section className="heroRecommendation" aria-labelledby="hero-title"><div className="largeFeature"><div className="featureVisual red"><span>绣</span><small>今日重点 · 贵州</small><b>02:18</b></div><div className="featureCopy"><span>人物故事 · 编辑精选</span><h2 id="hero-title">一根线，怎样绣出远方？</h2><p>跟随一双手，看纹样如何连接山川、生活与记忆。</p><div><b>阿锦的绣房</b><span>8.6万播放 · 3,214互动</span></div></div></div><div className="heroRecommendations">{content.slice(1,5).map(item=><ContentCard item={item} key={item.id}/>)}</div></section>
      <section className="feedSection" id="recommended"><SectionHeading eyebrow="FOR YOU" title={activeChannel==="hot"?"推荐内容":`正在浏览 · ${activeChannelLabel}`} action="换一换 ↻"/><div className="contentGrid">{feed.map(item=><ContentCard item={item} key={item.id}/>)}</div></section>
      <section className="trendingSection"><SectionHeading eyebrow="TRENDING NOW" title="正在热门"/><div className="trendTabs" role="tablist"><button className="active" type="button" role="tab">综合</button><button type="button" role="tab">视频</button><button type="button" role="tab">项目</button><button type="button" role="tab">传承人</button></div><div className="trendingLayout"><div className="trendCards">{content.slice(4,7).map(item=><ContentCard item={item} key={item.id}/>)}</div><ol className="rankingList">{content.slice(0,6).map((item,index)=><li key={item.id}><b>{String(index+1).padStart(2,"0")}</b><div><h3>{item.title}</h3><p>{item.category} · {item.views}播放</p></div></li>)}</ol></div></section>
      {["刺绣","陶瓷","竹编","戏曲"].map((category,sectionIndex)=><section className="categorySection" key={category}><SectionHeading title={category}/><div className="contentGrid categoryGrid">{[...content.slice(sectionIndex,sectionIndex+5),...content].slice(0,5).map((item,index)=><ContentCard item={{...item,id:`${category}-${index}`,category:index===0?category:item.category}} key={`${category}-${index}`}/>)}</div></section>)}
      <section className="regionDiscovery" id="regions"><SectionHeading eyebrow="EXPLORE BY PLACE" title="按地区发现非遗" action="进入文化地图 →"/><div className="regionGrid">{regions.map(([name,crafts,count],index)=><button type="button" className={`regionCard regionTone${index%4}`} key={name}><span>{String(index+1).padStart(2,"0")}</span><h3>{name}</h3><p>{crafts}</p><b>{count} 个项目　→</b></button>)}</div></section>
      <section className="topicSection" id="topics"><SectionHeading eyebrow="CURATED BY HAHA" title="专题策展"/><div className="topicGrid">{topics.map(([title,copy,mark],index)=><article className={`topicCard topicTone${index}`} key={title}><span>{mark}</span><div><small>HAHA 专题 · 0{index+1}</small><h3>{title}</h3><p>{copy}</p><button type="button">进入专题 →</button></div></article>)}</div></section>
      <section className="creatorTools" id="creator-tools"><SectionHeading eyebrow="HAHA CREATOR" title="创作者工具"/><div className="toolGrid"><button type="button"><i>↑</i><div><h3>视频投稿</h3><p>提交影像、图文或项目资料</p></div></button><Link className="featuredTool" href="/creator"><i>✦</i><div><h3>AI 图文脚本</h3><p>从想法生成策划、脚本、分镜与发布建议</p></div></Link><button type="button"><i>⌘</i><div><h3>智能对话工作台</h3><p>通过对话持续推进创作</p></div></button><button type="button"><i>库</i><div><h3>文化资料库</h3><p>查找事实、来源与创作方法</p></div></button><Link href="/creator"><i>↗</i><div><h3>创作中心</h3><p>管理项目、版本和审核状态</p></div></Link></div></section>
    </div>
    <footer className="communityFooterV2"><div><Link className="communityBrand" href="/"><span>HA</span>HA</Link><p>非遗知识与智能创作基础设施</p></div><nav><a href="#recommended">内容发现</a><a href="#regions">文化地图</a><Link href="/creator">创作中心</Link></nav><span>© 2026 HAHA CULTURE MEDIA</span></footer>
  </main>;
}
