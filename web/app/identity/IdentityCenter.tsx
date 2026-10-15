"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState, useSyncExternalStore } from "react";

import { ProductFrame } from "@/components/community/ProductFrame";
import { StateNotice } from "@/components/community/StateNotice";
import {
  AccountSession,
  activateBusinessRole,
  applyForBusinessRole,
  AUTH_REQUIRED,
  BusinessRole,
  clearUserCenterHistory,
  completeIdentityTask,
  deleteUserCenterNotification,
  getAuthSessionSnapshot,
  getIdentityWorkbench,
  getServerAuthSessionSnapshot,
  getUserCenter,
  initializeAuthSession,
  listAccountSessions,
  logoutAccount,
  markUserCenterNotificationRead,
  revokeAccountSession,
  revokeAllAccountSessions,
  setUserCenterFollow,
  setUserCenterLibrary,
  subscribeAuthSession,
  switchIdentityContext,
  updateUserCenterPreferences,
  updateUserCenterProfile,
  UserCenterSnapshot,
  WorkbenchSnapshot,
} from "@/lib/api";

type CenterView = "today" | "archive" | "workbench" | "tasks" | "settings";

const professionalRoles = new Set<BusinessRole>([
  "creator", "contributor", "seller", "reviewer", "admin",
]);
const roleLabels: Record<BusinessRole, string> = {
  viewer: "浏览者", buyer: "买家", learner: "学习者", creator: "创作者",
  contributor: "知识贡献者", seller: "卖家", reviewer: "审核员", admin: "管理员",
};
const roleDescriptions: Record<BusinessRole, string> = {
  viewer: "发现内容、关注人物并积累文化足迹。",
  buyer: "管理收藏商品、订单与售后。",
  learner: "管理想学清单、课程与成长记录。",
  creator: "管理创作、投稿与内容数据。",
  contributor: "提交来源、知识纠错和文化资料。",
  seller: "管理店铺、商品、库存与订单。",
  reviewer: "处理内容、来源与身份审核。",
  admin: "管理授权、风险与审计。",
};
const capabilityLabels = { available: "可使用", limited: "有限可用", blocked: "尚未接入" } as const;
const maturityLabels = { operational: "可运行", partial: "部分打通", blocked: "依赖后续模块" } as const;
const formatError = (cause: unknown) => cause instanceof Error ? cause.message : "操作失败，请稍后重试。";

