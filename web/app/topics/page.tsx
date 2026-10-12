"use client";

import Link from "next/link";

import { ContentTile } from "@/components/community/ContentTile";
import { EntityCard } from "@/components/community/EntityCard";
import { ProductFrame } from "@/components/community/ProductFrame";
import { useCommunity } from "@/lib/community";

export default function TopicsPage() {
  const { snapshot } = useCommunity();
  const dyeingContents = snapshot.contents.filter((content) => content.categoryId === "dyeing");
  const materialContents = snapshot.contents.filter((content) => content.tags.some((tag) => ["材料", "制瓷", "竹编"].includes(tag)));
  const inheritors = snapshot.people.filter((person) => person.role === "inheritor");
  const yunnan = snapshot.regions.find((region) => region.slug === "yunnan");

  return (
    <ProductFrame mainClassName="productDiscoveryPage">
      <header className="productPageHero">
        <span className="productDemoKicker">HAHA 本地演示策展</span>
        <h1>专题策展</h1>
        <p>把内容、项目、人物和地区组织成可继续探索的路径；所有入口均进入真实存在的本地演示页面。</p>
      </header>

      <section className="productTopicFeature">
        <div><span className="productSectionEyebrow">TOPIC 01</span><h2>中国蓝染地图</h2><p>从植物、布料、扎结与地方生活出发，理解蓝色如何在不同地区形成不同纹样。</p><Link href="/search?q=蓝染">查看全部蓝染结果 →</Link></div>
        {yunnan ? <EntityCard kind="region" id={yunnan.id} title={yunnan.name} summary={yunnan.summary} meta={yunnan.featuredCrafts.join(" · ")} /> : null}
        <div className="productContentGrid">{dyeingContents.map((content) => <ContentTile content={content} compact key={content.id} />)}</div>
      </section>

      <section className="productTopicFeature">
        <div><span className="productSectionEyebrow">TOPIC 02</span><h2>手艺背后的人</h2><p>从人物档案进入项目与作品，关注当代生活中持续发生的学习、实践和传播。</p><Link href="/inheritors">浏览人物列表 →</Link></div>
        <div className="productEntityGrid">{inheritors.map((person) => <EntityCard kind="profile" id={person.id} href={`/inheritors/${person.id}`} title={person.displayName} summary={person.bio} mark={person.avatar?.placeholder?.mark} verificationStatus={person.verified ? "inheritor_confirmed" : "pending"} key={person.id} />)}</div>
      </section>

      <section className="productTopicFeature">
        <div><span className="productSectionEyebrow">TOPIC 03</span><h2>从材料到器物</h2><p>将镜头放在材料准备、动作和等待上，而不是只展示最后的成品。</p><Link href="/search?q=材料">查找材料相关内容 →</Link></div>
        <div className="productContentGrid">{materialContents.map((content) => <ContentTile content={content} compact key={content.id} />)}</div>
      </section>
    </ProductFrame>
  );
}
