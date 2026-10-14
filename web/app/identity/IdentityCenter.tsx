"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { ProductFrame } from "@/components/community/ProductFrame";
import { StateNotice } from "@/components/community/StateNotice";
import {
  activateBusinessRole, applyForBusinessRole, AUTH_REQUIRED, BusinessRole, clearUserCenterHistory,
  completeIdentityTask, getUserCenter, markUserCenterNotificationRead,
  getAuthSessionSnapshot, getServerAuthSessionSnapshot, initializeAuthSession,
  listAccountSessions, logoutAccount, revokeAccountSession, revokeAllAccountSessions,
  setUserCenterLibrary, subscribeAuthSession,
  switchIdentityContext, updateUserCenterPreferences,
  updateUserCenterProfile, AccountSession, UserCenterSnapshot,
} from "@/lib/api";

type CenterView = "today" | "archive" | "identity" | "tasks" | "settings";
const roleLabels: Record<BusinessRole, string> = { viewer: "浏览者", buyer: "买家", learner: "学习者", creator: "创作者", contributor: "知识贡献者", seller: "卖家", reviewer: "审核员", admin: "管理员" };
const roleDescriptions: Record<BusinessRole, string> = {
  viewer: "发现内容、关注人物并积累文化足迹。", buyer: "管理收藏商品、订单与售后。",
  learner: "管理想学清单、课程与成长记录。", creator: "管理创作、投稿与内容数据。",
  contributor: "提交来源、知识纠错和文化资料。", seller: "管理店铺、商品、库存与订单。",
  reviewer: "处理内容、来源与身份审核。", admin: "管理授权、风险与审计。",
};
const formatError = (cause: unknown) => cause instanceof Error ? cause.message : "操作失败，请稍后重试。";

