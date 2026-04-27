import type { InspectorPending } from "../../api/types";

type Props = {
  pending: InspectorPending | null | undefined;
};

export function PendingState({ pending }: Props) {
  if (!pending) {
    return (
      <div className="panel">
        <h2>Pending</h2>
        <p className="muted">No pending effect or response.</p>
      </div>
    );
  }
  return (
    <div className="panel pending-state">
      <h2>Pending</h2>
      <dl className="pending-state__dl">
        <div>
          <dt>Kind</dt>
          <dd>{pending.kind}</dd>
        </div>
        {pending.reason && (
          <div>
            <dt>Reason</dt>
            <dd>{pending.reason}</dd>
          </div>
        )}
        <div>
          <dt>Actor</dt>
          <dd>{pending.actor_id}</dd>
        </div>
        <div>
          <dt>Target</dt>
          <dd>{pending.target_id}</dd>
        </div>
        {pending.respond_player_id != null && (
          <div>
            <dt>Respond as</dt>
            <dd>{pending.respond_player_id}</dd>
          </div>
        )}
        <div>
          <dt>Amount</dt>
          <dd>{pending.amount}</dd>
        </div>
        {pending.source_card_name && (
          <div>
            <dt>Source</dt>
            <dd>{pending.source_card_name}</dd>
          </div>
        )}
        {pending.negated && (
          <div>
            <dt>Negated</dt>
            <dd>Yes</dd>
          </div>
        )}
      </dl>
    </div>
  );
}
