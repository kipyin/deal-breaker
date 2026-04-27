import type { JsonObject, LegalAction } from "../../api/types";

type Props = {
  title?: string;
  legalActions: LegalAction[] | undefined;
  onChoose?: (payload: JsonObject) => void;
  readOnly?: boolean;
  emptyMessage?: string;
};

export function LegalActionPanel({
  title = "Legal actions",
  legalActions,
  onChoose,
  readOnly,
  emptyMessage = "No actions available for the active player at this state.",
}: Props) {
  const list = legalActions ?? [];
  return (
    <div className="panel">
      <h2>
        {title}
        {readOnly && <span className="muted" style={{ fontWeight: 400, marginLeft: "0.35rem" }}> (read-only)</span>}
      </h2>
      {list.length === 0 ? (
        <p className="muted">{emptyMessage}</p>
      ) : (
        <div className="row" style={{ flexDirection: "column", alignItems: "stretch" }}>
          {list.map((a) => (
            <button
              type="button"
              key={a.id}
              disabled={readOnly || !onChoose}
              onClick={() => onChoose?.(a.payload)}
              className="legal-action-btn"
            >
              {a.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
