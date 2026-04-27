import type { InspectorViewer } from "../../api/types";
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
};

type HandDockProps = {
  viewer: InspectorViewer;
  selectedCardId?: string | null;
  onSelectHandCard?: (cardId: string | null) => void;
};

export function PlayerTableState({ viewer }: Props) {
  const bankValue = sumCardValues(viewer.bank);

  return (
    <div className="player-area__zones">
      <div className="player-zone player-bank-zone" aria-label="Your bank">
        <div className="player-zone__chrome">
          <span className="player-zone__label">YOUR BANK</span>
          <span className="player-zone__badge">Bank {formatMoney(bankValue)}</span>
        </div>
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
        <div className="player-zone__chrome">
          <span className="player-zone__label">YOUR PROPERTIES</span>
          <span className="player-zone__badge">
            {propertyEntries(viewer.properties).reduce((total, [, cards]) => total + cards.length, 0)} cards
          </span>
        </div>
        <div className="player-zone__body">
          <PropertyStacks properties={viewer.properties} />
        </div>
      </div>
    </div>
  );
}

export function PlayerHandDock({
  viewer,
  selectedCardId,
  onSelectHandCard,
}: HandDockProps) {
  const hand = viewer.hand;
  const n = hand.length;

  return (
    <section className="player-area__hand-rail" aria-label="Hand dock">
      <h3 className="player-area__h3">YOUR HAND ({hand.length})</h3>
      {hand.length > 0 ? (
        <div
          className="play-hand"
          role="list"
          aria-label="Your hand"
          data-hand-count={n}
          data-hand-dense={n > 4 ? "true" : undefined}
        >
          {hand.map((card) => {
            const id = card.id ?? "";
            const key = String(id || cardLabel(card));
            const isSel = Boolean(id && selectedCardId === id);
            return (
              <div key={key} className="play-hand__item" role="listitem">
                <PlayCard
                  card={card}
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
      ) : (
        <EmptySlot label="Your hand is empty" />
      )}
    </section>
  );
}

export function PlayerArea({ viewer }: Props) {
  return (
    <section className="player-area" aria-label="Your cards">
      <PlayerTableState viewer={viewer} />
      <PlayerHandDock viewer={viewer} />
    </section>
  );
}
