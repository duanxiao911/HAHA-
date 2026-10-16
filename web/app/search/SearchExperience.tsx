"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { ConfirmDialog } from "@/components/community/ConfirmDialog";
import { ContentTile } from "@/components/community/ContentTile";
import { EntityCard } from "@/components/community/EntityCard";
import { ProductFrame } from "@/components/community/ProductFrame";
import { StateNotice } from "@/components/community/StateNotice";
import {
  COMMUNITY_PAGE_LIMIT_MAX,
  type CommunitySearchHit,
  type SearchEntityKind,
  type SearchQuery,
  useCommunity,
} from "@/lib/community";

const scopes: { value: SearchQuery["scope"]; label: string }[] = [
  { value: "all", label: "综合" },
  { value: "content", label: "视频与图文" },
  { value: "project", label: "非遗项目" },
  { value: "person", label: "人物" },
  { value: "region", label: "地区" },
];

const sorts: { value: NonNullable<SearchQuery["sort"]>; label: string }[] = [
  { value: "relevance", label: "综合相关度" },
  { value: "latest", label: "最新" },
  { value: "popular", label: "热门" },
  { value: "verified", label: "核验等级" },
];

function normalizeScope(value: string): NonNullable<SearchQuery["scope"]> {
  return scopes.some((scope) => scope.value === value)
    ? value as NonNullable<SearchQuery["scope"]>
    : "all";
}

function normalizeSort(value: string): NonNullable<SearchQuery["sort"]> {
  return sorts.some((sort) => sort.value === value)
    ? value as NonNullable<SearchQuery["sort"]>
    : "relevance";
}

function HitCard({ hit }: { hit: CommunitySearchHit }) {
  const { snapshot } = useCommunity();
  if (hit.kind === "content") {
    const content = snapshot.contents.find((item) => item.id === hit.id);
    return content ? <ContentTile content={content} compact /> : null;
  }

  const kind = hit.kind === "person" ? "profile" : hit.kind;
  return (
    <EntityCard
      kind={kind}
      id={hit.id}
      title={hit.title}
      summary={hit.summary}
      verificationStatus={hit.verificationStatus}
      href={hit.href}
    />
  );
}

