"use client";

import { EntityCard } from "@/components/community/EntityCard";
import { ProductFrame } from "@/components/community/ProductFrame";
import { StateNotice } from "@/components/community/StateNotice";
import { useCommunity } from "@/lib/community";

const levelLabels = {
  national: "国家级",
  provincial: "省级",
  municipal: "市级",
  community: "社区记录",
} as const;

export default function HeritageProjectsPage() {
  const { snapshot } = useCommunity();

  return (
    <ProductFrame mainClassName="productDiscoveryPage">
      <header className="productPageHero">
        <span className="productDemoKicker">本地演示数据 · 项目索引</span>
        <h1>非遗项目库</h1>
        <p>从项目进入材料、工艺、人物、地区与可信来源。这里的条目只用于内部演示，不代表正式机构名录。</p>
        <div className="productPageStats" aria-label="项目库统计">
          <span><b>{snapshot.projects.length}</b> 个演示项目</span>
          <span><b>{snapshot.projects.filter((project) => project.verificationStatus === "verified").length}</b> 个已建立来源关联</span>
        </div>
      </header>

      {snapshot.projects.length ? (
        <section className="productEntityGrid" aria-label="非遗项目列表">
          {snapshot.projects.map((project) => {
            const regionNames = snapshot.regions
              .filter((region) => project.regionIds.includes(region.id))
              .map((region) => region.name)
              .join(" · ");
            return (
              <EntityCard
                kind="project"
                id={project.id}
                title={project.name}
                summary={project.summary}
                eyebrow={`${levelLabels[project.level]} · ${project.category}`}
                meta={[regionNames, project.materials.slice(0, 3).join(" / ")].filter(Boolean).join(" · ")}
                mark={project.name.slice(0, 1)}
                verificationStatus={project.verificationStatus}
                key={project.id}
              />
            );
          })}
        </section>
      ) : (
        <StateNotice
          kind="empty"
          title="当前没有项目条目"
          description="本地演示资料中尚未建立非遗项目，可以先从内容发现页继续浏览。"
          actionLabel="返回首页"
          actionHref="/"
        />
      )}
    </ProductFrame>
  );
}
