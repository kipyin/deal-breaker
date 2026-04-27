import { useEffect, useId, useState } from "react";

type Props = {
  step: number;
  maxStep: number;
  disabled?: boolean;
  onStepChange: (next: number) => void;
};

function clamp(n: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, n));
}

export function ReplayStepControls({ step, maxStep, disabled, onStepChange }: Props) {
  const [jump, setJump] = useState(String(step));
  const id = useId();
  const safeMax = maxStep;
  const canMove = !disabled && safeMax > 0;

  useEffect(() => {
    setJump(String(step));
  }, [step]);

  useEffect(() => {
    if (!canMove) return;
    const onKey = (ev: KeyboardEvent) => {
      const t = ev.target as HTMLElement | null;
      if (t) {
        const tag = t.tagName;
        if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || t.isContentEditable) {
          return;
        }
      }
      if (ev.key === "ArrowLeft") {
        ev.preventDefault();
        onStepChange(clamp(step - 1, 0, safeMax));
      } else if (ev.key === "ArrowRight") {
        ev.preventDefault();
        onStepChange(clamp(step + 1, 0, safeMax));
      } else if (ev.key === "Home") {
        ev.preventDefault();
        onStepChange(0);
      } else if (ev.key === "End") {
        ev.preventDefault();
        onStepChange(safeMax);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [canMove, onStepChange, step, safeMax]);

  return (
    <div className="replay-step-controls" role="group" aria-labelledby={`${id}-label`}>
      <div className="row" id={`${id}-label`} style={{ alignItems: "center" }}>
        <span>
          Step <strong>{step}</strong>
          <span className="muted"> / {safeMax}</span>
        </span>
        <input
          type="range"
          min={0}
          max={safeMax}
          value={clamp(step, 0, safeMax)}
          onChange={(e) => onStepChange(parseInt(e.target.value, 10))}
          disabled={!canMove}
          aria-label="Scrub replay step"
          className="replay-step-controls__range"
        />
        <div className="replay-step-controls__btns" role="toolbar" aria-label="Step navigation">
          <button
            type="button"
            onClick={() => onStepChange(0)}
            disabled={!canMove || step <= 0}
            title="First (Home)"
            aria-label="First replay step"
          >
            «
          </button>
          <button
            type="button"
            onClick={() => onStepChange(clamp(step - 1, 0, safeMax))}
            disabled={!canMove || step <= 0}
            title="Previous (←)"
            aria-label="Previous replay step"
          >
            ←
          </button>
          <button
            type="button"
            onClick={() => onStepChange(clamp(step + 1, 0, safeMax))}
            disabled={!canMove || step >= safeMax}
            title="Next (→)"
            aria-label="Next replay step"
          >
            →
          </button>
          <button
            type="button"
            onClick={() => onStepChange(safeMax)}
            disabled={!canMove || step >= safeMax}
            title="Last (End)"
            aria-label="Last replay step"
          >
            »
          </button>
        </div>
        <form
          className="replay-step-controls__jump"
          onSubmit={(e) => {
            e.preventDefault();
            const n = parseInt(jump, 10);
            if (Number.isFinite(n)) onStepChange(clamp(n, 0, safeMax));
          }}
        >
          <label className="muted" htmlFor={`${id}-jump`} style={{ marginRight: "0.35rem" }}>
            Go to
          </label>
          <input
            id={`${id}-jump`}
            type="number"
            min={0}
            max={safeMax}
            value={jump}
            onChange={(e) => setJump(e.target.value)}
            disabled={!canMove}
            style={{ width: "4.5rem" }}
          />
        </form>
      </div>
      <p className="muted" style={{ margin: "0.25rem 0 0", fontSize: "0.82rem" }}>
        Use arrow keys to step when not typing. Home/End jump to first/last.
      </p>
    </div>
  );
}
