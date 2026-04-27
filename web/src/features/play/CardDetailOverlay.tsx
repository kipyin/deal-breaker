import type { InspectorCard } from "../../api/types";
import { PlayCard } from "./PlayCard";
import { cardLabel, formatCardValue, formatColor } from "./playUtils";

type CardDetailOverlayProps = {
  card: InspectorCard;
  onClose: () => void;
};

export function CardDetailOverlay({ card, onClose }: CardDetailOverlayProps) {
  const label = cardLabel(card);
  const colors = card.colors?.length
    ? card.colors.map((color) => formatColor(color).toUpperCase()).join(", ")
    : card.color
      ? formatColor(card.color).toUpperCase()
      : "NONE";

  return (
    <div className="play-overlay" role="presentation">
      <button
        type="button"
        className="play-overlay-scrim"
        aria-label="Dismiss card details"
        onClick={onClose}
      />
      <section className="card-detail" role="dialog" aria-modal="true" aria-label={`Card details for ${label}`}>
        <div className="card-detail__card">
          <PlayCard card={card} />
        </div>
        <div className="card-detail__info">
          <div className="card-detail__header">
            <span>Card details</span>
            <button type="button" className="card-detail__close" aria-label="Close details" onClick={onClose}>
              Close
            </button>
          </div>
          <h3>{label}</h3>
          <dl>
            <div>
              <dt>Kind</dt>
              <dd>{card.kind ?? "card"}</dd>
            </div>
            <div>
              <dt>Cash value</dt>
              <dd>{formatCardValue(card)}</dd>
            </div>
            <div>
              <dt>Color</dt>
              <dd>{colors}</dd>
            </div>
          </dl>
        </div>
      </section>
    </div>
  );
}
