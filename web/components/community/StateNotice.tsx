"use client";

import Link from "next/link";

export type StateNoticeKind =
  | "loading"
  | "empty"
  | "error"
  | "offline"
  | "forbidden"
  | "rate-limited";

type StateNoticeProps = {
  kind: StateNoticeKind;
  title: string;
  description: string;
  actionLabel?: string;
  actionHref?: string;
  onAction?: () => void;
  compact?: boolean;
};

const stateIcons: Record<StateNoticeKind, string> = {
  loading: "…",
  empty: "◇",
  error: "!",
  offline: "↯",
  forbidden: "锁",
  "rate-limited": "候",
};

export function StateNotice({
  kind,
  title,
  description,
  actionLabel,
  actionHref,
  onAction,
  compact = false,
}: StateNoticeProps) {
  const liveRole = kind === "error" || kind === "offline" ? "alert" : "status";

  return (
    <section
      className={`productStateNotice productStateNotice--${kind}${compact ? " is-compact" : ""}`}
      role={liveRole}
      aria-live={liveRole === "alert" ? "assertive" : "polite"}
      aria-busy={kind === "loading"}
    >
      <span className="productStateIcon" aria-hidden="true">
        {stateIcons[kind]}
      </span>
      <div>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
      {actionLabel && actionHref ? (
        <Link className="productStateAction" href={actionHref}>
          {actionLabel}
        </Link>
      ) : null}
      {actionLabel && onAction && !actionHref ? (
        <button className="productStateAction" type="button" onClick={onAction}>
          {actionLabel}
        </button>
      ) : null}
    </section>
  );
}

export default StateNotice;
