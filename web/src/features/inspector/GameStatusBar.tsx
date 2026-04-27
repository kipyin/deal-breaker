import type { ReactNode } from "react";
import type { InspectorState } from "../../api/types";

type Props = {
  state: InspectorState | null;
  extra?: ReactNode;
};

export function GameStatusBar({ state, extra }: Props) {
  if (!state) {
    return (
      <div className="inspector-status-bar" aria-live="polite">
        <span className="muted">Loading state…</span>
        {extra}
      </div>
    );
  }
  const { turn, phase, active_player_id, current_player_id, winner_id, status } = state;
  return (
    <div className="inspector-status-bar" aria-live="polite">
      {typeof turn === "number" && (
        <span>
          <span className="inspector-status-bar__k">Turn</span> {turn}
        </span>
      )}
      {phase && (
        <span>
          <span className="inspector-status-bar__k">Phase</span> {phase}
        </span>
      )}
      {active_player_id && (
        <span>
          <span className="inspector-status-bar__k">To move</span> {active_player_id}
        </span>
      )}
      {current_player_id && current_player_id !== active_player_id && (
        <span>
          <span className="inspector-status-bar__k">Current</span> {current_player_id}
        </span>
      )}
      {winner_id != null && (
        <span className="inspector-status-bar--winner">
          <span className="inspector-status-bar__k">Winner</span> {String(winner_id)}
        </span>
      )}
      {status && (
        <span>
          <span className="inspector-status-bar__k">Status</span> {status}
        </span>
      )}
      {extra}
    </div>
  );
}
