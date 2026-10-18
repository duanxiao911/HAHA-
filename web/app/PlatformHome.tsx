"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, useSyncExternalStore } from "react";

import { ProductFrame } from "@/components/community/ProductFrame";
import { StateNotice } from "@/components/community/StateNotice";
import {
  AUTH_REQUIRED,
  BusinessRole,
  DEMO_MODE,
  getAuthSessionSnapshot,
  getIdentityWorkbench,
  getServerAuthSessionSnapshot,
  getUserCenter,
  initializeAuthSession,
  subscribeAuthSession,
  UserCenterSnapshot,
  WorkbenchSnapshot,
} from "@/lib/api";

const roleLabels: Record<BusinessRole, string> = {
  viewer: "浏览者", buyer: "买家", learner: "学习者", creator: "创作者",
  contributor: "知识贡献者", seller: "卖家", reviewer: "审核员", admin: "管理员",
};
const roleConversionCopy: Partial<Record<BusinessRole, string>> = {
  learner: "开通学习者，保存课程进度、测验记录与成长成就。",
  creator: "开通创作者，进入脚本创作与内容投稿工作台。",
  contributor: "申请知识贡献者，提交来源、纠错与文化资料。",
  seller: "申请卖家，管理商品、库存与订单。",
};

type ModuleCardProps = {
  href: string;
  icon: string;
  title: string;
  description: string;
  status: string;
  statusTone?: "ready" | "sandbox" | "bounded";
  action: string;
  className?: string;
};

function ModuleCard({ href, icon, title, description, status, statusTone = "ready", action, className = "" }: ModuleCardProps) {
  return <Link className={`platformModuleCard ${className}`.trim()} href={href}>
    <span className="platformModuleIcon" aria-hidden="true">{icon}</span>
    <h3>{title}</h3><p>{description}</p>
    <footer><span className={`platformModuleStatus is-${statusTone}`}>{status}</span><b>{action} →</b></footer>
  </Link>;
}

