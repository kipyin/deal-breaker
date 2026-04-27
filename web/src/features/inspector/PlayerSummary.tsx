import type { InspectorCard } from "../../api/types";
import { cardLabel } from "./utils";

type Props = {
  title: string;
  hand: InspectorCard[] | undefined;
  bank: InspectorCard[] | undefined;
  properties: Record<string, InspectorCard[] | undefined> | undefined;
  compact?: boolean;
};

function sortProps(entries: [string, InspectorCard[] | undefined][]) {
  return entries
    .filter(([, cards]) => cards && cards.length > 0)
    .sort(([a], [b]) => a.localeCompare(b));
}

export function PlayerSummary({ title, hand, bank, properties, compact }: Props) {
  const h = hand ?? [];
  const b = bank ?? [];
  const propRows = sortProps(Object.entries(properties ?? {}));
  return (
    <div className="player-summary">
      <h3 className="player-summary__title">{title}</h3>
      <div className="player-summary__section">
        <span className="player-summary__label">Hand</span>
        {h.length === 0 ? (
          <p className="muted player-summary__empty">Empty</p>
        ) : (
          <ul className={`card-chip-list${compact ? " card-chip-list--compact" : ""}`}>
            {h.map((c) => (
              <li key={String(c.id ?? cardLabel(c))} className="card-chip" title={JSON.stringify(c)}>
                {cardLabel(c)}
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="player-summary__section">
        <span className="player-summary__label">Bank</span>
        {b.length === 0 ? (
          <p className="muted player-summary__empty">Empty</p>
        ) : (
          <ul className={`card-chip-list${compact ? " card-chip-list--compact" : ""}`}>
            {b.map((c) => (
              <li key={String(c.id ?? cardLabel(c))} className="card-chip">
                {cardLabel(c)}
              </li>
            ))}
          </ul>
        )}
      </div>
      {propRows.length > 0 && (
        <div className="player-summary__section">
          <span className="player-summary__label">Properties</span>
          <div className="property-groups">
            {propRows.map(([color, cards]) => (
              <div key={color} className="property-group">
                <div className="property-group__color">{color.replace(/_/g, " ")}</div>
                <ul className="card-chip-list card-chip-list--compact">
                  {cards!.map((c) => (
                    <li key={String(c.id ?? cardLabel(c))} className="card-chip">
                      {cardLabel(c)}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
