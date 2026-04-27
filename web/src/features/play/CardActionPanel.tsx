import type { InspectorCard, JsonObject, LegalAction } from "../../api/types";
import { cardLabel, payloadType } from "./playUtils";

type Props = {
  card: InspectorCard;
  actions: LegalAction[];
  onChoose: (payload: JsonObject) => void;
  onDismiss: () => void;
  disabled?: boolean;
};

function choiceHint(payload: JsonObject): string {
  const t = payloadType(payload);
  switch (t) {
    case "BankCard":
      return "Play to bank";
    case "PlayProperty":
      return "Play as property";
    case "PlayRent":
      return "Collect rent";
    case "PlayActionCard":
      return "Use action";
    case "DiscardCard":
      return "Discard";
    case "RearrangeProperty":
      return "Move property";
    default:
      return t.replace(/([A-Z])/g, " $1").trim() || "Play";
  }
}

/** Inline card actions below the hand (not a floating popover). */
export function CardActionPanel({
  card,
  actions,
  onChoose,
  onDismiss,
  disabled,
}: Props) {
  const label = cardLabel(card);

  return (
    <section
      className="card-action-panel"
      role="region"
      aria-label={`Actions for ${label}`}
    >
      <div className="card-action-panel__header">
        <span className="card-action-panel__title">{label}</span>
        <button
          type="button"
          className="card-action-panel__close"
          onClick={onDismiss}
          aria-label="Cancel card selection"
        >
          ×
        </button>
      </div>
      {actions.length === 0 ? (
        <p className="card-action-panel__empty">No legal plays for this card right now.</p>
      ) : (
        <ul className="card-action-panel__list">
          {actions.map((action) => (
            <li key={action.id}>
              <button
                type="button"
                className="card-action-panel__btn"
                disabled={disabled}
                onClick={() => {
                  onChoose(action.payload);
                  onDismiss();
                }}
              >
                <span className="card-action-panel__hint">{choiceHint(action.payload)}</span>
                <span className="card-action-panel__label">{action.label}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <button
        type="button"
        className="card-action-panel__cancel pixel-button pixel-button--secondary"
        onClick={onDismiss}
      >
        Cancel
      </button>
    </section>
  );
}

/** @deprecated Use {@link CardActionPanel}. */
export const CardActionPopover = CardActionPanel;
