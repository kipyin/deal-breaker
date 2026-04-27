import type { InspectorState } from "../../api/types";
import { isHumanTurn } from "./playUtils";

type Props = {
  state: InspectorState;
};

/**
 * Logo (left), turn banner (center), status chips (right).
 */
export function TableHud({ state }: Props) {
  const viewer = state.viewer;
  const humanTurn = isHumanTurn(state);
  const turn = state.turn == null ? "TURN --" : `TURN ${state.turn}`;
  const actionsLeft = viewer
    ? `${viewer.actions_left} ACTION${viewer.actions_left === 1 ? "" : "S"} LEFT`
    : "";

  return (
    <header className="play-table__hud" aria-label="Turn and table status">
      <div className="play-table__hud-brand">
        <p className="play-table__subtitle">Live table</p>
        <p className="play-table__brand">PIXEL PROPERTY DEAL</p>
      </div>
      <div className="play-table__hud-banner" role="status">
        <span className={`play-table__turn-flag${humanTurn ? " play-table__turn-flag--you" : ""}`}>
          {humanTurn ? "YOUR TURN" : "AI TURN"}
        </span>
        <span className="play-table__turn-meta">{turn}</span>
      </div>
      <div className="play-table__status-cluster">
        {actionsLeft ? <span className="status-chip">{actionsLeft}</span> : null}
        {viewer && viewer.discard_required > 0 ? (
          <span className="status-chip status-chip--warn">Discard {viewer.discard_required}</span>
        ) : null}
        {state.status === "completed" && (
          <span className="status-chip status-chip--ok">
            {state.winner_id ? `Winner ${state.winner_id}` : "Complete"}
          </span>
        )}
      </div>
    </header>
  );
}