export function IdentityCenter() {
  const authState = useSyncExternalStore(
    subscribeAuthSession, getAuthSessionSnapshot, getServerAuthSessionSnapshot,
  );
  const canLoad = !AUTH_REQUIRED || authState === "authenticated";
  const [snapshot, setSnapshot] = useState<UserCenterSnapshot | null>(null);
  const [workbench, setWorkbench] = useState<WorkbenchSnapshot | null>(null);
  const [view, setView] = useState<CenterView>("today");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [roleMenuOpen, setRoleMenuOpen] = useState(false);
  const [identityManagerOpen, setIdentityManagerOpen] = useState(false);
  const [applyRole, setApplyRole] = useState<BusinessRole | "">("");
  const [reason, setReason] = useState("");
  const [account, setAccount] = useState<UserCenterSnapshot["account"] | null>(null);
  const [preferences, setPreferences] = useState<UserCenterSnapshot["preferences"] | null>(null);
  const [sessions, setSessions] = useState<AccountSession[]>([]);

  useEffect(() => { void initializeAuthSession(); }, []);

  const load = useCallback(async () => {
    if (!canLoad) return;
    setError("");
    try {
      const [userCenter, roleWorkbench] = await Promise.all([getUserCenter(), getIdentityWorkbench()]);
      setSnapshot(userCenter);
      setWorkbench(roleWorkbench);
      setAccount(userCenter.account);
      setPreferences(userCenter.preferences);
    } catch (cause) {
      setError(formatError(cause));
    }
  }, [canLoad]);

  useEffect(() => {
    if (!canLoad) return;
    let active = true;
    void Promise.all([getUserCenter(), getIdentityWorkbench()])
      .then(([userCenter, roleWorkbench]) => {
        if (!active) return;
        setSnapshot(userCenter);
        setWorkbench(roleWorkbench);
        setAccount(userCenter.account);
        setPreferences(userCenter.preferences);
      })
      .catch((cause: unknown) => { if (active) setError(formatError(cause)); });
    return () => { active = false; };
  }, [canLoad]);
  useEffect(() => {
    if (view !== "settings" || (AUTH_REQUIRED && authState !== "authenticated")) return;
    void listAccountSessions().then((value) => setSessions(value.items)).catch((cause) => setError(formatError(cause)));
  }, [authState, view]);

  async function run(key: string, action: () => Promise<unknown>, message: string) {
    setBusy(key); setError(""); setFeedback("");
    try { await action(); await load(); setFeedback(message); }
    catch (cause) { setError(formatError(cause)); }
    finally { setBusy(""); }
  }

  async function switchRole(role: BusinessRole, label: string) {
    await run(`switch-${role}`, () => switchIdentityContext(role), `已切换为${label}。`);
    setRoleMenuOpen(false); setIdentityManagerOpen(false);
    if (!professionalRoles.has(role)) setView("today");
  }

  async function submitApplication(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!applyRole) return;
    await run("apply", () => applyForBusinessRole(applyRole, reason), "身份申请已提交审核。");
    setApplyRole(""); setReason("");
  }

  if (AUTH_REQUIRED && authState === "unknown") {
    return <ProductFrame><StateNotice kind="loading" title="正在验证安全会话" description="令牌由同源服务端安全保存，浏览器脚本不可读取。" /></ProductFrame>;
  }
  if (AUTH_REQUIRED && authState === "anonymous") {
    return <ProductFrame><StateNotice kind="empty" title="请先登录文化账户" description="用户中心保存身份、隐私偏好与个人文化资产，需要有效的内部测试账户会话。" actionLabel="前往登录" actionHref="/login" /></ProductFrame>;
  }
  if (!snapshot || !workbench) {
    return <ProductFrame>{error
      ? <StateNotice kind="error" title="用户中心 API 暂不可用" description={error} actionLabel="重新连接" onAction={() => void load()} />
      : <StateNotice kind="loading" title="正在加载文化账户" description="正在读取身份、文化资产、消息、工作台与偏好。" />}
    </ProductFrame>;
  }

  const activeRole = snapshot.profile.active_role;
  const activeRoles = snapshot.roles.filter((item) => item.status === "active");
  const hasProfessionalWorkbench = professionalRoles.has(activeRole);
  const navigation: [CenterView, string][] = [
    ["today", "今日"], ["archive", "文化资产"],
    ...(hasProfessionalWorkbench ? [["workbench", `${roleLabels[activeRole]}工作台`] as [CenterView, string]] : []),
    ["tasks", `消息与任务 ${snapshot.summary.unread_notifications + snapshot.summary.open_tasks}`],
    ["settings", "设置"],
  ];

  return <ProductFrame className="identityCenterFrame" mainClassName="identityCenterPage" demoLabel="文化账户 Gate C1">
    <section className="identityHero" data-testid="user-center-hero">
      <div><small>HAHA CULTURAL ACCOUNT</small><h1>{snapshot.account.display_name}的文化账户</h1><p>一个账户连接内容、学习、创作与未来的交易服务；数据由服务端按用户和工作空间隔离保存。</p></div>
      <div className="identityProfileMenu">
        <button className="identityProfileTrigger" type="button" aria-expanded={roleMenuOpen} aria-controls="identity-role-menu" onClick={() => setRoleMenuOpen((open) => !open)}>
          <span className="identityAvatar" aria-hidden="true">{snapshot.account.display_name.slice(0, 1).toUpperCase()}</span>
          <span><small>当前身份</small><strong>{roleLabels[activeRole]}</strong><em>{snapshot.account.region || "尚未设置地区"}</em></span><b aria-hidden="true">⌄</b>
        </button>
        {roleMenuOpen ? <div className="identityRoleMenu" id="identity-role-menu"><small>切换工作上下文</small>
          {activeRoles.map((item) => <button type="button" className={item.role === activeRole ? "current" : ""} disabled={item.role === activeRole || Boolean(busy)} key={item.id} onClick={() => void switchRole(item.role, item.label)}><span>{item.label}</span><em>{item.role === activeRole ? "当前" : "切换"}</em></button>)}
          <button className="manage" type="button" onClick={() => { setRoleMenuOpen(false); setIdentityManagerOpen(true); }}>管理身份与申请</button>
        </div> : null}
        <small className="identityVisibility">{snapshot.account.profile_visibility === "private" ? "仅自己可见" : snapshot.account.profile_visibility === "members" ? "成员可见" : "公开"}</small>
      </div>
    </section>

    <nav className="identityViewNav" aria-label="用户中心视图">{navigation.map(([key, label]) => <button type="button" key={key} className={view === key ? "active" : ""} aria-pressed={view === key} onClick={() => setView(key)}>{label}</button>)}</nav>
    {error ? <div className="identityAlert" role="alert">{error}</div> : null}

    {view === "today" ? <section className="identityMainPanel" data-testid="user-center-today">
      <div className="identitySectionHeading"><div><small>TODAY</small><h2>今天从这里继续</h2><p>只显示当前账户真实保存的数据、待办和能力边界。</p></div></div>
      <div className="productStatGrid"><div><b>{snapshot.summary.bookmarks}</b><span>收藏</span></div><div><b>{snapshot.summary.want_to_learn}</b><span>想学</span></div><div><b>{snapshot.summary.following}</b><span>关注</span></div><div><b>{snapshot.summary.history}</b><span>观看记录</span></div></div>
      <div className="identityWorkspaceGrid">
        <article><span className="productStatusPill is-good">继续观看</span><h3>{snapshot.today.continue_watching?.title ?? "还没有观看记录"}</h3><Link className="productButtonSecondary" href={snapshot.today.continue_watching?.target_href || "/"}>{snapshot.today.continue_watching ? "继续" : "发现内容"}</Link></article>
        <article><span className="productStatusPill is-good">下一项想学</span><h3>{snapshot.today.next_learning?.title ?? "想学清单还是空的"}</h3><Link className="productButtonSecondary" href={snapshot.today.next_learning?.target_href || "/search"}>{snapshot.today.next_learning ? "打开" : "搜索非遗"}</Link></article>
        <article><span className="productStatusPill is-warning">待处理</span><h3>{snapshot.today.open_tasks} 项任务 · {snapshot.today.unread_notifications} 条未读</h3><button className="productButtonSecondary" type="button" onClick={() => setView("tasks")}>查看消息与任务</button></article>
        <article><span className={`productStatusPill ${workbench.maturity === "operational" ? "is-good" : "is-warning"}`}>关键状态</span><h3>{roleLabels[activeRole]} · {maturityLabels[workbench.maturity]}</h3><p>{workbench.boundary_note}</p>{hasProfessionalWorkbench ? <button className="productButtonSecondary" type="button" onClick={() => setView("workbench")}>进入专业工作台</button> : <button className="productButtonSecondary" type="button" onClick={() => setRoleMenuOpen(true)}>切换身份</button>}</article>
      </div>
      {!hasProfessionalWorkbench ? <div className="identityCompactCapabilities" data-testid="current-role-boundary"><div><small>CURRENT ROLE CAPABILITIES</small><h3>{workbench.label}能力状态</h3><p>{workbench.description}</p></div><ul>{workbench.capabilities.map((capability) => <li className={`is-${capability.status}`} key={capability.key}><span><strong>{capability.label}</strong>{capability.reason ? <small>{capability.reason}</small> : null}</span><b>{capabilityLabels[capability.status]}</b></li>)}</ul></div> : null}
    </section> : null}

    {view === "archive" ? <section className="identityMainPanel" data-testid="user-center-archive">
      <div className="identitySectionHeading"><div><small>DURABLE CULTURAL ASSETS</small><h2>收藏与想学</h2><p>收藏、想学与稍后看已保存到服务端，可跨页面和设备恢复。</p></div></div>
      {snapshot.library.length ? <ul className="identityTaskList">{snapshot.library.map((item) => <li key={item.id}><div><span>{item.kind === "bookmark" ? "收藏" : item.kind === "want_to_learn" ? "想学" : "稍后看"}</span><h3>{item.title}</h3></div><div className="identityRowActions"><Link className="productButtonQuiet" href={item.target_href || "/"}>打开</Link><button className="productButtonSecondary" type="button" disabled={Boolean(busy)} onClick={() => void run(`remove-${item.id}`, () => setUserCenterLibrary(item.kind, item.target_id, item.title, item.target_href, false), "已移除。")}>移除</button></div></li>)}</ul> : <StateNotice kind="empty" title="文化资产还是空的" description="在内容详情页收藏、加入想学或稍后看，都会同步到这里。" />}

      <div className="identitySectionHeading"><div><small>FOLLOWING</small><h2>关注的人与机构</h2><p>关注关系属于当前账户，不随身份切换丢失。</p></div></div>
      {snapshot.follows.length ? <ul className="identityTaskList" data-testid="user-center-follows">{snapshot.follows.map((item) => <li key={item.id}><div><span>正在关注</span><h3>{item.display_name}</h3></div><div className="identityRowActions"><Link className="productButtonQuiet" href={item.target_href || "/inheritors"}>查看</Link><button className="productButtonSecondary" type="button" disabled={Boolean(busy)} onClick={() => void run(`unfollow-${item.id}`, () => setUserCenterFollow(item.target_id, item.display_name, item.target_href, false), "已取消关注。")}>取消关注</button></div></li>)}</ul> : <StateNotice kind="empty" title="还没有关注对象" description="在传承人或创作者页面关注后，会保存到这里。" actionLabel="发现传承人" actionHref="/inheritors" />}

      <div className="identitySectionHeading"><div><small>CULTURAL FOOTPRINT</small><h2>文化足迹与成长状态</h2><p>以下数字只由服务端真实资产、关注、观看和身份任务聚合。</p></div></div>
      <div className="identityFootprintGrid" data-testid="culture-footprint"><div><b>{snapshot.footprint.active_days}</b><span>留下足迹的日期</span></div><div><b>{snapshot.footprint.saved_assets}</b><span>文化资产</span></div><div><b>{snapshot.footprint.watched_items}</b><span>观看内容</span></div><div><b>{snapshot.footprint.completed_views}</b><span>完整观看</span></div><div><b>{snapshot.growth.active_roles}</b><span>已开通身份</span></div><div><b>{snapshot.growth.completed_tasks}</b><span>已完成任务</span></div></div>
      <div className="identityGrowthNote"><strong>{snapshot.growth.has_cultural_footprint ? "文化足迹已经建立" : "从第一条文化足迹开始"}</strong><p>{snapshot.footprint.latest_activity_at ? `最近活动：${new Date(snapshot.footprint.latest_activity_at).toLocaleDateString("zh-CN")}。` : "收藏、关注或观看内容后，这里会形成真实记录。"}学习路径、测验和成就属于 Gate C3，本页不会伪造。</p></div>

      <div className="identitySectionHeading"><div><h2>观看历史</h2><p>关闭历史记录后不会继续写入。</p></div>{snapshot.history.length ? <button className="productButtonSecondary" type="button" onClick={() => void run("clear-history", clearUserCenterHistory, "观看历史已清空。")}>清空历史</button> : null}</div>
      {snapshot.history.length ? <ul className="identityTaskList">{snapshot.history.map((item) => <li key={item.id}><div><span>{item.completed ? "已看完" : "观看记录"}</span><h3>{item.title}</h3><p>{item.progress_seconds} / {item.duration_seconds || "未知"} 秒</p></div><Link className="productButtonQuiet" href={item.target_href || "/"}>继续</Link></li>)}</ul> : <p>暂无观看历史。</p>}
    </section> : null}

    {view === "workbench" && hasProfessionalWorkbench ? <section className="identityMainPanel" data-testid="identity-workbench">
      <div className="identitySectionHeading"><div><small>ACTIVE ROLE WORKBENCH</small><h2>{workbench.label}工作台</h2><p>{workbench.headline}。{workbench.description}</p></div><span className={`identityMaturity is-${workbench.maturity}`}>{maturityLabels[workbench.maturity]}</span></div>
      <div className="identityWorkbenchMetrics" data-testid="workbench-metrics">{workbench.metrics.map((metric) => <div key={metric.key}><b>{metric.value}</b><span>{metric.label}</span></div>)}</div>
      <div className="identityCapabilityGrid" data-testid="workbench-capabilities">{workbench.capabilities.map((capability) => <article className={`is-${capability.status}`} key={capability.key}><div><span>{capabilityLabels[capability.status]}</span><h3>{capability.label}</h3><p>{capability.description}</p>{capability.reason ? <small>{capability.reason}</small> : null}</div>{capability.href && capability.action_label ? <Link className={capability.status === "available" ? "productButton" : "productButtonSecondary"} href={capability.href}>{capability.action_label}</Link> : <b>等待真实业务接入</b>}</article>)}</div>
      {workbench.resources.length ? <><div className="identitySectionHeading"><div><small>RESTORABLE WORK</small><h2>可继续的工作</h2><p>以下条目来自当前账户或工作空间的服务端持久状态。</p></div></div><ul className="identityTaskList" data-testid="workbench-resources">{workbench.resources.map((resource) => <li key={`${resource.kind}-${resource.id}`}><div><span>{resource.subtitle}</span><h3>{resource.title}</h3><p>{resource.status}</p></div><Link className="productButtonQuiet" href={resource.href}>继续</Link></li>)}</ul></> : <StateNotice kind="empty" title={`还没有${workbench.label}工作记录`} description="完成第一个真实任务后，可恢复的项目或文化资产会显示在这里。" />}
      <div className="identityBoundaryNote"><strong>能力边界</strong><p>{workbench.boundary_note}</p></div>
    </section> : null}

    {view === "tasks" ? <section className="identityMainPanel" data-testid="user-center-inbox">
      <div className="identitySectionHeading"><div><small>INBOX & TASKS</small><h2>消息与任务</h2><p>系统消息与身份任务均为服务端持久状态。</p></div></div>
      {snapshot.notifications.length ? <ul className="identityTaskList">{snapshot.notifications.map((item) => <li className={item.read_at ? "completed" : "open"} key={item.id}><div><span>{item.read_at ? "已读" : "未读"} · {item.kind}</span><h3>{item.title}</h3><p>{item.body}</p></div><div className="identityRowActions">{!item.read_at ? <button className="productButtonSecondary" type="button" onClick={() => void run(`read-${item.id}`, () => markUserCenterNotificationRead(item.id), "消息已读。")}>标记已读</button> : null}<button className="productButtonQuiet" type="button" onClick={() => void run(`delete-${item.id}`, () => deleteUserCenterNotification(item.id), "消息已删除。")}>删除</button></div></li>)}</ul> : <StateNotice kind="empty" title="没有系统消息" description="新的身份和系统事件会出现在这里。" />}
      {snapshot.tasks.length ? <><div className="identitySectionHeading"><div><h2>身份任务</h2><p>任务完成状态由服务端保存。</p></div></div><ul className="identityTaskList">{snapshot.tasks.map((task) => <li className={task.status} key={task.id}><div><span>{roleLabels[task.role]} · {task.kind}</span><h3>{task.title}</h3><p>{task.description}</p></div>{task.status === "open" ? <button className="productButtonSecondary" type="button" onClick={() => void run(`task-${task.id}`, () => completeIdentityTask(task.id), "任务已完成。")}>标记完成</button> : <b>已完成</b>}</li>)}</ul></> : null}
    </section> : null}

    {view === "settings" && account && preferences ? <section className="identityMainPanel" data-testid="user-center-settings">
      <div className="identitySectionHeading"><div><small>ACCOUNT & PRIVACY</small><h2>账户资料与隐私</h2><p>画像、推荐、通知和历史均可独立关闭。</p></div></div>
      <form className="identitySettingsForm" onSubmit={(event) => { event.preventDefault(); void run("profile", () => updateUserCenterProfile(account), "账户资料已保存。"); }}><label>显示名称<input value={account.display_name} maxLength={50} required onChange={(event) => setAccount({ ...account, display_name: event.target.value })} /></label><label>所在地区<input value={account.region} maxLength={100} onChange={(event) => setAccount({ ...account, region: event.target.value })} /></label><label>个人简介<textarea value={account.bio} maxLength={300} onChange={(event) => setAccount({ ...account, bio: event.target.value })} /></label><label>资料可见范围<select value={account.profile_visibility} onChange={(event) => setAccount({ ...account, profile_visibility: event.target.value as typeof account.profile_visibility })}><option value="private">仅自己</option><option value="members">平台成员</option><option value="public">公开</option></select></label><button className="productButton" type="submit">保存账户资料</button></form>
      <form className="identitySettingsForm" onSubmit={(event) => { event.preventDefault(); void run("preferences", () => updateUserCenterPreferences(preferences), "体验偏好已保存。"); }}>{([["history_enabled", "保存观看历史"], ["recommendation_enabled", "允许内容推荐"], ["personalization_enabled", "允许跨板块个性化"], ["notification_enabled", "接收站内通知"]] as [keyof typeof preferences, string][]).map(([key, label]) => <label className="identityToggle" key={key}><input type="checkbox" checked={preferences[key]} onChange={(event) => setPreferences({ ...preferences, [key]: event.target.checked })} /><span>{label}</span></label>)}<button className="productButtonSecondary" type="submit">保存体验偏好</button></form>
      <div className="identitySectionHeading"><div><small>SECURE SESSIONS</small><h2>登录设备与会话</h2><p>撤销后，对应访问令牌会立即失效。会话列表不包含任何令牌或密码。</p></div>{sessions.some((item) => item.status === "active") ? <button className="productButtonSecondary" type="button" onClick={() => void run("revoke-all", async () => { await revokeAllAccountSessions(); await logoutAccount(); }, "所有登录会话已撤销。")}>退出全部设备</button> : null}</div>
      {sessions.length ? <ul className="identityTaskList" data-testid="account-session-list">{sessions.map((session) => <li className={session.status === "active" ? "open" : "completed"} key={session.id}><div><span>{session.is_current ? "当前会话" : "其他会话"} · {session.status === "active" ? "有效" : session.status === "expired" ? "已过期" : "已撤销"}</span><h3>{session.id.slice(0, 20)}…</h3><p>最近使用：{new Date(session.last_used_at).toLocaleString("zh-CN")} · 到期：{new Date(session.expires_at).toLocaleString("zh-CN")}</p></div>{session.status === "active" ? <button className="productButtonSecondary" type="button" onClick={() => void run(`revoke-${session.id}`, async () => { await revokeAccountSession(session.id); if (session.is_current) await logoutAccount(); else setSessions((items) => items.map((item) => item.id === session.id ? { ...item, status: "revoked" } : item)); }, session.is_current ? "当前会话已退出。" : "该会话已撤销。")}>撤销</button> : null}</li>)}</ul> : <p>当前没有可显示的服务端会话。</p>}
    </section> : null}

    {identityManagerOpen ? <div className="identityDialogBackdrop"><section className="identityDialog identityManagerDialog" role="dialog" aria-modal="true" aria-labelledby="identity-manager-title"><button className="identityDialogClose" type="button" aria-label="关闭" onClick={() => setIdentityManagerOpen(false)}>×</button><small>ROLE MANAGEMENT</small><h2 id="identity-manager-title">管理身份与申请</h2><p>身份切换只改变工作上下文，服务端授权不会因此扩大。</p><div className="identityRoleGrid">{activeRoles.map((item) => <article className={item.role === activeRole ? "current" : ""} key={item.id}><span className="identityRoleMark">{item.label.slice(0, 1)}</span><div><h3>{item.label}</h3><p>{roleDescriptions[item.role]}</p></div>{item.role === activeRole ? <b>当前身份</b> : <button type="button" disabled={Boolean(busy)} onClick={() => void switchRole(item.role, item.label)}>切换</button>}</article>)}</div>{snapshot.available_actions.self_activate.length ? <><div className="identitySectionHeading"><div><h2>开通基础身份</h2><p>学习者和创作者可由本人开通，但不会获得管理权限。</p></div></div><div className="identityActionGrid">{snapshot.available_actions.self_activate.map((role) => <article key={role}><h3>开通{roleLabels[role]}</h3><p>{roleDescriptions[role]}</p><button className="productButton" type="button" onClick={() => void run(`activate-${role}`, () => activateBusinessRole(role), `${roleLabels[role]}已开通。`)}>开通身份</button></article>)}</div></> : null}{snapshot.available_actions.apply.length ? <><div className="identitySectionHeading"><div><h2>申请受控身份</h2><p>贡献者和卖家须进入审核，提交申请不会自动获得权限。</p></div></div><div className="identityActionGrid">{snapshot.available_actions.apply.map((role) => <article key={role}><h3>申请{roleLabels[role]}</h3><p>{roleDescriptions[role]}</p><button className="productButtonSecondary" type="button" onClick={() => { setIdentityManagerOpen(false); setApplyRole(role); }}>申请审核</button></article>)}</div></> : null}</section></div> : null}

    {applyRole ? <div className="identityDialogBackdrop"><form className="identityDialog" role="dialog" aria-modal="true" onSubmit={submitApplication}><button className="identityDialogClose" type="button" aria-label="关闭" onClick={() => setApplyRole("")}>×</button><h2>申请{roleLabels[applyRole]}身份</h2><p>提交后进入审核，不会自动获得权限。</p><label>申请说明<textarea value={reason} minLength={8} maxLength={1000} required onChange={(event) => setReason(event.target.value)} /></label><button className="productButton" type="submit">提交审核</button></form></div> : null}
    {feedback ? <div className="productToast" role="status">{feedback}</div> : null}
  </ProductFrame>;
}
