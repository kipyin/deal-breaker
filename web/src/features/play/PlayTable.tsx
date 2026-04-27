import { useEffect, useMemo, useState } from "react";
import type { InspectorCard, InspectorOpponent, InspectorState, JsonObject, LegalAction } from "../../api/types";
import { BoardCenter } from "./BoardCenter";
import { CardDetailOverlay } from "./CardDetailOverlay";
import { OpponentSeat } from "./OpponentSeat";
import { OpponentDetailOverlay, type OpponentDetail } from "./OpponentDetailOverlay";
import { PlayerHandDock, PlayerTableState } from "./PlayerArea";
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
  const [detailCard, setDetailCard] = useState<InspectorCard | null>(null);
  const [opponentDetail, setOpponentDetail] = useState<OpponentDetail | null>(null);
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
    setDetailCard(null);
    setOpponentDetail(null);
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
          <div className="play-table__empty">Loading live table…</div>
        </div>
      </TableFrame>
    );
  }

  const opponents = state.opponents ?? [];
  const humanTurn = isHumanTurn(state);
  const turn = state.turn == null ? "TURN --" : `TURN ${state.turn}`;
  const actionsLeft = `${viewer.actions_left} ACTION${viewer.actions_left === 1 ? "" : "S"} LEFT`;
  const selectedCard = selectedCardId
    ? viewer.hand.find((card) => card.id === selectedCardId) ?? null
    : null;

  function showOpponentBank(opponent: InspectorOpponent) {
    setOpponentDetail({
      kind: "bank",
      opponentName: opponent.name || opponent.id,
      cards: opponent.bank ?? [],
    });
  }

  function showOpponentProperties(opponent: InspectorOpponent) {
    setOpponentDetail({
      kind: "properties",
      opponentName: opponent.name || opponent.id,
      properties: opponent.properties,
    });
  }

  return (
    <TableFrame>
      <div className="play-table__inner play-table__inner--prototype" data-table>
        <header className="play-surface__hud">
          <div className={`play-turn-banner${humanTurn ? " play-turn-banner--you" : ""}`} role="status">
            <span>{humanTurn ? "YOUR TURN" : "AI TURN"}</span>
            <small>
              <span>{turn}</span>
              <span>{actionsLeft}</span>
            </small>
          </div>
        </header>

        <section className="play-board" aria-label="Card table">
          <section className="play-opponents" aria-label="Opponent seats" data-opponent-count={opponents.length}>
            {opponents.length > 0 ? (
              opponents.map((opponent, index) => (
                <OpponentSeat
                  key={opponent.id}
                  opponent={opponent}
                  activePlayerId={state.active_player_id}
                  seatIndex={index}
                  onShowBank={showOpponentBank}
                  onShowProperties={showOpponentProperties}
                />
              ))
            ) : (
              <EmptySlot label="No opponents in snapshot" />
            )}
          </section>

          <div className="play-board__middle">
            <PlayerTableState viewer={viewer} />
            <BoardCenter
              state={state}
              legalActions={zoneActions}
              onChoose={onChoose}
              onRunAi={onRunAi}
              readOnly={readOnly}
              flashMessage={flashMessage}
              handActionsHint={selectedCard ? null : handActionsHint}
              onDraw={drawPileAction}
              drawEnabled={drawEnabled}
            />
          </div>
        </section>

        <PlayerHandDock
          viewer={viewer}
          selectedCardId={readOnly ? null : selectedCardId}
          onSelectHandCard={readOnly ? undefined : (id) => setSelectedCardId(id)}
          selectedCardActions={readOnly ? [] : actionsForSelected}
          onChooseCardAction={readOnly ? undefined : onChoose}
          onViewCardDetails={
            readOnly || !selectedCard
              ? undefined
              : () => {
                  setDetailCard(selectedCard);
                }
          }
          cardActionsDisabled={readOnly || !playerCanAct}
        />

        {detailCard ? <CardDetailOverlay card={detailCard} onClose={() => setDetailCard(null)} /> : null}
        {opponentDetail ? (
          <OpponentDetailOverlay detail={opponentDetail} onClose={() => setOpponentDetail(null)} />
        ) : null}
      </div>
    </TableFrame>
  );
}
