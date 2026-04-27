import type { InspectorState } from "../../api/types";
import { PlayCard } from "./PlayCard";

function EmptySlot({ label }: { label: string }) {
  return <div className="play-empty-slot">{label}</div>;
}

type Props = {
  state: InspectorState;
  /** When set, draw pile is clickable to submit a draw action (visual only if false). */
  onDraw?: () => void;
  drawEnabled?: boolean;
};

export function PileZone({ state, onDraw, drawEnabled }: Props) {
  const deck = state.deck_count;
  const discardN = state.discard_count;
  const top = state.discard_top;

  const deckLabel =
    typeof deck === "number" ? `${deck}` : "—";
  const discardLabel =
    typeof discardN === "number" ? `${discardN}` : "—";

  const drawInteractive = Boolean(onDraw);
  const drawInner = (
    <>
      <span className="pile-zone__label">DRAW PILE</span>
      <span className="pile-zone__deck-art" aria-hidden>
        <span />
        <span />
        <span>DRAW<br />+2</span>
      </span>
      <strong>{deckLabel}</strong>
      <span className="pile-zone__hint">LEFT</span>
    </>
  );

  return (
    <div className="pile-zone" aria-label="Draw and discard piles" data-layout="side-by-side">
      {drawInteractive ? (
        <button
          type="button"
          className={`pile-zone__draw deck-stack deck-stack--interactive${drawEnabled ? "" : " deck-stack--disabled"}`}
          onClick={() => {
            if (drawEnabled) onDraw?.();
          }}
          disabled={!drawEnabled}
          aria-label={drawEnabled ? "Draw +2 cards" : "Draw pile (no draw action available)"}
        >
          {drawInner}
        </button>
      ) : (
        <div className="pile-zone__draw deck-stack">{drawInner}</div>
      )}
      <div className="pile-zone__discard deck-stack deck-stack--discard">
        <span className="pile-zone__label">DISCARD</span>
        <strong>{discardLabel}</strong>
        {top ? (
          <div className="pile-zone__top-card">
            <PlayCard card={top} compact />
          </div>
        ) : (
          <EmptySlot label="No discard yet" />
        )}
      </div>
    </div>
  );
}
