import type { CSSProperties } from "react";
import type { InspectorViewer, JsonObject, LegalAction } from "../../api/types";
import { CardActionPopover } from "./CardActionPopover";
import { cardLabel } from "./playUtils";
import { PlayCard } from "./PlayCard";
import { formatColor, formatMoney, propertyEntries, sumCardValues } from "./playUtils";

function EmptySlot({ label }: { label: string }) {
  return <div className="play-empty-slot">{label}</div>;
}

function PropertyStacks({ properties }: { properties: InspectorViewer["properties"] }) {
  const groups = propertyEntries(properties);
  if (groups.length === 0) return <EmptySlot label="No properties on board" />;

  return (
    <div className="play-property-stacks">
      {groups.map(([color, cards]) => (
        <section key={color} className="play-property-stack">
          <div className="play-property-stack__header">
            <span>{formatColor(color)}</span>
            <span>
              {cards.length}/3
              {cards.length >= 3 ? " ★" : ""}
            </span>
          </div>
          <div className="play-property-stack__cards">
            {cards.map((card, index) => (
              <PlayCard
                key={String(card.id ?? cardLabel(card))}
                card={card}
                compact
                stackIndex={index}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

type Props = {
  viewer: InspectorViewer;
  /** When set, hand cards with this id show as selected. */
  selectedCardId?: string | null;
  onSelectHandCard?: (cardId: string | null) => void;
  /** Legal actions for {@link selectedCardId} (popover). */
  actionsForSelectedCard?: LegalAction[];
  onChooseCardAction?: (payload: JsonObject) => void;
  cardActionDisabled?: boolean;
};

export function PlayerArea({
  viewer,
  selectedCardId,
  onSelectHandCard,
  actionsForSelectedCard,
  onChooseCardAction,
  cardActionDisabled,
}: Props) {
  const bankValue = sumCardValues(viewer.bank);
  const hand = viewer.hand;
  const n = hand.length;
  const fanStepDeg = n <= 1 ? 0 : Math.min(4.25, 30 / (n - 1));
  const handSpreadScale = n > 6 ? 0.68 : n > 4 ? 0.85 : 1;
  const selected = hand.find((c) => c.id === selectedCardId);

  return (
    <section className="player-area" aria-label="Your cards">
      <div className="player-zone player-bank-zone" aria-label="Your bank">
        <div className="player-zone__label">YOUR BANK</div>
        <div className="player-zone__badge">Bank {formatMoney(bankValue)}</div>
        <div className="player-zone__body">
          {viewer.bank.length > 0 ? (
            <div className="player-bank-zone__cards">
              {viewer.bank.map((card) => (
                <span key={String(card.id ?? cardLabel(card))} className="bank-token">
                  {formatMoney(card.value ?? 0)}
                </span>
              ))}
            </div>
          ) : (
            <EmptySlot label="Bank is empty" />
          )}
        </div>
      </div>

      <div className="player-zone player-property-zone" aria-label="Your properties">
        <div className="player-zone__label">YOUR PROPERTIES</div>
        <div className="player-zone__badge">
          {propertyEntries(viewer.properties).reduce((total, [, cards]) => total + cards.length, 0)} CARDS
        </div>
        <div className="player-zone__body">
          <PropertyStacks properties={viewer.properties} />
        </div>
      </div>

      <div
        className="player-area__hand-block"
        aria-label="Your hand"
        data-hand-count={n}
        data-hand-dense={n > 6 ? "true" : undefined}
        style={
          {
            "--play-fan-deg-per-step": `${fanStepDeg}deg`,
            "--play-hand-spread-scale": String(handSpreadScale),
          } as CSSProperties
        }
      >
        <h3 className="player-area__h3">YOUR HAND ({hand.length})</h3>
        {hand.length > 0 ? (
          <>
            <div
              className="play-card-row play-hand"
              role="list"
            >
              {hand.map((card, i) => {
                const id = card.id ?? "";
                const key = String(id || cardLabel(card));
                const isSel = Boolean(id && selectedCardId === id);
                const mid = (n - 1) / 2;
                const offset = i - mid;
                const slotStyle: CSSProperties = {
                  "--play-hand-offset": String(offset),
                  "--play-hand-abs-offset": String(Math.abs(offset)),
                  "--play-card-fan-index": String(i),
                  "--play-card-fan-total": String(n),
                  zIndex: 25 + i,
                } as CSSProperties;
                return (
                  <div key={key} className="play-hand__slot" role="listitem" style={slotStyle}>
                    <PlayCard
                      card={card}
                      fanIndex={i}
                      fanTotal={n}
                      interactive={Boolean(onSelectHandCard && id)}
                      selected={isSel}
                      onActivate={() => {
                        if (!onSelectHandCard || !id) return;
                        onSelectHandCard(isSel ? null : id);
                      }}
                    />
                  </div>
                );
              })}
            </div>
            {selected && actionsForSelectedCard && onChooseCardAction && onSelectHandCard ? (
              <CardActionPopover
                card={selected}
                actions={actionsForSelectedCard}
                onChoose={onChooseCardAction}
                onDismiss={() => onSelectHandCard(null)}
                disabled={cardActionDisabled}
              />
            ) : null}
          </>
        ) : (
          <EmptySlot label="Your hand is empty" />
        )}
      </div>
    </section>
  );
}
