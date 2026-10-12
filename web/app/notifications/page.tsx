"use client";

import { useMemo, useState } from "react";
import Link from "next/link";

import { ProductFrame } from "@/components/community/ProductFrame";
import { StateNotice } from "@/components/community/StateNotice";
import { type NotificationKind, useCommunity } from "@/lib/community";

const filters: { value: "all" | NotificationKind; label: string }[] = [
  { value: "all", label: "全部" },
  { value: "comment", label: "评论与回复" },
  { value: "follow", label: "关注" },
  { value: "review", label: "审核结果" },
  { value: "correction", label: "纠错处理" },
  { value: "event", label: "活动提醒" },
  { value: "system", label: "系统" },
];

const dateTimeFormatter = new Intl.DateTimeFormat("zh-CN", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "Asia/Shanghai",
});

export default function NotificationsPage() {
  const { snapshot, actions, unreadNotificationCount } = useCommunity();
  const [filter, setFilter] = useState<(typeof filters)[number]["value"]>("all");
  const [busyId, setBusyId] = useState("");
  const [feedback, setFeedback] = useState("");

  const notifications = useMemo(() => snapshot.notifications
    .filter((item) => filter === "all" || item.kind === filter)
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt)), [filter, snapshot.notifications]);

  async function act(id: string, operation: () => Promise<void>, message: string) {
    setBusyId(id);
    setFeedback("");
    try {
      await operation();
      setFeedback(message);
    } catch (cause) {
      setFeedback(cause instanceof Error ? cause.message : "操作失败，请重试。");
    } finally {
      setBusyId("");
    }
  }

  return (
    <ProductFrame>
      <div className="productDemoStrip" role="note">
        <b>本地消息中心</b>
        <span>审核流转和互动生成的消息保存在当前浏览器；真实账号通知将在 API 接入后启用。</span>
      </div>
      <header className="productPageHead">
        <div>
          <small>NOTIFICATIONS</small>
          <h1>消息中心</h1>
          <p>{unreadNotificationCount ? `还有 ${unreadNotificationCount} 条未读消息。` : "当前消息都已读。"}</p>
        </div>
        {unreadNotificationCount ? (
          <button
            className="productButtonSecondary"
            type="button"
            disabled={busyId === "all"}
            onClick={() => void act("all", actions.markAllNotificationsRead, "已将全部消息标记为已读。")}
          >全部已读</button>
        ) : null}
      </header>
      <div className="productFilterBar" aria-label="消息类型">
        {filters.map((item) => (
          <button
            className={filter === item.value ? "active" : ""}
            type="button"
            aria-pressed={filter === item.value}
            onClick={() => setFilter(item.value)}
            key={item.value}
          >{item.label}</button>
        ))}
      </div>
      {notifications.length ? (
        <ul className="productNotificationList">
          {notifications.map((notification) => (
            <li className={notification.readAt ? "" : "unread"} key={notification.id}>
              <small>{dateTimeFormatter.format(new Date(notification.createdAt))} · {filters.find((item) => item.value === notification.kind)?.label ?? notification.kind}</small>
              <h2>{notification.title}</h2>
              <p>{notification.body}</p>
              <div className="productNotificationActions">
                {notification.targetHref ? <Link className="productButtonSecondary" href={notification.targetHref}>查看详情</Link> : null}
                {!notification.readAt ? (
                  <button
                    className="productButtonQuiet"
                    type="button"
                    disabled={busyId === notification.id}
                    onClick={() => void act(notification.id, () => actions.markNotificationRead(notification.id), "消息已读。")}
                  >标为已读</button>
                ) : null}
                <button
                  className="productButtonQuiet"
                  type="button"
                  disabled={busyId === notification.id}
                  onClick={() => void act(notification.id, () => actions.deleteNotification(notification.id), "已删除这条本地消息。")}
                >删除</button>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <StateNotice kind="empty" title="这个分类还没有消息" description="投稿审核、评论回复和活动提醒会出现在这里。" actionLabel="去浏览内容" actionHref="/" />
      )}
      {feedback ? <div className="productToast" role="status">{feedback}</div> : null}
    </ProductFrame>
  );
}
