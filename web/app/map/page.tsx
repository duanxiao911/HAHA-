"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";

import { ContentTile } from "@/components/community/ContentTile";
import { EntityCard } from "@/components/community/EntityCard";
import { ProductFrame } from "@/components/community/ProductFrame";
import { useCommunity } from "@/lib/community";

function CultureMapContent() {
  const { snapshot } = useCommunity();
  const searchParams = useSearchParams();
  const [activeRegionId, setActiveRegionId] = useState("");
  const requestedRegionId = searchParams.get("region");
  const requestedRegion = snapshot.regions.find((region) => region.id === requestedRegionId || region.slug === requestedRegionId);
  const activeRegion = snapshot.regions.find((region) => region.id === activeRegionId) ?? requestedRegion ?? snapshot.regions[0];
  const projects = activeRegion ? snapshot.projects.filter((project) => project.regionIds.includes(activeRegion.id)) : [];
  const people = activeRegion ? snapshot.people.filter((person) => person.regionId === activeRegion.id) : [];
  const contents = activeRegion ? snapshot.contents.filter((content) => content.regionId === activeRegion.id) : [];

  return (
    <ProductFrame mainClassName="productDiscoveryPage">
      <header className="productPageHero">
        <span className="productDemoKicker">本地演示地区档案 · 非真实地理服务</span>
        <h1>文化地图</h1>
        <p>按地区查看项目、人物和内容之间的联系。当前不使用定位，也不表示完整项目数量。</p>
      </header>

      <nav className="productRegionFilters" aria-label="选择地区">
        {snapshot.regions.map((region) => (
          <button
            type="button"
            aria-pressed={activeRegion?.id === region.id}
            onClick={() => setActiveRegionId(region.id)}
            key={region.id}
          >
            {region.name}<small>{region.featuredCrafts.slice(0, 2).join(" · ")}</small>
          </button>
        ))}
      </nav>

      {activeRegion ? (
        <>
          <section className="productMapSpotlight">
            <div className="productMapVisual" aria-hidden="true"><span>{activeRegion.name.slice(0, 1)}</span><i>{String(activeRegion.projectCount).padStart(3, "0")}</i></div>
            <div><span className="productSectionEyebrow">{activeRegion.province}</span><h2>{activeRegion.name}</h2><p>{activeRegion.summary}</p><ul className="productChipList">{activeRegion.featuredCrafts.map((craft) => <li key={craft}>{craft}</li>)}</ul><small>页面中的 {activeRegion.projectCount} 为演示统计，正式上线前需接入可信数据源。</small></div>
          </section>

          <section className="productDetailSection">
            <span className="productSectionEyebrow">PROJECTS</span><h2>{activeRegion.name}关联项目</h2>
            {projects.length ? <div className="productEntityGrid">{projects.map((project) => <EntityCard kind="project" id={project.id} title={project.name} summary={project.summary} meta={project.techniques.join(" · ")} verificationStatus={project.verificationStatus} key={project.id} />)}</div> : <p className="productSectionIntro">演示资料中暂未建立该地区的项目条目。</p>}
          </section>

          {people.length ? <section className="productDetailSection"><span className="productSectionEyebrow">PEOPLE</span><h2>人物</h2><div className="productEntityGrid">{people.map((person) => <EntityCard kind="profile" id={person.id} href={`/inheritors/${person.id}`} title={person.displayName} summary={person.bio} verificationStatus={person.verified ? "inheritor_confirmed" : "pending"} key={person.id} />)}</div></section> : null}
          {contents.length ? <section className="productDetailSection"><span className="productSectionEyebrow">STORIES</span><h2>来自这里的内容</h2><div className="productContentGrid">{contents.map((content) => <ContentTile content={content} compact key={content.id} />)}</div></section> : null}
        </>
      ) : null}
    </ProductFrame>
  );
}

export default function CultureMapPage() {
  return (
    <Suspense fallback={<ProductFrame><div className="productStateNotice productStateNotice--loading" role="status" aria-busy="true"><span className="productStateIcon" aria-hidden="true">…</span><div><h2>正在打开文化地图</h2><p>正在恢复地区选择与本地演示资料。</p></div></div></ProductFrame>}>
      <CultureMapContent />
    </Suspense>
  );
}
