import type { CSSProperties, KeyboardEvent, MouseEvent } from "react";
import type { InspectorCard } from "../../api/types";
import { cardLabel, formatCardValue, formatColor } from "./playUtils";

const RENT_LADDER_BY_COLOR: Record<string, number[]> = {
  brown: [1, 2],
  light_blue: [1, 2, 3],
  pink: [1, 3, 5],
  orange: [1, 3, 5],
  red: [2, 3, 6],
  yellow: [2, 3, 6],
  green: [2, 4, 7],
  blue: [3, 8],
  railroad: [1, 2, 3, 4],
  utility: [1, 2],
};

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

function cardKind(card: InspectorCard): string {
  return (card.kind ?? "card").toLowerCase();
}

function primaryColor(card: InspectorCard): string | null {
  return card.color ?? card.colors?.[0] ?? null;
}

function displayColor(card: InspectorCard): string {
  const color = primaryColor(card);
  if (!color) return "WILD";
  return formatColor(color).toUpperCase();
}

function rentLadder(card: InspectorCard): string | null {
  const color = primaryColor(card);
  if (!color) return null;
  const ladder = RENT_LADDER_BY_COLOR[colorToken(color)];
  if (!ladder) return null;
  return ladder.map((value) => formatCardValue({ value })).join(" -> ");
}

function simplifiedTitle(card: InspectorCard): string {
  const kind = cardKind(card);
  if (kind === "property" || kind === "wild_property" || kind === "wild property") {
    return `${displayColor(card)} property`;
  }
  if (kind === "money") return formatCardValue(card);
  return cardLabel(card);
}

function simplifiedAriaLabel(card: InspectorCard): string {
  const kind = cardKind(card);
  const value = formatCardValue(card);
  if (kind === "property" || kind === "wild_property" || kind === "wild property") {
    const ladder = rentLadder(card);
    return `${displayColor(card)} property ${value}${ladder ? ` rent ${ladder}` : ""}`;
  }
  if (kind === "money") return `Money ${value}`;
  return `${cardLabel(card)} ${kind} ${value}`;
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
  const label = simplifiedAriaLabel(card);
  const kindClass = cardKindClass(card.kind);
  const ct = colorToken(card.color ?? card.colors?.[0]);
  const kind = cardKind(card);
  const isProperty = kind === "property" || kind === "wild_property" || kind === "wild property";
  const isMoney = kind === "money";
  const title = simplifiedTitle(card);
  const value = formatCardValue(card);
  const ladder = isProperty ? rentLadder(card) : null;
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
      <div className={`play-card__chrome play-card__chrome--${ct}`} aria-hidden />
      <div className="play-card__body">
        <div className="play-card__stripe">
          {isMoney ? "BANK" : isProperty ? "PROPERTY" : kind.toUpperCase().replace(/_/g, " ")}
        </div>
        <div className="play-card__name">{title}</div>
        <div className="play-card__meta">
          {isProperty && ladder ? <span>{ladder}</span> : null}
          {!isMoney ? <span>{value}</span> : null}
        </div>
      </div>
    </>
  );

  const className = [
    "play-card",
    compact ? "play-card--compact" : "",
    kindClass,
    `play-card--color-${ct}`,
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
