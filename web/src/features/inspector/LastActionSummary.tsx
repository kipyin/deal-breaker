import type { InspectorState } from "../../api/types";

type Props = {
  state: InspectorState | null;
};

export function LastActionSummary({ state }: Props) {
  const last = state?.last_action;
  if (!last) {
    return (
      <div className="panel">
        <h2>Last action</h2>
        <p className="muted">No actions yet (initial state).</p>
      </div>
    );
  }
  return (
    <div className="panel last-action">
      <h2>Last action</h2>
      <p>
        <span className="last-action__player">{last.player_id}</span>
      </p>
      <pre className="inspector-raw inspector-raw--tight" style={{ maxHeight: 180 }}>
        {JSON.stringify(last.payload, null, 2)}
      </pre>
    </div>
  );
}
