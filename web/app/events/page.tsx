"use client";

import Link from "next/link";

import { ContentTile } from "@/components/community/ContentTile";
import { ProductFrame } from "@/components/community/ProductFrame";
import { useCommunity } from "@/lib/community";

const eventDates = ["2026-10-18", "2026-10-25", "2026-11-01", "2026-11-08"];

export default function EventsPage() {
  const { snapshot } = useCommunity();
  const eventRegions = snapshot.regions.slice(0, 4);

  return (
    <ProductFrame mainClassName="productDiscoveryPage">
      <header className="productPageHero">
        <span className="productDemoKicker">内部展示日程 · 不接受真实报名</span>
        <h1>非遗活动</h1>
        <p>以下活动由现有地区和内容组合生成，用来验收活动发现与跳转流程，不代表真实机构活动。</p>
      </header>

      <section className="productEventList" aria-label="本地演示活动">
        {eventRegions.map((region, index) => {
          const content = snapshot.contents.find((item) => item.regionId === region.id) ?? snapshot.contents[index];
          const project = snapshot.projects.find((item) => item.regionIds.includes(region.id));
          const date = eventDates[index] ?? eventDates[0];
          return (
            <article className="productEventCard" key={region.id}>
              <div className="productEventDate"><time dateTime={date}>{date.slice(5).replace("-", ".")}</time><span>内部演示</span></div>
              <div className="productEventCopy">
                <span className="productSectionEyebrow">{region.name} · 线上策展导览</span>
                <h2>{region.featuredCrafts[0]}材料与工艺观察会</h2>
                <p>以“{content?.title ?? region.summary}”为观看入口，串联地区、项目与人物档案。</p>
                <div className="productEventActions">
                  {content ? <Link href={`/content/${content.id}`}>观看导览内容</Link> : null}
                  {project ? <Link href={`/heritage-projects/${project.id}`}>查看关联项目</Link> : null}
                  <Link href={`/map?region=${region.id}`}>探索{region.name}</Link>
                </div>
              </div>
              {content ? <ContentTile content={content} compact /> : null}
            </article>
          );
        })}
      </section>
    </ProductFrame>
  );
}
