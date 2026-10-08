import Link from "next/link";

const stories = [
  { mark: "绣", eyebrow: "人物故事 · 贵州", title: "一根线，怎样绣出远方？", copy: "从一双手的重复练习开始，看纹样如何成为记忆的语言。", author: "阿锦的绣房", meta: "02:18 · 8.6万观看", tone: "red" },
  { mark: "陶", eyebrow: "工序观察 · 景德镇", title: "泥土被火记住的声音", copy: "拉坯、晾晒、入窑，每一步都在和时间协商。", author: "泥与火工作室", meta: "01:32 · 5.4万观看", tone: "green" },
  { mark: "纹", eyebrow: "文化观察 · 云南", title: "一朵纹样，走过多少地方？", copy: "把一个常见图案拆开看，它会连接祝愿、自然与日常生活。", author: "纹样观察所", meta: "00:54 · 3.1万观看", tone: "blue" },
  { mark: "作", eyebrow: "手艺日常 · 浙江", title: "工作台上的安静时刻", copy: "镜头不急着解释，只记录一件作品慢慢成形。", author: "青年手艺档案", meta: "01:07 · 2.8万观看", tone: "gold" },
];

const regions = ["贵州苗绣", "景德镇陶瓷", "云南扎染", "福建木偶戏", "浙江竹编"];

export default function CommunityPage() {
  return <main className="communityPage">
    <header className="communityHeader">
      <Link className="communityBrand" href="/"><span>HA</span>HA <small>非遗影像馆</small></Link>
      <nav aria-label="社区导航"><a href="#featured">推荐</a><a href="#discover">发现</a><a href="#regions">文化地图</a></nav>
      <div className="communityActions"><button type="button" aria-label="搜索">⌕</button><Link href="/creator">进入 AI 创作台 <span>↗</span></Link></div>
    </header>

    <section className="communityHero" id="featured">
      <div className="heroCopy"><p className="kicker">HAHA CURATED · 今日精选</p><h1>让正在发生的手艺，<br/><em>被今天的人看见。</em></h1><p>从真实的人、材料与地方出发，观看非遗如何继续活在日常里。</p><div className="heroButtons"><a href="#discover">开始观看 <span>↓</span></a><Link href="/creator">用 AI 讲述我的文化故事</Link></div><div className="heroFacts"><span><b>32</b> 个地方档案</span><span><b>126</b> 位文化记录者</span><span><b>480+</b> 条可信内容</span></div></div>
      <article className="heroFeature"><div className="heroVisual"><span>剪</span><i>FEATURED STORY · 01</i><b>02:18</b></div><div className="heroFeatureCopy"><small>剪纸 · 人物故事</small><h2>一把剪刀，<br/>怎样留下一个地方？</h2><p>跟随一位剪纸艺人的手，看红纸上的线条如何连接节气、生活与记忆。</p><div><span>中国剪纸档案</span><button type="button" aria-label="播放精选故事">▶</button></div></div></article>
    </section>

    <section className="storySection" id="discover"><div className="sectionTitle"><div><p>EDITOR&apos;S PICK</p><h2>值得停下来看的故事</h2></div><a href="#regions">查看全部内容 →</a></div><div className="storyGrid">{stories.map((story,index)=><article className="storyCard" key={story.title}><div className={`storyCover ${story.tone}`}><span>{story.mark}</span><small>0{index+1}</small><button type="button" aria-label={`播放${story.title}`}>▶</button></div><div className="storyText"><small>{story.eyebrow}</small><h3>{story.title}</h3><p>{story.copy}</p><div><span>{story.author}</span><span>{story.meta}</span></div></div></article>)}</div></section>

    <section className="regionSection" id="regions"><div><p>EXPLORE BY PLACE</p><h2>沿着地方，<br/>找到手艺生长的现场。</h2><span>非遗不是孤立的符号。选择一个地方，认识那里的材料、生活与人。</span></div><div className="regionMap"><i>西南</i><b>中国文化地图</b><i>东南</i><span>正在持续补充地方档案</span></div><div className="regionList">{regions.map((region,index)=><a href="#featured" key={region}><small>0{index+1}</small><b>{region}</b><span>探索 →</span></a>)}</div></section>

    <section className="creatorBanner"><div><small>HAHA CREATOR</small><h2>你也可以成为文化的记录者。</h2><p>从一个真实的瞬间开始，用知识证据和 AI 创作工具完成可拍、可审、可发布的内容。</p></div><Link href="/creator">打开创作工作台 <span>↗</span></Link></section>
    <footer className="communityFooter"><Link className="communityBrand" href="/"><span>HA</span>HA</Link><p>非遗知识与智能创作基础设施</p><span>© 2026 HAHA CULTURE MEDIA</span></footer>
  </main>;
}
