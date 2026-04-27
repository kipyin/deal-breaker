import type { InspectorOpponent } from "../../api/types";
import { formatMoney, formatColor, propertyEntries } from "./playUtils";

type Props = {
  opponent: InspectorOpponent;
  activePlayerId?: string;
  seatIndex?: number;
};

export function OpponentSeat({ opponent, activePlayerId, seatIndex = 0 }: Props) {
  const groups = propertyEntries(opponent.properties);
  const isActive = activePlayerId === opponent.id;
  const avatar = opponent.name?.trim().charAt(0).toUpperCase() || opponent.id.charAt(0).toUpperCase();
  const label = `${opponent.name || opponent.id} (${opponent.id})`;

  return (
    <article
      className={`opponent-seat opponent-seat--${seatIndex}${isActive ? " opponent-seat--active" : ""}`}
      aria-label={label}
    >
      <div className="opponent-seat__row">
        <div className="opponent-seat__avatar" aria-hidden>
          {avatar}
        </div>
        <div className="opponent-seat__main">
          <div className="opponent-seat__name-line">
            <span className="opponent-seat__name">{opponent.name || opponent.id}</span>
            {isActive ? (
              <span className="opponent-seat__turn-pill" title="Current turn">
                Turn
              </span>
            ) : null}
          </div>
          <div className="opponent-seat__meta" aria-label={`${opponent.id} stats`}>
            <span className="opponent-seat__id">{opponent.id}</span>
            <span>Hand {opponent.hand_size}</span>
            <span>Bank {formatMoney(opponent.bank_value)}</span>
            <span>{opponent.completed_sets} sets</span>
          </div>
        </div>
      </div>
      {groups.length > 0 ? (
        <div className="opponent-seat__props-line" aria-label="Property progress">
          {groups.map(([color, cards]) => (
            <span key={color} className="opponent-seat__prop-chip" title={`${formatColor(color)}: ${cards.length} cards`}>
              {formatColor(color).slice(0, 3)}×{cards.length}
            </span>
          ))}
        </div>
      ) : null}
    </article>
  );
}
