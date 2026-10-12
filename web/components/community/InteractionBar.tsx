type InteractionBarProps = {
  respected: boolean;
  bookmarked: boolean;
  wantsToLearn: boolean;
  watchLater: boolean;
  onRespectChange: (nextValue: boolean) => void;
  onBookmarkChange: (nextValue: boolean) => void;
  onWantToLearnChange: (nextValue: boolean) => void;
  onWatchLaterChange: (nextValue: boolean) => void;
  counts?: Partial<Record<"respect" | "bookmark" | "wantToLearn" | "watchLater", number>>;
  disabled?: boolean;
  compact?: boolean;
};

const countFormatter = new Intl.NumberFormat("zh-CN", {
  notation: "compact",
  maximumFractionDigits: 1,
});

export function InteractionBar({
  respected,
  bookmarked,
  wantsToLearn,
  watchLater,
  onRespectChange,
  onBookmarkChange,
  onWantToLearnChange,
  onWatchLaterChange,
  counts = {},
  disabled = false,
  compact = false,
}: InteractionBarProps) {
  const actions = [
    { key: "respect", label: "致意", icon: "礼", pressed: respected, onChange: onRespectChange },
    { key: "bookmark", label: "收藏", icon: "藏", pressed: bookmarked, onChange: onBookmarkChange },
    { key: "wantToLearn", label: "想学", icon: "学", pressed: wantsToLearn, onChange: onWantToLearnChange },
    { key: "watchLater", label: "稍后看", icon: "候", pressed: watchLater, onChange: onWatchLaterChange },
  ] as const;

  return (
    <div className={`productInteractionBar${compact ? " is-compact" : ""}`} aria-label="内容互动">
      {actions.map((action) => {
        const count = counts[action.key];
        return (
          <button
            type="button"
            aria-pressed={action.pressed}
            aria-label={`${action.pressed ? "取消" : ""}${action.label}`}
            disabled={disabled}
            onClick={() => action.onChange(!action.pressed)}
            key={action.key}
          >
            <i aria-hidden="true">{action.icon}</i>
            <span>{action.label}</span>
            {typeof count === "number" ? <small>{countFormatter.format(Math.max(0, count))}</small> : null}
          </button>
        );
      })}
    </div>
  );
}

export default InteractionBar;
