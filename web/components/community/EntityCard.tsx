import Link from "next/link";

import type { VerificationStatus } from "@/lib/community";

import { TrustBadge } from "./TrustBadge";

export type EntityCardKind = "project" | "profile" | "region";

type EntityCardProps = {
  kind: EntityCardKind;
  id: string;
  title: string;
  summary: string;
  eyebrow?: string;
  meta?: string;
  mark?: string;
  verificationStatus?: VerificationStatus;
  href?: string;
  className?: string;
};

const kindPresentation: Record<EntityCardKind, { label: string; mark: string }> = {
  project: { label: "非遗项目", mark: "项" },
  profile: { label: "人物档案", mark: "人" },
  region: { label: "地域探索", mark: "地" },
};

function defaultHref(kind: EntityCardKind, id: string): string {
  const safeId = encodeURIComponent(id);
  if (kind === "project") return `/heritage-projects/${safeId}`;
  if (kind === "profile") return `/profile/${safeId}`;
  return `/map?region=${safeId}`;
}

export function EntityCard({
  kind,
  id,
  title,
  summary,
  eyebrow,
  meta,
  mark,
  verificationStatus,
  href,
  className = "",
}: EntityCardProps) {
  const presentation = kindPresentation[kind];
  const cardClassName = ["productEntityCard", `productEntityCard--${kind}`, className]
    .filter(Boolean)
    .join(" ");

  return (
    <article className={cardClassName}>
      <Link href={href ?? defaultHref(kind, id)} aria-label={`查看${presentation.label}：${title}`}>
        <span className="productEntityMark" aria-hidden="true">{mark ?? presentation.mark}</span>
        <div className="productEntityBody">
          <small>{eyebrow ?? presentation.label}</small>
          <h2>{title}</h2>
          <p>{summary}</p>
          {meta ? <span className="productEntityMeta">{meta}</span> : null}
          {verificationStatus ? <TrustBadge status={verificationStatus} compact /> : null}
        </div>
        <span className="productEntityArrow" aria-hidden="true">→</span>
      </Link>
    </article>
  );
}

export default EntityCard;
