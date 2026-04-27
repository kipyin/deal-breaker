import type { InspectorCard, InspectorOpponent } from "../../api/types";
import { cardLabel } from "./utils";

type Props = {
  opponents: InspectorOpponent[];
};

function propSummary(props: Record<string, InspectorCard[] | undefined> | undefined): string {
  if (!props) return "";
  const n = Object.values(props).reduce((acc, g) => acc + (g?.length ?? 0), 0);
  return n ? `${n} on board` : "";
}

export function OpponentsPanel({ opponents }: Props) {
  return (
    <div className="opponents-panel">
      <h3 className="opponents-panel__title">Opponents</h3>
      <ul className="opponents-list">
        {opponents.map((o) => {
          const psum = propSummary(o.properties);
          return (
            <li key={o.id} className="opponents-list__row">
              <div>
                <strong>{o.name}</strong> <span className="muted">({o.id})</span>
              </div>
              <div className="opponents-list__stats muted">
                Hand {o.hand_size} · Bank ${o.bank_value} · {o.completed_sets} sets
                {psum ? ` · ${psum}` : ""}
              </div>
              {o.properties && Object.keys(o.properties).length > 0 && (
                <ul className="card-chip-list card-chip-list--compact" style={{ marginTop: "0.35rem" }}>
                  {Object.entries(o.properties).flatMap(([color, cards]) =>
                    (cards ?? []).map((c) => (
                      <li
                        key={`${o.id}-${color}-${String(c.id ?? cardLabel(c))}`}
                        className="card-chip"
                        title={JSON.stringify(c)}
                      >
                        <span className="muted" style={{ marginRight: "0.25rem" }}>
                          {color}:
                        </span>
                        {cardLabel(c)}
                      </li>
                    ))
                  )}
                </ul>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
