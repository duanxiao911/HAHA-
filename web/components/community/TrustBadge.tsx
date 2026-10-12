import type { VerificationStatus } from "@/lib/community";

type TrustBadgeProps = {
  status: VerificationStatus;
  label?: string;
  sourceCount?: number;
  aiAssisted?: boolean;
  compact?: boolean;
};

const statusPresentation: Record<VerificationStatus, { icon: string; label: string; detail: string }> = {
  verified: { icon: "✓", label: "来源已核验", detail: "关键事实已与可信来源核对" },
  inheritor_confirmed: { icon: "传", label: "传承人确认", detail: "内容已由相关传承人确认" },
  expert_reviewed: { icon: "审", label: "专家核验", detail: "内容已由专业审核人员核验" },
  pending: { icon: "候", label: "待核验", detail: "关键事实仍在等待核验" },
  disputed: { icon: "!", label: "存在争议", detail: "部分事实存在不同来源或待处理争议" },
};

export function TrustBadge({
  status,
  label,
  sourceCount,
  aiAssisted = false,
  compact = false,
}: TrustBadgeProps) {
  const presentation = statusPresentation[status];
  const sourceDescription = typeof sourceCount === "number" ? `，关联 ${sourceCount} 条来源` : "";
  const aiDescription = aiAssisted ? "，包含 AI 辅助内容" : "";

  return (
    <span
      className={`productTrustBadge productTrustBadge--${status}${compact ? " is-compact" : ""}`}
      title={`${presentation.detail}${sourceDescription}${aiDescription}`}
    >
      <i aria-hidden="true">{presentation.icon}</i>
      <span>{label ?? presentation.label}</span>
      {!compact && typeof sourceCount === "number" ? <small>{sourceCount} 条来源</small> : null}
      {!compact && aiAssisted ? <small>AI 辅助</small> : null}
    </span>
  );
}

export default TrustBadge;