export function PlatformHome() {
  const authState = useSyncExternalStore(subscribeAuthSession, getAuthSessionSnapshot, getServerAuthSessionSnapshot);
  const canLoadPersonal = !DEMO_MODE && (!AUTH_REQUIRED || authState === "authenticated");
  const [snapshot, setSnapshot] = useState<UserCenterSnapshot | null>(null);
  const [workbench, setWorkbench] = useState<WorkbenchSnapshot | null>(null);
  const [error, setError] = useState("");

  useEffect(() => { void initializeAuthSession(); }, []);
  const load = useCallback(async () => {
    if (!canLoadPersonal) return;
    setError("");
    try {
      const [userCenter, roleWorkbench] = await Promise.all([getUserCenter(), getIdentityWorkbench()]);
      setSnapshot(userCenter); setWorkbench(roleWorkbench);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "平台首页暂时无法读取账户摘要。");
    }
  }, [canLoadPersonal]);
  useEffect(() => {
    if (!canLoadPersonal) return;
    let active = true;
    void Promise.all([getUserCenter(), getIdentityWorkbench()])
      .then(([userCenter, roleWorkbench]) => {
        if (!active) return;
        setSnapshot(userCenter); setWorkbench(roleWorkbench);
      })
      .catch((cause: unknown) => {
        if (active) setError(cause instanceof Error ? cause.message : "平台首页暂时无法读取账户摘要。");
      });
    return () => { active = false; };
  }, [canLoadPersonal]);

  const signedOut = AUTH_REQUIRED && authState === "anonymous";
  const loading = canLoadPersonal && !snapshot && !error;
  const activeRole = snapshot?.profile.active_role;
  const selfActivateRole = snapshot?.available_actions.self_activate[0];
  const applicationRole = snapshot?.available_actions.apply[0];
  const conversionRole = selfActivateRole ?? applicationRole;
  const availableCapability = workbench?.capabilities.find((item) => item.status === "available" && item.href);
  const aiTutorCapability = workbench?.capabilities.find((item) => item.key === "ai_tutor");
  const aiTutorStatus = aiTutorCapability?.status === "available"
    ? "学习可用 · AI 老师可用"
    : aiTutorCapability?.status === "blocked"
      ? "学习可用 · AI 老师受阻"
      : "学习可用 · AI 按运行状态";
  const resumeItems = snapshot ? [
    snapshot.today.continue_watching ? {
      eyebrow: "视频社区", title: snapshot.today.continue_watching.title,
      detail: `已观看 ${snapshot.today.continue_watching.progress_seconds} 秒`, href: snapshot.today.continue_watching.target_href || "/community",
    } : null,
    snapshot.today.next_learning ? {
      eyebrow: "学习清单", title: snapshot.today.next_learning.title,
      detail: "已保存到当前账户", href: snapshot.today.next_learning.target_href || "/learning",
    } : null,
    availableCapability ? {
      eyebrow: `${workbench?.label ?? "身份"}工作台`, title: availableCapability.label,
      detail: availableCapability.description, href: availableCapability.href,
    } : null,
  ].filter((item): item is NonNullable<typeof item> => Boolean(item)) : [];

  return <ProductFrame className="platformHomeFrame" mainClassName="platformHomePage">
    <section className="platformHero" data-testid="platform-home-hero">
      <div className="platformWelcome">
        <small>HAHA · 文化今日</small>
        <h1>{snapshot ? `${snapshot.account.display_name}，继续你的非遗探索` : "从今天开始，认识仍在发生的非遗"}</h1>
        <p>{snapshot
          ? `一个账户连接观看、学习、创作与交易。当前使用“${activeRole ? roleLabels[activeRole] : "读取中"}”视角，首页会据此推荐可继续的任务。`
          : DEMO_MODE
            ? "当前为本地演示，仅展示模块结构与本机社区数据；真实账户摘要只在 API 模式从服务端读取。"
            : "从视频、学习、创作与可信交易入口进入；登录后可以跨设备恢复服务端保存的进度与任务。"}</p>
        <div className="platformHeroActions">
          {snapshot?.today.next_learning ? <Link className="productButton" href="/learning">继续学习</Link> : <Link className="productButton" href="/community">发现非遗内容</Link>}
          {signedOut ? <Link className="productButtonSecondary" href="/login">登录文化账户</Link> : null}
          {snapshot ? <span>{snapshot.growth.completed_units} 个学习节点 · {snapshot.footprint.watched_items} 条观看记录</span> : null}
        </div>
      </div>
      <aside className="platformToday" aria-label="今日账户状态">
        <header><div><small>TODAY</small><h2>今日概览</h2></div>{snapshot ? <span>连续 {snapshot.growth.current_streak} 天</span> : null}</header>
        {loading ? <div className="platformTodayLoading" aria-busy="true"><i /><i /><i /></div> : null}
        {!loading && snapshot ? <>
          <Link href="/identity?tab=tasks"><b>{snapshot.summary.open_tasks}</b><span>待处理任务</span><em>查看 →</em></Link>
          <Link href="/notifications"><b>{snapshot.summary.unread_notifications}</b><span>未读消息</span><em>查看 →</em></Link>
          <Link href="/learning"><b>{snapshot.growth.achievements}</b><span>学习成就</span><em>继续 →</em></Link>
        </> : null}
        {!loading && !snapshot && !error ? <p className="platformTodayEmpty">{DEMO_MODE ? "本地演示不伪造账户任务、通知或成长记录。" : "登录后显示当前账户的真实任务、通知和成长状态。"}</p> : null}
      </aside>
    </section>

    {snapshot && conversionRole ? <section className="platformIdentityGuide" data-testid="identity-conversion-guide">
      <div><small>身份成长建议</small><h2>{selfActivateRole ? `想使用${roleLabels[conversionRole]}能力？` : `想申请${roleLabels[conversionRole]}身份？`}</h2><p>{roleConversionCopy[conversionRole] ?? "前往用户中心查看身份用途、授权状态与申请要求。"} 开通或申请是权限变化，与快捷切换已开通身份不同。</p></div>
      <Link className="productButtonSecondary" href="/identity?manage=roles">{selfActivateRole ? `了解并开通${roleLabels[conversionRole]}` : `查看${roleLabels[conversionRole]}申请`}</Link>
    </section> : null}

    {error ? <StateNotice kind="error" title="个人摘要暂未加载" description={error} actionLabel="重新读取" onAction={() => void load()} compact /> : null}

    <section className="platformModuleSection" aria-labelledby="platform-modules-title">
      <div className="platformSectionHeading"><div><small>FOUR CORE SPACES</small><h2 id="platform-modules-title">四大板块，一处进入</h2></div><p>全局入口保持稳定，创作、投稿和经营操作回到所属板块与身份工作台。</p></div>
      <div className="platformModuleGrid">
        <ModuleCard href="/community" icon="▶" title="视频社区" description="发现内容、观看互动、加入想学清单，并进入创作者投稿。" status="可使用" action="进入社区" />
        <ModuleCard href="/commerce" icon="袋" title="非遗电商" description="浏览商品、管理购物车与订单，或进入卖家经营工作台。" status="内部沙盒" statusTone="sandbox" action="进入电商" className="is-commerce" />
        <ModuleCard href="/learning" icon="学" title="AI 学习" description="学习路径、知识卡、测验、每日任务与成长记录。" status={aiTutorStatus} statusTone="bounded" action="进入学习" className="is-learning" />
        <ModuleCard href="/identity" icon="人" title="用户中心" description="统一账户、文化资产、成长汇总、身份权限与安全设置。" status={activeRole ? `当前：${roleLabels[activeRole]}` : "统一账户"} action="管理账户" />
      </div>
    </section>

    <section className="platformLowerGrid">
      <article className="platformResumePanel">
        <div className="platformSectionHeading"><div><small>RESUME</small><h2>继续上次进度</h2></div></div>
        {loading ? <StateNotice kind="loading" title="正在恢复账户进度" description="从服务端读取观看、学习和当前身份工作台。" compact /> : null}
        {!loading && resumeItems.length ? <div className="platformResumeGrid">{resumeItems.map((item) => <Link href={item.href} key={`${item.eyebrow}-${item.title}`}><small>{item.eyebrow}</small><b>{item.title}</b><span>{item.detail}</span><em>继续 →</em></Link>)}</div> : null}
        {!loading && !resumeItems.length ? <StateNotice kind="empty" title="还没有可继续的进度" description={DEMO_MODE ? "本地演示不伪造跨设备账户进度；可先进入社区体验本机数据。" : signedOut ? "登录后会显示服务端保存的观看、学习和工作台任务。" : "从社区观看内容、加入学习路径或开通业务身份后，这里会形成快捷入口。"} actionLabel={signedOut ? "去登录" : "浏览视频社区"} actionHref={signedOut ? "/login" : "/community"} compact /> : null}
      </article>
      <aside className="platformBoundaryPanel">
        <small>BOUNDARIES</small><h2>能力边界</h2>
        <div><strong>AI 非遗老师 · 受控能力</strong><p>登录学习中心后按运行时状态开放；回答只使用版本化来源，未命中时明确拒答。</p></div>
        <div className="is-sandbox"><strong>非遗电商 · INTERNAL SANDBOX</strong><p>只用于内部交易闭环验证，不接入真实支付，不发生真实资金移动。</p></div>
        {workbench ? <Link href="/identity?tab=workbench">当前身份：{workbench.label} · {workbench.maturity === "operational" ? "可运行" : workbench.maturity === "partial" ? "部分可用" : "受阻"} →</Link> : null}
      </aside>
    </section>
  </ProductFrame>;
}

export default PlatformHome;
