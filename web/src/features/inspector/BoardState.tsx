import type { InspectorState, InspectorViewer } from "../../api/types";
import { PlayerSummary } from "./PlayerSummary";
import { OpponentsPanel } from "./OpponentsPanel";

type Props = {
  state: InspectorState | null;
};

function viewerTitle(v: InspectorViewer): string {
  return `You (${v.player_id})`;
}

export function BoardState({ state }: Props) {
  const v = state?.viewer;
  if (!v) {
    return (
      <div className="panel">
        <h2>Board</h2>
        <p className="muted">No viewer snapshot.</p>
      </div>
    );
  }
  return (
    <div className="panel inspector-board">
      <h2>Board</h2>
      <div className="inspector-board__meta row" style={{ marginBottom: "0.5rem" }}>
        <span className="muted">
          Actions {v.actions_taken} / {v.actions_left} left
        </span>
        {v.discard_required > 0 && (
          <span className="inspector-board__warn">Discard {v.discard_required}</span>
        )}
      </div>
      <PlayerSummary
        title={viewerTitle(v)}
        hand={v.hand}
        bank={v.bank}
        properties={v.properties}
      />
      {state?.opponents && state.opponents.length > 0 && (
        <OpponentsPanel opponents={state.opponents} />
      )}
    </div>
  );
}
