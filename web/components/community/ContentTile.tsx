import type { CSSProperties } from "react";
import Link from "next/link";

import type { ContentSummary } from "@/lib/community";

import { TrustBadge } from "./TrustBadge";

type ContentTileProps = {
  content: ContentSummary;
  compact?: boolean;
  className?: string;
};

const countFormatter = new Intl.NumberFormat("zh-CN", {
  notation: "compact",
  maximumFractionDigits: 1,
});

function formatCount(value: number): string {
  return countFormatter.format(Math.max(0, value));
}

function formatDuration(seconds?: number): string | null {
  if (typeof seconds !== "number" || !Number.isFinite(seconds) || seconds < 0) return null;
  const rounded = Math.round(seconds);
  const hours = Math.floor(rounded / 3600);
  const minutes = Math.floor((rounded % 3600) / 60);
  const remainingSeconds = rounded % 60;
  return hours > 0
    ? `${hours}:${String(minutes).padStart(2, "0")}:${String(remainingSeconds).padStart(2, "0")}`
    : `${minutes}:${String(remainingSeconds).padStart(2, "0")}`;
}

function getCoverStyle(content: ContentSummary): CSSProperties | undefined {
  if (!content.cover.url) return undefined;
  return { backgroundImage: `url(${JSON.stringify(content.cover.url)})` };
}

export function ContentTile({ content, compact = false, className = "" }: ContentTileProps) {
  const duration = formatDuration(content.durationSeconds ?? content.cover.durationSeconds);
  const placeholder = content.cover.placeholder;
  const tileClassName = ["productContentTile", compact ? "is-compact" : "", className]
    .filter(Boolean)
    .join(" ");

  return (
    <article className={tileClassName}>
      <Link href={`/content/${encodeURIComponent(content.id)}`} aria-label={`查看《${content.title}》`}>
        <div
          className={`productContentCover${placeholder ? ` productTone--${placeholder.tone}` : ""}${content.cover.url ? " has-image" : ""}`}
          style={getCoverStyle(content)}
          role="img"
          aria-label={content.cover.alt}
        >
          {placeholder ? <span aria-hidden="true">{placeholder.mark}</span> : null}
          <div className="productContentCoverMeta" aria-hidden="true">
            <span>{formatCount(content.metrics.viewCount)} 播放</span>
            {duration ? <b>{duration}</b> : null}
          </div>
        </div>
        <div className="productContentTileBody">
          <div className="productContentTaxonomy">
            <span>{content.categoryLabel}</span>
            <span>{content.regionLabel}</span>
          </div>
          <h2>{content.title}</h2>
          {!compact ? <p>{content.summary}</p> : null}
          <div className="productContentByline">
            <span>{content.creator.displayName}</span>
            <span>{formatCount(content.metrics.interactionCount)} 互动</span>
          </div>
          <TrustBadge
            status={content.trust.status}
            label={content.trust.label}
            sourceCount={content.trust.sourceCount}
            aiAssisted={content.trust.aiAssisted}
            compact={compact}
          />
        </div>
      </Link>
    </article>
  );
}

export default ContentTile;
