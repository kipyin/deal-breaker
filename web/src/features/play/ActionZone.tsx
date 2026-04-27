import type {
  InspectorLastAction,
  InspectorPending,
  InspectorState,
  JsonObject,
  LegalAction,
} from "../../api/types";
import {
  actionType,
  formatMoney,
  isEndTurnAction,
  isHumanTurn,
} from "./playUtils";

function PendingSpot({ pending }: { pending: InspectorPending | null | undefined }) {
  if (!pending) {
    return (
      <div className="action-zone__callout action-zone__callout--quiet">
        <span className="action-zone__label">Pending</span>
        <span>No pending effect</span>
      </div>
    );
  }

  return (
    <div className="action-zone__callout" role="status">
      <span className="action-zone__label">Pending {pending.kind}</span>
      <strong>{pending.reason || pending.source_card_name || "Response required"}</strong>
      <span>
        {pending.actor_id} to {pending.target_id}
        {pending.amount ? ` · ${formatMoney(pending.amount)}` : ""}
      </span>
    </div>
  );
}

function LastActionSpot({ lastAction }: { lastAction: InspectorLastAction | null | undefined }) {
  if (!lastAction) {
    return (
      <div className="action-zone__callout action-zone__callout--quiet">
        <span className="action-zone__label">Last action</span>
        <span>Initial state</span>
      </div>
    );
  }

  const type = lastAction.payload.type;
  const label = typeof type === "string" ? type.replace(/_/g, " ") : "action";
  return (
    <div className="action-zone__callout action-zone__callout--quiet">
      <span className="action-zone__label">Last action</span>
      <span>
        {lastAction.player_id} played {label}
      </span>
    </div>
  );
}

type Props = {
  state: InspectorState;
  /** Subset of {@link state.legal_actions} shown as zone buttons (excludes hand-card popover actions). */
  legalActions: LegalAction[];
  onChoose: (payload: JsonObject) => void;
  onRunAi: () => void;
  readOnly?: boolean;
  flashMessage?: string | null;
  /** Shown when card plays are routed through the hand popover. */
  handActionsHint?: string | null;
};

export function ActionZone({
  state,
  legalActions,
  onChoose,
  onRunAi,
  readOnly,
  flashMessage,
  handActionsHint,
}: Props) {
  const endTurn = legalActions.find(isEndTurnAction);
  const cardActions = legalActions.filter((action) => action !== endTurn);
  const playerCanAct = isHumanTurn(state) && state.status !== "completed";

  return (
    <section className="action-zone" aria-label="Action zone">
      {flashMessage ? (
        <p className="action-zone__flash" role="alert">
          {flashMessage}
        </p>
      ) : null}
      <div className="action-zone__header">
        <span>Action zone</span>
        <span>{legalActions.length} legal</span>
      </div>
      <div className="action-zone__grid">
        <PendingSpot pending={state.pending} />
        <LastActionSpot lastAction={state.last_action} />
      </div>
      {handActionsHint ? <p className="action-zone__hint-line">{handActionsHint}</p> : null}
      {cardActions.length > 0 ? (
        <div className="action-zone__actions">
          {cardActions.map((action: LegalAction) => (
            <button
              key={action.id}
              type="button"
              className="action-card-button"
              disabled={readOnly || !playerCanAct}
              onClick={() => onChoose(action.payload)}
            >
              <span>{action.label}</span>
              <small>{actionType(action) || "action"}</small>
            </button>
          ))}
        </div>
      ) : (
        <p className="action-zone__empty">
          {playerCanAct ? "No card actions available." : "AI is resolving the table."}
        </p>
      )}
      <div className="action-zone__primary">
        {playerCanAct ? (
          <button
            type="button"
            className="pixel-button play-primary-action"
            disabled={readOnly || !endTurn}
            onClick={() => {
              if (endTurn) onChoose(endTurn.payload);
            }}
          >
            END TURN
          </button>
        ) : (
          <button
            type="button"
            className="pixel-button play-primary-action"
            disabled={readOnly || state.status === "completed"}
            onClick={onRunAi}
          >
            RUN AI UNTIL YOUR TURN
          </button>
        )}
      </div>
    </section>
  );
}
