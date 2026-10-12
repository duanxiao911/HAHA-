"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { ContentTile } from "@/components/community/ContentTile";
import { EntityCard } from "@/components/community/EntityCard";
import { ProductFrame } from "@/components/community/ProductFrame";
import { StateNotice } from "@/components/community/StateNotice";
import { TrustBadge } from "@/components/community/TrustBadge";
import { useCommunity } from "@/lib/community";

const levelLabels = {
  national: "国家级",
  provincial: "省级",
  municipal: "市级",
  community: "社区记录",
} as const;

export default function HeritageProjectDetailPage() {
  const params = useParams<{ id: string }>();
  const { snapshot } = useCommunity();
  const routeId = decodeURIComponent(params.id);
  const project = snapshot.projects.find((item) => item.id === routeId || item.slug === routeId);

  if (!project) {
    return (
      <ProductFrame>
        <StateNotice
          kind="empty"
          title="没有找到这个项目"
          description="项目可能已被移除，或当前本地演示资料中没有对应条目。"
          actionLabel="返回项目库"
          actionHref="/heritage-projects"
        />
      </ProductFrame>
    );
  }

  const regions = snapshot.regions.filter((region) => project.regionIds.includes(region.id));
  const people = snapshot.people.filter((person) => project.inheritorIds.includes(person.id));
  const sources = snapshot.sources.filter((source) => project.sourceIds.includes(source.id));
  const contents = snapshot.contents.filter((content) => content.projectIds.includes(project.id));

  return (
    <ProductFrame mainClassName="productDetailPage">
      <nav className="productBreadcrumb" aria-label="面包屑">
        <Link href="/heritage-projects">非遗项目库</Link><span aria-hidden="true">/</span><span>{project.name}</span>
      </nav>

      <header className="productDetailHero">
        <div className="productDetailMark" aria-hidden="true">{project.name.slice(0, 1)}</div>
        <div>
          <span className="productDemoKicker">本地演示项目 · {levelLabels[project.level]} · {project.category}</span>
          <h1>{project.name}</h1>
          <p>{project.summary}</p>
          <TrustBadge status={project.verificationStatus} sourceCount={sources.length} />
        </div>
      </header>

      <div className="productDetailColumns">
        <section className="productDetailSection">
          <span className="productSectionEyebrow">MATERIALS</span>
          <h2>材料</h2>
          <ul className="productChipList">
            {project.materials.map((material) => <li key={material}>{material}</li>)}
          </ul>
        </section>
        <section className="productDetailSection">
          <span className="productSectionEyebrow">TECHNIQUES</span>
          <h2>工艺过程</h2>
          <ol className="productProcessList">
            {project.techniques.map((technique, index) => (
              <li key={technique}><span>{String(index + 1).padStart(2, "0")}</span><b>{technique}</b></li>
            ))}
          </ol>
        </section>
      </div>

      <section className="productDetailSection">
        <span className="productSectionEyebrow">SOURCES</span>
        <h2>可信来源</h2>
        <p className="productSectionIntro">来源均为本地演示索引；对外发布前仍需在服务端逐条复核原文、访问时间与适用事实。</p>
        <div className="productSourceList">
          {sources.map((source) => (
            <article key={source.id}>
              <div><b>{source.title}</b><span>{source.publisher} · {source.sourceLevel}</span></div>
              <p>{source.note}</p>
              {source.url ? <a href={source.url} target="_blank" rel="noreferrer">查看来源网站 ↗</a> : <span>本地资料索引</span>}
            </article>
          ))}
        </div>
      </section>

      {regions.length ? (
        <section className="productDetailSection">
          <span className="productSectionEyebrow">PLACES</span><h2>关联地区</h2>
          <div className="productEntityGrid">
            {regions.map((region) => (
              <EntityCard kind="region" id={region.id} title={region.name} summary={region.summary} meta={region.featuredCrafts.join(" · ")} key={region.id} />
            ))}
          </div>
        </section>
      ) : null}

      {people.length ? (
        <section className="productDetailSection">
          <span className="productSectionEyebrow">PEOPLE</span><h2>关联人物</h2>
          <div className="productEntityGrid">
            {people.map((person) => (
              <EntityCard kind="profile" id={person.id} href={`/inheritors/${person.id}`} title={person.displayName} summary={person.bio} meta={person.demoLabel} verificationStatus={person.verified ? "inheritor_confirmed" : "pending"} key={person.id} />
            ))}
          </div>
        </section>
      ) : null}

      {contents.length ? (
        <section className="productDetailSection">
          <span className="productSectionEyebrow">STORIES</span><h2>关联内容</h2>
          <div className="productContentGrid">
            {contents.map((content) => <ContentTile content={content} compact key={content.id} />)}
          </div>
        </section>
      ) : null}
    </ProductFrame>
  );
}
