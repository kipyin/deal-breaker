import { useEffect, useMemo, useState } from "react";
import type { InspectorState, JsonObject, LegalAction } from "../../api/types";
import { ActionZone } from "./ActionZone";
import { OpponentSeat } from "./OpponentSeat";
import { PileZone } from "./PileZone";
import { PlayerArea } from "./PlayerArea";
import { TableFrame } from "./TableFrame";
import {
  actionType,
  handCardIdSet,
  isEndTurnAction,
  isHumanTurn,
  legalActionsForHandCard,
  showInActionZone,
} from "./playUtils";

function EmptySlot({ label }: { label: string }) {
  return <div className="play-empty-slot">{label}</div>;
}

function findDrawAction(actions: LegalAction[]): LegalAction | undefined {
  return actions.find((a) => actionType(a) === "drawcards");
}

export type PlayTableProps = {
  state: InspectorState | null;
  onChoose: (payload: JsonObject) => void;
  onRunAi: () => void;
  readOnly?: boolean;
  /** Short user-visible message (e.g. action errors). */
  flashMessage?: string | null;
};

export function PlayTable({
  state,
  onChoose,
  onRunAi,
  readOnly,
  flashMessage,
}: PlayTableProps) {
  const [selectedCardId, setSelectedCardId] = useState<string | null>(null);
  const viewer = state?.viewer;

  const all = state?.legal_actions ?? [];
  const hand = viewer?.hand ?? [];
  const handIds = useMemo(() => handCardIdSet(hand), [hand]);
  const zoneActions = useMemo(
    () => all.filter((a) => showInActionZone(a, handIds)),
    [all, handIds]
  );
  const actionsForSelected = useMemo(
    () =>
      selectedCardId && viewer
        ? legalActionsForHandCard(selectedCardId, all, handIds)
        : [],
    [all, handIds, selectedCardId, viewer]
  );
  const hasDeferredHandPlays = useMemo(
    () => all.some((a) => !showInActionZone(a, handIds) && !isEndTurnAction(a)),
    [all, handIds]
  );

  const playerCanAct = state ? isHumanTurn(state) && state.status !== "completed" : false;
  const handActionsHint =
    state && playerCanAct && hasDeferredHandPlays
      ? "SELECT A HAND CARD FOR CARD PLAYS"
      : null;

  const drawAction = findDrawAction(all);
  const drawPileAction =
    playerCanAct && !readOnly && drawAction
      ? () => {
          onChoose(drawAction.payload);
        }
      : undefined;
  const drawEnabled = Boolean(drawPileAction);

  useEffect(() => {
    setSelectedCardId(null);
  }, [state?.version, viewer?.player_id]);

  useEffect(() => {
    if (!selectedCardId || !viewer) return;
    const still = viewer.hand.some((c) => c.id === selectedCardId);
    if (!still) {
      setSelectedCardId(null);
    }
  }, [viewer, selectedCardId]);

  if (!state || !viewer) {
    return (
      <TableFrame>
        <div className="play-table__inner play-table__inner--loading">
          <p className="play-table__brand play-table__brand--solo">PIXEL PROPERTY DEAL</p>
          <div className="play-table__empty">Loading live table…</div>
        </div>
      </TableFrame>
    );
  }

  const opponents = state.opponents ?? [];
  const humanTurn = isHumanTurn(state);
  const turn = state.turn == null ? "TURN --" : `TURN ${state.turn}`;
  const actionsLeft = `${viewer.actions_left} ACTION${viewer.actions_left === 1 ? "" : "S"} LEFT`;

  return (
    <TableFrame>
      <div className="play-table__inner play-table__inner--prototype" data-table>
        <div className="play-logo" aria-label="Game logo">
          <span className="play-logo__full">PIXEL PROPERTY DEAL</span>
          <span>PIXEL</span>
          <strong>PROPERTY DEAL</strong>
        </div>

        <div className={`play-turn-banner${humanTurn ? " play-turn-banner--you" : ""}`} role="status">
          <span>{humanTurn ? "YOUR TURN" : "AI TURN"}</span>
          <small>
            <span>{turn}</span>
            <span>{actionsLeft}</span>
          </small>
        </div>

        <section className="play-opponents" aria-label="Opponent seats">
          {opponents.length > 0 ? (
            opponents.map((opponent, index) => (
              <OpponentSeat
                key={opponent.id}
                opponent={opponent}
                activePlayerId={state.active_player_id}
                seatIndex={index}
              />
            ))
          ) : (
            <EmptySlot label="No opponents in snapshot" />
          )}
        </section>

        <div className="play-center-row">
          <PileZone
            state={state}
            onDraw={drawPileAction}
            drawEnabled={drawEnabled}
          />
          <ActionZone
            state={state}
            legalActions={zoneActions}
            onChoose={onChoose}
            onRunAi={onRunAi}
            readOnly={readOnly}
            flashMessage={flashMessage}
            handActionsHint={handActionsHint}
          />
        </div>

        <PlayerArea
          viewer={viewer}
          selectedCardId={readOnly ? null : selectedCardId}
          onSelectHandCard={readOnly ? undefined : (id) => setSelectedCardId(id)}
          actionsForSelectedCard={readOnly ? [] : actionsForSelected}
          onChooseCardAction={readOnly ? undefined : (p) => onChoose(p)}
          cardActionDisabled={readOnly || !playerCanAct}
        />
      </div>
    </TableFrame>
  );
}
