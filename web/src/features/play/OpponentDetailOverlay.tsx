import type { InspectorCard } from "../../api/types";
import { PlayCard } from "./PlayCard";
import { formatColor, formatMoney, propertyEntries, sumCardValues } from "./playUtils";

type OpponentDetail =
  | {
      kind: "bank";
      opponentName: string;
      cards: InspectorCard[];
    }
  | {
      kind: "properties";
      opponentName: string;
      properties: Record<string, InspectorCard[]>;
    };

type OpponentDetailOverlayProps = {
  detail: OpponentDetail;
  onClose: () => void;
};

export function OpponentDetailOverlay({ detail, onClose }: OpponentDetailOverlayProps) {
  const title = `${detail.opponentName} ${detail.kind}`;
  const groups = detail.kind === "properties" ? propertyEntries(detail.properties) : [];
  const bankTotal = detail.kind === "bank" ? sumCardValues(detail.cards) : 0;

  return (
    <div className="play-overlay" role="presentation">
      <button
        type="button"
        className="play-overlay-scrim"
        aria-label="Dismiss details"
        onClick={onClose}
      />
      <section className="opponent-detail" role="dialog" aria-modal="true" aria-label={title}>
        <div className="opponent-detail__header">
          <span>{title}</span>
          <button type="button" className="card-detail__close" aria-label="Close details" onClick={onClose}>
            Close
          </button>
        </div>

        {detail.kind === "bank" ? (
          <>
            <p className="opponent-detail__summary">Bank total {formatMoney(bankTotal)}</p>
            <div className="opponent-detail__cards">
              {detail.cards.length > 0 ? (
                detail.cards.map((card, index) => (
                  <PlayCard key={String(card.id ?? `${card.name}-${index}`)} card={card} compact />
                ))
              ) : (
                <p className="play-empty-slot">No bank cards</p>
              )}
            </div>
          </>
        ) : (
          <div className="opponent-detail__groups">
            {groups.length > 0 ? (
              groups.map(([color, cards]) => (
                <section key={color} className="opponent-detail__group">
                  <h3>{formatColor(color).toUpperCase()}</h3>
                  <div className="opponent-detail__cards">
                    {cards.map((card, index) => (
                      <PlayCard key={String(card.id ?? `${card.name}-${index}`)} card={card} compact />
                    ))}
                  </div>
                </section>
              ))
            ) : (
              <p className="play-empty-slot">No properties</p>
            )}
          </div>
        )}
      </section>
    </div>
  );
}

export type { OpponentDetail };