export function SearchExperience({
  initialQuery,
  initialScope,
  initialSort,
}: {
  initialQuery: string;
  initialScope: string;
  initialSort: string;
}) {
  const router = useRouter();
  const { snapshot, actions } = useCommunity();
  const apiMode = snapshot.runtime.mode === "api";
  const [query, setQuery] = useState(initialQuery);
  const [submittedQuery, setSubmittedQuery] = useState(initialQuery.trim());
  const [scope, setScope] = useState<NonNullable<SearchQuery["scope"]>>(
    normalizeScope(initialScope),
  );
  const [sort, setSort] = useState<NonNullable<SearchQuery["sort"]>>(normalizeSort(initialSort));
  const [hits, setHits] = useState<CommunitySearchHit[]>([]);
  const [state, setState] = useState<"idle" | "loading" | "success" | "error">(
    initialQuery.trim() ? "loading" : "idle",
  );
  const [error, setError] = useState("");
  const [clearHistoryOpen, setClearHistoryOpen] = useState(false);
  const [clearingHistory, setClearingHistory] = useState(false);
  const [feedback, setFeedback] = useState("");

  useEffect(() => {
    if (!submittedQuery) return;
    const controller = new AbortController();
    actions.search({
      query: submittedQuery,
      scope,
      sort,
      limit: COMMUNITY_PAGE_LIMIT_MAX,
    }, controller.signal)
      .then((result) => {
        setHits(result.items);
        setState("success");
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return;
        setError(cause instanceof Error ? cause.message : "搜索失败，请重试。");
        setState("error");
      });
    return () => controller.abort();
  }, [actions, scope, sort, submittedQuery]);

  function searchHref(nextQuery: string, nextScope = scope, nextSort = sort) {
    const params = new URLSearchParams();
    if (nextQuery) params.set("q", nextQuery);
    if (nextScope !== "all") params.set("type", nextScope);
    if (nextSort !== "relevance") params.set("sort", nextSort);
    return `/search${params.size ? `?${params.toString()}` : ""}`;
  }

  async function runSearch(event?: FormEvent) {
    event?.preventDefault();
    const clean = query.trim();
    setError("");
    if (clean) setState("loading");
    else {
      setHits([]);
      setState("idle");
    }
    setSubmittedQuery(clean);
    if (clean) await actions.rememberSearchTerm(clean);
    router.push(searchHref(clean), { scroll: false });
  }

  function selectSearchTerm(term: string) {
    setQuery(term);
    setState("loading");
    setSubmittedQuery(term);
    void actions.rememberSearchTerm(term);
    router.push(searchHref(term), { scroll: false });
  }

  async function clearHistory() {
    setClearingHistory(true);
    setFeedback("");
    try {
      await actions.clearSearchHistory();
      setClearHistoryOpen(false);
      setFeedback("最近搜索已清空。");
    } catch (cause) {
      setFeedback(cause instanceof Error ? cause.message : "清空失败，请重试。");
    } finally {
      setClearingHistory(false);
    }
  }

  const groupedCounts = useMemo(() => hits.reduce<Record<SearchEntityKind, number>>(
    (counts, hit) => ({ ...counts, [hit.kind]: counts[hit.kind] + 1 }),
    { content: 0, project: 0, person: 0, region: 0 },
  ), [hits]);

  const suggestedTerms = ["苗绣", "景德镇", "竹编工序", "云南扎染", "年轻传承人"];

  return (
    <ProductFrame initialQuery={submittedQuery} mainClassName="productSearchPage">
      <div className="productDemoStrip" role="note">
        <b>{apiMode ? "内部搜索" : "搜索演示边界"}</b>
        <span>{apiMode ? "搜索通过社区 API 查询服务端目录；当前采用 PostgreSQL 目录检索，尚未引入独立搜索集群。" : "本轮使用本地领域数据完成分类、排序与历史闭环。"}</span>
      </div>
      <header className="productPageHead">
        <div>
          <small>DISCOVER CULTURE</small>
          <h1>搜索与发现</h1>
          <p>从内容进入项目、人物和地区，让一次搜索不只停在标题匹配。</p>
        </div>
      </header>

      <form className="productSearchHero" role="search" onSubmit={runSearch}>
        <label className="productVisuallyHidden" htmlFor="community-search-query">搜索词</label>
        <input
          id="community-search-query"
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="试试：蓝染、景德镇、竹编工序"
          autoFocus
        />
        <button className="productButton" type="submit">搜索</button>
      </form>

      <div className="productFilterBar" aria-label="搜索范围">
        {scopes.map((item) => (
          <button
            type="button"
            className={scope === item.value ? "active" : ""}
            aria-pressed={scope === item.value}
            onClick={() => { const nextScope = item.value ?? "all"; setState(submittedQuery ? "loading" : "idle"); setScope(nextScope); router.replace(searchHref(submittedQuery, nextScope, sort), { scroll: false }); }}
            key={item.value}
          >
            {item.label}
          </button>
        ))}
      </div>

      {submittedQuery ? (
        <div className="productSearchLayout">
          <section aria-live="polite">
            <div className="productSectionHead">
              <div>
                <small>RESULTS</small>
                <h2>“{submittedQuery}”的结果</h2>
                {state === "success" ? <p>共找到 {hits.length} 项{apiMode ? "服务端" : "本地演示"}结果。</p> : null}
              </div>
              <label>
                <span className="productVisuallyHidden">排序方式</span>
                <select value={sort} onChange={(event) => { const nextSort = event.target.value as typeof sort; setState("loading"); setSort(nextSort); router.replace(searchHref(submittedQuery, scope, nextSort), { scroll: false }); }}>
                  {sorts.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
                </select>
              </label>
            </div>
            {state === "loading" ? (
              <StateNotice kind="loading" title="正在整理结果" description="同时匹配内容、项目、人物和地区。" />
            ) : null}
            {state === "error" ? (
              <StateNotice kind="error" title="搜索没有完成" description={error} actionLabel="重试" onAction={() => void runSearch()} />
            ) : null}
            {state === "success" && hits.length === 0 ? (
              <StateNotice
                kind="empty"
                title="没有找到直接匹配项"
                description="请缩短关键词，或从“苗绣”“景德镇”“竹编”等主题继续探索。"
                actionLabel="查看全部内容"
                actionHref="/"
              />
            ) : null}
            {state === "success" && hits.length > 0 ? (
              <div className="productSearchResults">{hits.map((hit) => <HitCard hit={hit} key={`${hit.kind}-${hit.id}`} />)}</div>
            ) : null}
          </section>
          <aside className="productSidePanel">
            <h2>结果结构</h2>
            <ul>
              <li>视频与图文：{groupedCounts.content}</li>
              <li>非遗项目：{groupedCounts.project}</li>
              <li>人物：{groupedCounts.person}</li>
              <li>地区：{groupedCounts.region}</li>
            </ul>
            <h2>最近搜索</h2>
            <div className="productTabs">
              {snapshot.searchHistory.length ? snapshot.searchHistory.map((term) => (
                <button type="button" onClick={() => selectSearchTerm(term)} key={term}>{term}</button>
              )) : <p>搜索过的词会只保存在当前浏览器。</p>}
            </div>
            {snapshot.searchHistory.length ? (
              <button className="productButtonQuiet productDangerText" type="button" onClick={() => setClearHistoryOpen(true)}>清空最近搜索</button>
            ) : null}
          </aside>
        </div>
      ) : (
        <section>
          <div className="productSectionHead"><div><small>START HERE</small><h2>热门探索入口</h2><p>选择一个主题开始。</p></div></div>
          <div className="productTabs">
            {suggestedTerms.map((term) => (
              <button type="button" onClick={() => selectSearchTerm(term)} key={term}>{term}</button>
            ))}
          </div>
          <div className="productEntityGrid">
            {snapshot.projects.slice(0, 3).map((project) => (
              <EntityCard
                kind="project"
                id={project.id}
                title={project.name}
                summary={project.summary}
                verificationStatus={project.verificationStatus}
                key={project.id}
              />
            ))}
          </div>
        </section>
      )}
      <ConfirmDialog open={clearHistoryOpen} title="清空最近搜索？" description="只会删除当前账户或浏览器保存的搜索词，不会删除收藏、想学或观看记录。" confirmLabel="确认清空" busy={clearingHistory} onCancel={() => setClearHistoryOpen(false)} onConfirm={() => void clearHistory()} />
      {feedback ? <div className="productToast" role="status">{feedback}</div> : null}
    </ProductFrame>
  );
}

export function SearchExperienceFromRoute() {
  const params = useSearchParams();
  return <SearchExperience key={params.toString()} initialQuery={params.get("q") ?? ""} initialScope={params.get("type") ?? "all"} initialSort={params.get("sort") ?? "relevance"} />;
}
