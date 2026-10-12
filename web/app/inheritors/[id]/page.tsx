"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { ContentTile } from "@/components/community/ContentTile";
import { EntityCard } from "@/components/community/EntityCard";
import { ProductFrame } from "@/components/community/ProductFrame";
import { StateNotice } from "@/components/community/StateNotice";
import { useCommunity } from "@/lib/community";

const roleLabels = {
  creator: "创作者",
  inheritor: "传承人",
  institution: "文化机构",
  expert: "专家",
} as const;

export default function InheritorDetailPage() {
  const params = useParams<{ id: string }>();
  const { snapshot, actions } = useCommunity();
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  const routeId = decodeURIComponent(params.id);
  const person = snapshot.people.find((item) => item.id === routeId || item.slug === routeId);

  if (!person) {
    return (
      <ProductFrame>
        <StateNotice kind="empty" title="没有找到这个人物" description="人物可能已被移除，或当前本地演示资料中没有对应条目。" actionLabel="返回人物列表" actionHref="/inheritors" />
      </ProductFrame>
    );
  }

  const personId = person.id;
  const followed = snapshot.followingPersonIds.includes(personId);
  const region = snapshot.regions.find((item) => item.id === person.regionId);
  const projects = snapshot.projects.filter((project) => person.projectIds.includes(project.id) || project.inheritorIds.includes(person.id));
  const contents = snapshot.contents.filter((content) => content.creatorId === person.id || content.personIds.includes(person.id));

  async function toggleFollow() {
    setBusy(true);
    setActionError("");
    try {
      await actions.setPersonFollow(personId, !followed);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "关注状态保存失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <ProductFrame mainClassName="productDetailPage">
      <nav className="productBreadcrumb" aria-label="面包屑"><Link href="/inheritors">传承人与手艺人</Link><span aria-hidden="true">/</span><span>{person.displayName}</span></nav>
      <header className="productProfileHero">
        <div className={`productProfileAvatar productTone--${person.avatar?.placeholder?.tone ?? "red"}`} aria-hidden="true">
          {person.avatar?.placeholder?.mark ?? person.displayName.slice(0, 1)}
        </div>
        <div>
          <span className="productDemoKicker">{person.demoLabel}</span>
          <h1>{person.displayName}</h1>
          <p>{person.bio}</p>
          <div className="productProfileMeta">
            <span>{roleLabels[person.role]}</span>
            {person.verified ? <span>✓ 本地演示认证</span> : <span>待核验</span>}
            {region ? <Link href={`/map?region=${region.id}`}>{region.name}</Link> : null}
          </div>
        </div>
        <button type="button" aria-pressed={followed} disabled={busy} onClick={toggleFollow}>
          {busy ? "保存中…" : followed ? "已关注" : "＋ 关注"}
        </button>
      </header>
      {actionError ? <StateNotice kind="error" compact title="关注状态没有保存" description={actionError} actionLabel="重试" onAction={toggleFollow} /> : null}

      {projects.length ? (
        <section className="productDetailSection">
          <span className="productSectionEyebrow">PROJECTS</span><h2>关联项目</h2>
          <div className="productEntityGrid">
            {projects.map((project) => <EntityCard kind="project" id={project.id} title={project.name} summary={project.summary} meta={`${project.category} · ${project.materials.join(" / ")}`} verificationStatus={project.verificationStatus} key={project.id} />)}
          </div>
        </section>
      ) : null}

      {contents.length ? (
        <section className="productDetailSection">
          <span className="productSectionEyebrow">STORIES</span><h2>相关作品与记录</h2>
          <div className="productContentGrid">
            {contents.map((content) => <ContentTile content={content} key={content.id} />)}
          </div>
        </section>
      ) : (
        <StateNotice kind="empty" title="还没有关联内容" description="该人物目前只有本地演示档案，没有关联作品。" actionLabel="浏览内容" actionHref="/search" />
      )}
    </ProductFrame>
  );
}
