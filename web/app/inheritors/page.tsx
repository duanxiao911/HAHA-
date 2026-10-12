"use client";

import { EntityCard } from "@/components/community/EntityCard";
import { ProductFrame } from "@/components/community/ProductFrame";
import { StateNotice } from "@/components/community/StateNotice";
import { useCommunity } from "@/lib/community";

export default function InheritorsPage() {
  const { snapshot } = useCommunity();
  const inheritors = snapshot.people.filter((person) => person.role === "inheritor");

  return (
    <ProductFrame mainClassName="productDiscoveryPage">
      <header className="productPageHero">
        <span className="productDemoKicker">本地虚构人物 · 功能演示</span>
        <h1>传承人与手艺人</h1>
        <p>从人物进入项目、地区和作品。当前人物均为本地虚构数据，不应作为真实传承人资料引用。</p>
      </header>
      {inheritors.length ? (
        <section className="productEntityGrid" aria-label="演示传承人列表">
          {inheritors.map((person) => {
            const region = snapshot.regions.find((item) => item.id === person.regionId);
            return (
              <EntityCard
                kind="profile"
                id={person.id}
                href={`/inheritors/${person.id}`}
                title={person.displayName}
                summary={person.bio}
                eyebrow="认证演示人物"
                meta={[region?.name, `${person.projectIds.length} 个关联项目`].filter(Boolean).join(" · ")}
                mark={person.avatar?.placeholder?.mark}
                verificationStatus={person.verified ? "inheritor_confirmed" : "pending"}
                key={person.id}
              />
            );
          })}
        </section>
      ) : (
        <StateNotice kind="empty" title="没有人物条目" description="本地演示资料暂未建立传承人记录。" actionLabel="浏览项目" actionHref="/heritage-projects" />
      )}
    </ProductFrame>
  );
}
