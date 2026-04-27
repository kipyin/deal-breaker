import type { CSSProperties, KeyboardEvent, MouseEvent } from "react";
import type { InspectorCard } from "../../api/types";
import { cardLabel, formatCardValue, formatColor } from "./playUtils";

function cardKindClass(kind: string | undefined): string {
  const k = (kind ?? "card").toLowerCase();
  if (k === "wild_property" || k === "wild property") return "play-card--wild";
  if (k.includes("house")) return "play-card--house";
  if (k.includes("hotel")) return "play-card--hotel";
  if (k === "money") return "play-card--money";
  if (k === "property") return "play-card--property";
  if (k === "rent") return "play-card--rent";
  if (k === "action") return "play-card--action";
  return "play-card--default";
}

function colorToken(color: string | undefined | null): string {
  if (!color) return "neutral";
  return String(color).toLowerCase().replace(/\s+/g, "_");
}

type PlayCardProps = {
  card: InspectorCard;
  compact?: boolean;
  fanIndex?: number;
  fanTotal?: number;
  stackIndex?: number;
  /** Renders as a button with keyboard support; used for hand selection. */
  interactive?: boolean;
  selected?: boolean;
  onActivate?: () => void;
};

export function PlayCard({
  card,
  compact = false,
  fanIndex,
  fanTotal,
  stackIndex,
  interactive = false,
  selected = false,
  onActivate,
}: PlayCardProps) {
  const color = card.color ?? card.colors?.[0] ?? card.kind ?? "card";
  const label = cardLabel(card);
  const kindClass = cardKindClass(card.kind);
  const stripe = String(color).replace(/_/g, " ");
  const ct = colorToken(card.color ?? card.colors?.[0]);
  const fan =
    fanIndex != null && fanTotal != null && fanTotal > 1
      ? {
          "--play-card-fan-index": String(fanIndex),
          "--play-card-fan-total": String(fanTotal),
        }
      : undefined;
  const stack =
    stackIndex != null
      ? {
          "--play-card-stack-index": String(stackIndex),
        }
      : undefined;

  const body = (
    <>
      <div className="play-card__chrome">
        <div className={`play-card__color-band play-card__color-band--${ct}`} />
        <div className={`play-card__icon play-card__icon--${kindClass.replace("play-card--", "")}`} aria-hidden />
      </div>
      <div className="play-card__body">
        <div className="play-card__stripe">{formatColor(stripe)}</div>
        <div className="play-card__name">{label}</div>
        <div className="play-card__meta">
          <span>{card.kind ?? "card"}</span>
          <span>{formatCardValue(card)}</span>
        </div>
      </div>
    </>
  );

  const className = [
    "play-card",
    compact ? "play-card--compact" : "",
    kindClass,
    fan ? "play-card--fanned" : "",
    stack ? "play-card--stacked" : "",
    interactive ? "play-card--interactive" : "",
    selected ? "play-card--selected" : "",
  ]
    .filter(Boolean)
    .join(" ");

  const style = { ...fan, ...stack } as CSSProperties | undefined;

  function onKeyDown(e: KeyboardEvent) {
    if (!interactive) return;
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onActivate?.();
    }
  }

  function stop(e: MouseEvent) {
    e.stopPropagation();
  }

  if (interactive && onActivate) {
    return (
      <button
        type="button"
        className={className}
        style={style}
        onClick={(e) => {
          stop(e);
          onActivate();
        }}
        onKeyDown={onKeyDown}
        aria-pressed={selected}
        aria-label={label}
        title={label}
      >
        {body}
      </button>
    );
  }

  return (
    <article className={className} style={style} aria-label={label} title={label}>
      {body}
    </article>
  );
}
