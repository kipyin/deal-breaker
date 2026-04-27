import type { InspectorLastAction, InspectorPending, InspectorState, JsonObject, LegalAction } from "../../api/types";
import { PileZone } from "./PileZone";
import { actionType, formatMoney, isEndTurnAction, isHumanTurn } from "./playUtils";

type BoardCenterProps = {
  state: InspectorState;
  legalActions: LegalAction[];
  onChoose: (payload: JsonObject) => void;
  onRunAi: () => void;
  onDraw?: () => void;
  drawEnabled: boolean;
  readOnly?: boolean;
  flashMessage?: string | null;
  handActionsHint?: string | null;
};

function PendingSpot({ pending }: { pending: InspectorPending | null | undefined }) {
  if (!pending) return <span>No pending effect</span>;
  return (
    <span>
      {pending.reason || pending.source_card_name || "Response required"}
      {pending.amount ? ` ${formatMoney(pending.amount)}` : ""}
    </span>
  );
}

function LastActionSpot({ lastAction }: { lastAction: InspectorLastAction | null | undefined }) {
  if (!lastAction) return <span>Initial state</span>;
  const type = lastAction.payload.type;
  const label = typeof type === "string" ? type.replace(/_/g, " ") : "action";
  return (
    <span>
      {lastAction.player_id} played {label}
    </span>
  );
}

export function BoardCenter({
  state,
  legalActions,
  onChoose,
  onRunAi,
  onDraw,
  drawEnabled,
  readOnly,
  flashMessage,
  handActionsHint,
}: BoardCenterProps) {
  const endTurn = legalActions.find(isEndTurnAction);
  const boardActions = legalActions.filter((action) => action !== endTurn && actionType(action) !== "drawcards");
  const playerCanAct = isHumanTurn(state) && state.status !== "completed";
  const actionsTaken = state.viewer?.actions_taken ?? 0;
  const actionsLeft = state.viewer?.actions_left ?? 0;
  const actionsTotal = actionsTaken + actionsLeft;

  return (
    <section className="board-center" aria-label="Board center">
      <PileZone state={state} onDraw={onDraw} drawEnabled={drawEnabled} />
      <div className="board-center__actions-left" aria-label="Actions left">
        ACTIONS {actionsTaken}/{actionsTotal || 3}
      </div>
      <section className="board-controls" aria-label="Board controls">
        {flashMessage ? (
          <p className="board-controls__flash" role="alert">
            {flashMessage}
          </p>
        ) : null}
        <div className="board-controls__status">
          <span>Pending</span>
          <PendingSpot pending={state.pending} />
        </div>
        <div className="board-controls__status">
          <span>Last</span>
          <LastActionSpot lastAction={state.last_action} />
        </div>
        {handActionsHint ? <p className="board-controls__hint">{handActionsHint}</p> : null}
        {boardActions.length > 0 ? (
          <div className="board-controls__actions">
            {boardActions.map((action) => (
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
          <p className="board-controls__empty">
            {playerCanAct ? "Select a hand card to play." : "AI is resolving the table."}
          </p>
        )}
        <div className="board-controls__primary" data-placement="table-bottom-right">
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
    </section>
  );
}