export function IdentityCenter() {
  const authState = useSyncExternalStore(
    subscribeAuthSession, getAuthSessionSnapshot, getServerAuthSessionSnapshot,
  );
  const needsLogin = AUTH_REQUIRED && authState === "anonymous";
  const canLoad = !AUTH_REQUIRED || authState === "authenticated";
  const [snapshot, setSnapshot] = useState<UserCenterSnapshot | null>(null);
  const [view, setView] = useState<CenterView>("today");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [applyRole, setApplyRole] = useState<BusinessRole | "">("");
  const [reason, setReason] = useState("");
  const [account, setAccount] = useState<UserCenterSnapshot["account"] | null>(null);
  const [preferences, setPreferences] = useState<UserCenterSnapshot["preferences"] | null>(null);
  const [sessions, setSessions] = useState<AccountSession[]>([]);

  useEffect(() => { void initializeAuthSession(); }, []);

  const load = useCallback(async () => {
    if (!canLoad) return;
    setError("");
    try { const value = await getUserCenter(); setSnapshot(value); setAccount(value.account); setPreferences(value.preferences); }
    catch (cause) { setError(formatError(cause)); }
  }, [canLoad]);
  useEffect(() => {
    if (!canLoad) return;
    let active = true;
    void getUserCenter().then((value) => {
      if (!active) return;
      setSnapshot(value); setAccount(value.account); setPreferences(value.preferences);
    }).catch((cause: unknown) => { if (active) setError(formatError(cause)); });
    return () => { active = false; };
  }, [canLoad]);
  useEffect(() => {
    if (view !== "settings" || (AUTH_REQUIRED && authState !== "authenticated")) return;
    void listAccountSessions().then((value) => setSessions(value.items)).catch((cause: unknown) => setError(formatError(cause)));
  }, [authState, view]);
  async function run(key: string, action: () => Promise<UserCenterSnapshot | void>, message: string) {
    setBusy(key); setError("");
    try { const value = await action(); if (value) setSnapshot(value); else await load(); setFeedback(message); }
    catch (cause) { setError(formatError(cause)); }
    finally { setBusy(""); }
  }
  async function submitApplication(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!applyRole) return;
    await run("apply", async () => { await applyForBusinessRole(applyRole, reason); await load(); }, "身份申请已提交审核。");
    setApplyRole(""); setReason("");
  }
  if (AUTH_REQUIRED && authState === "unknown") return <ProductFrame><StateNotice kind="loading" title="正在验证安全会话" description="令牌由同源服务端安全保存，浏览器脚本不可读取。" /></ProductFrame>;
  if (needsLogin) return <ProductFrame><StateNotice kind="empty" title="请先登录文化账户" description="用户中心保存身份、隐私偏好与个人文化资产，需要有效的内部测试账户会话。" actionLabel="前往登录" actionHref="/login" /></ProductFrame>;
  if (!snapshot) return <ProductFrame>{error ? <StateNotice kind="error" title="用户中心 API 暂不可用" description={error} actionLabel="重新连接" onAction={() => void load()} /> : <StateNotice kind="loading" title="正在加载文化账户" description="正在读取身份、文化资产、消息与偏好。" />}</ProductFrame>;
  const activeRole = snapshot.profile.active_role;

  return <ProductFrame className="identityCenterFrame" mainClassName="identityCenterPage" demoLabel="安全账户 G3">
    <section className="identityHero" data-testid="user-center-hero"><div><small>HAHA CULTURAL ACCOUNT</small><h1>{snapshot.account.display_name}的文化账户</h1><p>一个账户连接内容、学习、创作与未来的交易服务；数据由服务端按用户和工作空间隔离保存。</p></div><div className="identityCurrentRole"><span>当前身份</span><strong>{roleLabels[activeRole]}</strong><small>{snapshot.account.region || "尚未设置地区"} · {snapshot.account.profile_visibility === "private" ? "仅自己可见" : snapshot.account.profile_visibility === "members" ? "成员可见" : "公开"}</small></div></section>
    <nav className="identityViewNav" aria-label="用户中心视图">{([['today','今日'],['archive','文化资产'],['identity','身份与工作台'],['tasks',`消息与任务 ${snapshot.summary.unread_notifications + snapshot.summary.open_tasks}`],['settings','设置']] as [CenterView,string][]).map(([key,label]) => <button type="button" key={key} className={view === key ? "active" : ""} aria-pressed={view === key} onClick={() => setView(key)}>{label}</button>)}</nav>
    {error ? <div className="identityAlert" role="alert">{error}</div> : null}

    {view === "today" ? <section className="identityMainPanel" data-testid="user-center-today"><div className="identitySectionHeading"><div><small>TODAY</small><h2>今天从这里继续</h2><p>只显示当前账户真实保存的数据与待办。</p></div></div><div className="productStatGrid"><div><b>{snapshot.summary.bookmarks}</b><span>收藏</span></div><div><b>{snapshot.summary.want_to_learn}</b><span>想学</span></div><div><b>{snapshot.summary.following}</b><span>关注</span></div><div><b>{snapshot.summary.history}</b><span>观看记录</span></div></div><div className="identityWorkspaceGrid"><article><span className="productStatusPill is-good">继续观看</span><h3>{snapshot.today.continue_watching?.title ?? "还没有观看记录"}</h3><Link className="productButtonSecondary" href={snapshot.today.continue_watching?.target_href || "/"}>{snapshot.today.continue_watching ? "继续" : "发现内容"}</Link></article><article><span className="productStatusPill is-good">下一项想学</span><h3>{snapshot.today.next_learning?.title ?? "想学清单还是空的"}</h3><Link className="productButtonSecondary" href={snapshot.today.next_learning?.target_href || "/search"}>{snapshot.today.next_learning ? "打开" : "搜索非遗"}</Link></article><article><span className="productStatusPill is-warning">待处理</span><h3>{snapshot.today.open_tasks} 项任务 · {snapshot.today.unread_notifications} 条未读</h3><button className="productButtonSecondary" type="button" onClick={() => setView("tasks")}>查看消息与任务</button></article></div></section> : null}

    {view === "archive" ? <section className="identityMainPanel" data-testid="user-center-archive"><div className="identitySectionHeading"><div><small>DURABLE CULTURAL ASSETS</small><h2>文化资产</h2><p>收藏、想学与稍后看已保存到服务端，可跨页面和设备恢复。</p></div></div>{snapshot.library.length ? <ul className="identityTaskList">{snapshot.library.map((item) => <li key={item.id}><div><span>{item.kind === "bookmark" ? "收藏" : item.kind === "want_to_learn" ? "想学" : "稍后看"}</span><h3>{item.title}</h3></div><div><Link className="productButtonQuiet" href={item.target_href || "/"}>打开</Link><button className="productButtonSecondary" type="button" onClick={() => void run(`remove-${item.id}`, () => setUserCenterLibrary(item.kind, item.target_id, item.title, item.target_href, false), "已移除。")}>移除</button></div></li>)}</ul> : <StateNotice kind="empty" title="文化资产还是空的" description="在内容详情页收藏、加入想学或稍后看，都会同步到这里。" />}<div className="identitySectionHeading"><div><h2>观看历史</h2><p>关闭历史记录后不会继续写入。</p></div>{snapshot.history.length ? <button className="productButtonSecondary" type="button" onClick={() => void run("clear-history", async () => { await clearUserCenterHistory(); }, "观看历史已清空。")}>清空历史</button> : null}</div>{snapshot.history.length ? <ul className="identityTaskList">{snapshot.history.map((item) => <li key={item.id}><div><span>{item.completed ? "已看完" : "观看记录"}</span><h3>{item.title}</h3><p>{item.progress_seconds} / {item.duration_seconds || '未知'} 秒</p></div><Link className="productButtonQuiet" href={item.target_href || "/"}>继续</Link></li>)}</ul> : <p>暂无观看历史。</p>}</section> : null}

    {view === "identity" ? <section className="identityMainPanel" data-testid="identity-workbench"><div className="identitySectionHeading"><div><small>ROLE CONTEXT</small><h2>身份与工作台</h2><p>切换只改变工作上下文，服务端权限不会因此扩大。</p></div></div><div className="identityRoleGrid">{snapshot.roles.filter((item) => item.status === "active").map((item) => <article className={item.role === activeRole ? "current" : ""} key={item.id}><span className="identityRoleMark">{item.label.slice(0,1)}</span><div><h3>{item.label}</h3><p>{roleDescriptions[item.role]}</p></div>{item.role === activeRole ? <b>当前身份</b> : <button type="button" disabled={Boolean(busy)} onClick={() => void run(`switch-${item.role}`, async () => { await switchIdentityContext(item.role); await load(); }, `已切换为${item.label}。`)}>切换</button>}</article>)}</div>{snapshot.available_actions.self_activate.length ? <div className="identityActionGrid">{snapshot.available_actions.self_activate.map((role) => <article key={role}><h3>开通{roleLabels[role]}</h3><p>{roleDescriptions[role]}</p><button className="productButton" type="button" onClick={() => void run(`activate-${role}`, async () => { await activateBusinessRole(role); await load(); }, `${roleLabels[role]}已开通。`)}>开通身份</button></article>)}</div> : null}{snapshot.available_actions.apply.length ? <div className="identityActionGrid">{snapshot.available_actions.apply.map((role) => <article key={role}><h3>申请{roleLabels[role]}</h3><p>{roleDescriptions[role]}</p><button className="productButtonSecondary" type="button" onClick={() => setApplyRole(role)}>申请审核</button></article>)}</div> : null}</section> : null}

    {view === "tasks" ? <section className="identityMainPanel" data-testid="user-center-inbox"><div className="identitySectionHeading"><div><small>INBOX & TASKS</small><h2>消息与任务</h2><p>系统消息与身份任务均为服务端持久状态。</p></div></div>{snapshot.notifications.length ? <ul className="identityTaskList">{snapshot.notifications.map((item) => <li className={item.read_at ? "completed" : "open"} key={item.id}><div><span>{item.read_at ? "已读" : "未读"} · {item.kind}</span><h3>{item.title}</h3><p>{item.body}</p></div>{!item.read_at ? <button className="productButtonSecondary" type="button" onClick={() => void run(`read-${item.id}`, async () => { await markUserCenterNotificationRead(item.id); }, "消息已读。")}>标记已读</button> : null}</li>)}</ul> : <p>没有系统消息。</p>}{snapshot.tasks.length ? <ul className="identityTaskList">{snapshot.tasks.map((task) => <li className={task.status} key={task.id}><div><span>{roleLabels[task.role]} · {task.kind}</span><h3>{task.title}</h3><p>{task.description}</p></div>{task.status === "open" ? <button className="productButtonSecondary" type="button" onClick={() => void run(`task-${task.id}`, async () => { await completeIdentityTask(task.id); }, "任务已完成。")}>标记完成</button> : <b>已完成</b>}</li>)}</ul> : null}</section> : null}

    {view === "settings" && account && preferences ? <section className="identityMainPanel" data-testid="user-center-settings"><div className="identitySectionHeading"><div><small>ACCOUNT & PRIVACY</small><h2>账户资料与隐私</h2><p>画像、推荐、通知和历史均可独立关闭。</p></div></div><form className="identitySettingsForm" onSubmit={(event) => { event.preventDefault(); void run("profile", () => updateUserCenterProfile(account), "账户资料已保存。"); }}><label>显示名称<input value={account.display_name} maxLength={50} required onChange={(event) => setAccount({...account, display_name:event.target.value})} /></label><label>所在地区<input value={account.region} maxLength={100} onChange={(event) => setAccount({...account, region:event.target.value})} /></label><label>个人简介<textarea value={account.bio} maxLength={300} onChange={(event) => setAccount({...account, bio:event.target.value})} /></label><label>资料可见范围<select value={account.profile_visibility} onChange={(event) => setAccount({...account, profile_visibility:event.target.value as typeof account.profile_visibility})}><option value="private">仅自己</option><option value="members">平台成员</option><option value="public">公开</option></select></label><button className="productButton" type="submit">保存账户资料</button></form><form className="identitySettingsForm" onSubmit={(event) => { event.preventDefault(); void run("preferences", () => updateUserCenterPreferences(preferences), "体验偏好已保存。"); }}>{([['history_enabled','保存观看历史'],['recommendation_enabled','允许内容推荐'],['personalization_enabled','允许跨板块个性化'],['notification_enabled','接收站内通知']] as [keyof typeof preferences,string][]).map(([key,label]) => <label className="identityToggle" key={key}><input type="checkbox" checked={preferences[key]} onChange={(event) => setPreferences({...preferences,[key]:event.target.checked})} /><span>{label}</span></label>)}<button className="productButtonSecondary" type="submit">保存体验偏好</button></form><div className="identitySectionHeading"><div><small>SECURE SESSIONS</small><h2>登录设备与会话</h2><p>撤销后，对应访问令牌会立即失效。会话列表不包含任何令牌或密码。</p></div>{sessions.some((item) => item.status === "active") ? <button className="productButtonSecondary" type="button" onClick={() => void run("revoke-all", async () => { await revokeAllAccountSessions(); await logoutAccount(); }, "所有登录会话已撤销。")}>退出全部设备</button> : null}</div>{sessions.length ? <ul className="identityTaskList" data-testid="account-session-list">{sessions.map((session) => <li className={session.status === "active" ? "open" : "completed"} key={session.id}><div><span>{session.is_current ? "当前会话" : "其他会话"} · {session.status === "active" ? "有效" : session.status === "expired" ? "已过期" : "已撤销"}</span><h3>{session.id.slice(0, 20)}…</h3><p>最近使用：{new Date(session.last_used_at).toLocaleString("zh-CN")} · 到期：{new Date(session.expires_at).toLocaleString("zh-CN")}</p></div>{session.status === "active" ? <button className="productButtonSecondary" type="button" onClick={() => void run(`revoke-${session.id}`, async () => { await revokeAccountSession(session.id); if (session.is_current) await logoutAccount(); else setSessions((items) => items.map((item) => item.id === session.id ? {...item, status:"revoked"} : item)); }, session.is_current ? "当前会话已退出。" : "该会话已撤销。")}>撤销</button> : null}</li>)}</ul> : <p>当前没有可显示的服务端会话。</p>}</section> : null}

    {applyRole ? <div className="identityDialogBackdrop"><form className="identityDialog" role="dialog" aria-modal="true" onSubmit={submitApplication}><button className="identityDialogClose" type="button" aria-label="关闭" onClick={() => setApplyRole("")}>×</button><h2>申请{roleLabels[applyRole]}身份</h2><p>提交后进入审核，不会自动获得权限。</p><label>申请说明<textarea value={reason} minLength={8} maxLength={1000} required onChange={(event) => setReason(event.target.value)} /></label><button className="productButton" type="submit">提交审核</button></form></div> : null}
    {feedback ? <div className="productToast" role="status">{feedback}</div> : null}
  </ProductFrame>;
}
