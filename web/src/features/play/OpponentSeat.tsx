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

  return (
    <article className={`opponent-seat opponent-seat--${seatIndex}${isActive ? " opponent-seat--active" : ""}`}>
      <div className="opponent-seat__top">
        <div className="opponent-seat__avatar" aria-hidden>
          {avatar}
        </div>
        <div>
          <div className="opponent-seat__name">{opponent.name}</div>
          <div className="opponent-seat__id">{isActive ? "TURN" : opponent.id}</div>
        </div>
        <div className="opponent-seat__stats">
          <span>Hand {opponent.hand_size}</span>
          <span>Bank {formatMoney(opponent.bank_value)}</span>
          <span>{opponent.completed_sets} sets</span>
        </div>
      </div>
      <div className="opponent-seat__mini-hand" aria-hidden>
        {Array.from({ length: Math.min(opponent.hand_size, 5) }).map((_, i) => (
          <span key={i} />
        ))}
      </div>
      {groups.length > 0 && (
        <div className="opponent-seat__props" aria-label="Property progress">
          {groups.map(([color, cards]) => (
            <span key={color} title={`${formatColor(color)}: ${cards.length} cards`}>
              <span className="opponent-seat__prop-meter">
                <span
                  className="opponent-seat__prop-meter-fill"
                  style={{ width: `${Math.min(100, cards.length * 25)}%` }}
                />
              </span>
              <span className="opponent-seat__prop-label">
                {formatColor(color)} ×{cards.length}
              </span>
            </span>
          ))}
        </div>
      )}
    </article>
  );
}
