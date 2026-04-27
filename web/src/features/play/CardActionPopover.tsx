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

export function CardActionPopover({
  card,
  actions,
  onChoose,
  onDismiss,
  disabled,
}: Props) {
  const label = cardLabel(card);

  return (
    <div
      className="card-action-popover"
      role="dialog"
      aria-label={`Actions for ${label}`}
      data-placement="hand"
    >
      <div className="card-action-popover__header">
        <span className="card-action-popover__title">{label}</span>
        <button
          type="button"
          className="card-action-popover__close"
          onClick={onDismiss}
          aria-label="Cancel card selection"
        >
          ×
        </button>
      </div>
      {actions.length === 0 ? (
        <p className="card-action-popover__empty">
          No legal plays for this card right now.
        </p>
      ) : (
        <ul className="card-action-popover__list">
          {actions.map((action) => (
            <li key={action.id}>
              <button
                type="button"
                className="card-action-popover__btn"
                disabled={disabled}
                onClick={() => {
                  onChoose(action.payload);
                  onDismiss();
                }}
              >
                <span className="card-action-popover__hint">{choiceHint(action.payload)}</span>
                <span className="card-action-popover__label">{action.label}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <button
        type="button"
        className="card-action-popover__cancel pixel-button pixel-button--secondary"
        onClick={onDismiss}
      >
        Cancel
      </button>
    </div>
  );
}
