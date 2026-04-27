import type { InspectorCard, JsonObject, InspectorState, LegalAction } from "../../api/types";

export function formatMoney(value: number): string {
  return `$${value}M`;
}

export function sumCardValues(cards: InspectorCard[] | undefined): number {
  return (cards ?? []).reduce((total, card) => total + (card.value ?? 0), 0);
}

export function formatCardValue(card: InspectorCard): string {
  return card.value == null ? "No value" : formatMoney(card.value);
}

export function formatColor(color: string): string {
  return color.replace(/_/g, " ");
}

export function propertyEntries(
  properties: Record<string, InspectorCard[] | undefined> | undefined
): [string, InspectorCard[]][] {
  return Object.entries(properties ?? {})
    .filter((entry): entry is [string, InspectorCard[]] => Boolean(entry[1]?.length))
    .sort(([a], [b]) => a.localeCompare(b));
}

export function actionType(action: LegalAction): string {
  const value = action.payload.type;
  return typeof value === "string" ? value.toLowerCase() : "";
}

export function payloadType(payload: JsonObject): string {
  const t = payload.type;
  return typeof t === "string" ? t : "";
}

export function payloadPrimaryCardId(payload: JsonObject): string | null {
  if (typeof payload.card_id === "string") return payload.card_id;
  const ids = payload.card_ids;
  if (Array.isArray(ids) && ids.length > 0 && typeof ids[0] === "string") {
    return ids[0];
  }
  return null;
}

/**
 * Return legal actions that apply to a specific card in the viewer hand, shown
 * in the hand-card popover (bank/play/rent/discard, etc.). Multi-card and
 * global actions stay in the action zone.
 */
export function legalActionsForHandCard(
  cardId: string,
  all: LegalAction[],
  handIdSet: Set<string>
): LegalAction[] {
  return all.filter(
    (a) =>
      !isGlobalOrMultiCardAction(a) && shouldDeferToHandCardPopover(a, handIdSet) && payloadPrimaryCardId(a.payload) === cardId
  );
}

function isGlobalOrMultiCardAction(action: LegalAction): boolean {
  const t = actionType(action);
  if (t === "endturn" || t === "drawcards") return true;
  if (t === "paywithassets" || t === "respondjustsayno") return true;
  return false;
}

export function shouldDeferToHandCardPopover(action: LegalAction, handIdSet: Set<string>): boolean {
  if (isGlobalOrMultiCardAction(action)) return false;
  const cid = payloadPrimaryCardId(action.payload);
  return cid != null && handIdSet.has(cid);
}

export function showInActionZone(
  action: LegalAction,
  handIdSet: Set<string>
): boolean {
  if (isEndTurnAction(action)) return true;
  if (isGlobalOrMultiCardAction(action)) return true;
  return !shouldDeferToHandCardPopover(action, handIdSet);
}

export function isEndTurnAction(action: LegalAction): boolean {
  const label = action.label.toLowerCase();
  const t = actionType(action);
  return label.includes("end turn") || t === "endturn" || t.includes("end_turn");
}

export function isHumanTurn(state: InspectorState | null): boolean {
  const viewerId = state?.viewer?.player_id;
  if (!viewerId) return false;
  // The seat that may act is `active_player_id` (payer, responder, or current turn).
  // `current_player_id` can differ during payment/response; do not treat it alone as permission.
  return state?.active_player_id === viewerId;
}

export function handCardIdSet(hand: InspectorCard[] | undefined): Set<string> {
  const s = new Set<string>();
  for (const c of hand ?? []) {
    if (c.id) s.add(c.id);
  }
  return s;
}

export { cardLabel } from "../inspector";
